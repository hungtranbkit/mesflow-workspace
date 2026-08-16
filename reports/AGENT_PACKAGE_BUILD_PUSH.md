# Deploy Agent Package Build + Push

Project: `deploy-agent/`. Goal: build the Deploy Agent's own immutable
installer package from the Agent Update page (not a manual shell command),
and push it to Bootstrap for install/update/rollback -- without
duplicating Bootstrap's own updater logic.

## ARCHITECTURE (unchanged, confirmed against the real contracts)

```
DEV Deploy Agent  ──build──▶  artifacts/deploy-agent/releases/<version>/
                                 AGENT_UPDATE_<version>.zip (+ .sha256,
                                 manifest.json, agent-release.json,
                                 checksums.txt, BUILD_REPORT.md)
DEV Deploy Agent  ──push───▶  Bootstrap :8098  POST /updater/update
                                 (bearer token, same wire contract as the
                                 old :8099 updater.py service)
Bootstrap         ──installs─▶ Target Deploy Agent :8090
```

Bootstrap's `deploy-agent/updater/updater.py` (vendored **unmodified** into
Bootstrap per `bootstrap/AGENTS.md`) owns verify → `docker load` → image-id
verify → `docker compose up` (restart) → poll target `/agent/health` →
verify version → rollback-on-failure, **all inside one synchronous HTTP
call**. Nothing in this task touches that file or reimplements any of it.

## WHAT ALREADY EXISTED (found during audit, reused as-is)

- `scripts/build-agent-release.sh` -- version validation, immutable-once
  guard, Docker image build, SHA256, `agent-release.json` manifest. Had to
  be run manually from a terminal; no UI trigger.
- `_agent_releases_root()` / `_latest_agent_release()` -- reads the
  manifest back.
- `_agent_updater_target()` / `_push_agent_update()` / `_run_agent_update()`
  / `start_agent_update()` -- the entire push mechanism, already wired to
  `POST /api/release-manager/update-agent` with `role=PRODUCTION_TEST` (no
  extra confirm) / `role=PRODUCTION` (requires `{"confirm":true}` AND
  `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1`), already surfacing
  `SUCCESS`/`ROLLED_BACK`/`ROLLBACK_FAILED`/`FAILED` from Bootstrap's
  response. None of this needed to change.

## WHAT WAS ADDED

- **Build trigger**: `POST /api/release-manager/build-agent-package` runs
  the script as a background job (`agent_package_build_job`,
  QUEUED→BUILDING→SUCCESS/FAILED), same pattern as the existing ESP/
  MESFlow build jobs.
- **Latest package identity + Download**: `_agent_update_tab_context()`
  now includes `latest_agent_release` (version, built-at, image digest,
  source commit, package size, package SHA256); `GET
  /api/release-manager/agent-package/download` serves the ZIP.
- **`scripts/build-agent-release.sh`** pipeline extended: source preflight
  (required files present) → version validation (unchanged) → **tests**
  (the deploy-agent test suite, isolated `WORKSHOP_AGENT_HOME`, `pytest`
  installed on demand if missing) → package build → SHA256 → **manifest.json**
  (canonical directory-level copy of `agent-release.json` -- the filename
  Bootstrap's updater extracts *from the ZIP* stays exactly
  `agent-release.json`, never renamed) → **BUILD_REPORT.md** → immutable
  artifact. `$dist` is only created once the artifact is real, so a
  failed/interrupted attempt leaves no stale directory behind.
- **UI**: new "Deploy Agent Package" card on the Agent Update page (Build
  button, identity display or empty state, build log). States shown:
  BUILDING, READY (package built, not yet pushed), UPLOADING (the push
  POST is in flight -- display-only relabeling of the existing
  QUEUED/UPDATING/PUSHING statuses), PASS (relabeling of SUCCESS), FAILED,
  ROLLED_BACK (unchanged, matches Bootstrap's own wire value exactly).
  VERIFYING/INSTALLING/RESTARTING/HEALTH CHECK are **not** shown as live
  states -- Bootstrap's single synchronous `/updater/update` call doesn't
  expose progress for them, and inventing fake real-time granularity
  would violate this project's own "do not invent quantities/times/
  evidence" rule. They're documented as static, honest pipeline text
  instead ("Bootstrap đang xử lý: verify → install → restart → health
  check → xác nhận version").

## REAL BUGS FOUND WHILE VERIFYING LIVE (fixed before reporting)

1. `Path(__file__).resolve().parent/"scripts"/...` resolved to `/app/scripts/`
   inside the running container -- `/app` is the image's baked copy and
   never includes `scripts/` (see `docker/Dockerfile`'s COPY list). Fixed
   with a new `DEPLOY_AGENT_SOURCE_DIR` env var (mirroring the existing
   `MESFLOW_SOURCE_DIR` convention exactly), pointed at the real
   bind-mounted workspace path in `compose.dev.override.yml`.
2. `pytest` is intentionally not in `requirements.txt` (it would bloat
   every deployed Agent, including TEST/PRODUCTION roles that never
   build) -- the tests stage now installs it on demand into whichever
   interpreter it picks.
3. The container's `docker-cli` package doesn't support the classic
   `docker build --provenance=false --sbom=false` flags (legacy,
   non-BuildKit CLI) -- switched to `docker buildx build ... --load`
   (added `docker-cli-buildx` to the image) which works identically on
   the host (which already has buildx) and inside the container.
4. `zip` wasn't installed in the image at all -- `package_installer.sh`
   (used by the pipeline's own test suite) needs it; added to the image.

All 4 were proven via a real, live "Build Agent Package" run against the
running container that failed on each in turn, was fixed, and re-run
until it passed for real -- not assumed from reading the Dockerfile.

## TEST: build package

**PASS, live, for real.** Version bumped to `2.24.2-docker-runtime`,
triggered via the real `POST /api/release-manager/build-agent-package`
against the running Agent. Full pipeline completed: source preflight →
version validation → **440 tests passed** (real `pytest tests/` inside
the container) → real `docker buildx build` → real artifact:

```
artifacts/deploy-agent/releases/2.24.2-docker-runtime/
  AGENT_UPDATE_2.24.2-docker-runtime.zip   216,120,084 bytes
  AGENT_UPDATE_2.24.2-docker-runtime.zip.sha256
  agent-release.json
  checksums.txt
  manifest.json
  BUILD_REPORT.md
```

`GET /api/release-manager/agent-package/download` served the file and its
SHA256 matched (`0861cbae84a0...`) byte for byte.

## TEST: bad version

**PASS, live, real script invocation** against an isolated copy of the
repo: `VERSION.txt` set to `not-a-valid-version` → `VERSION_INVALID`,
exit nonzero, no artifact.

## TEST: duplicate version

**PASS, live.** A pre-existing `agent-release.json` under the target
version's release dir → `VERSION_ALREADY_RELEASED`, exit nonzero. Also
proven organically during this verification pass: re-running the build
for `2.24.1` after it had already produced a divergent image (built once
via `docker compose build` for my own dev-loop rebuild, once via
`build-agent-release.sh`'s stricter attestation-disabled build) correctly
refused with `IMAGE_TAG_CONTAMINATED` rather than silently retagging.

## TEST: checksum

**PASS.** `AGENT_UPDATE_2.24.2-docker-runtime.zip.sha256` matches a fresh
`sha256sum` of the downloaded file; `checksums.txt` inside the release
dir matches the tar bundle + `agent-release.json` Bootstrap's
`extract_and_verify_artifact()` independently re-verifies on install
(unmodified code, not touched by this task).

## TEST: Production Test push

**Route-level, mocked -- not a live push.** This dev environment has no
real Bootstrap target configured (`MESFLOW_PRODUCTION_TEST_AGENT_UPDATER_URL`
is empty here), so a genuine end-to-end push could not be exercised.
Verified instead: `POST /api/release-manager/update-agent
{"role":"PRODUCTION_TEST"}` starts the job with no extra confirmation
required (unchanged behavior); `_run_agent_update()` correctly reports
`AGENT_ARTIFACT_NOT_FOUND` when nothing is built, and correctly surfaces
whatever status Bootstrap's response contains.

## TEST: rollback

**Mocked, not live** (same real-target limitation as above).
`_push_agent_update()` mocked to return `{"status":"ROLLED_BACK",...}`
(Bootstrap's real value when its own health-check-after-install fails and
it restores the previous image) -- `agent_update_job.status` ends at
`ROLLED_BACK`, matching Bootstrap's wire contract exactly, no new status
vocabulary invented.

## TEST: UI progress

**PASS, live.** Real Playwright pass against the rebuilt Agent: page
shows the real version/SHA256/download link; idle page makes **0**
`/api/*` requests over 8s (no auto-triggered build or push just from
opening the tab); a plain refresh re-shows the same real data; 0 console
errors, 0 page errors.

## TEST: normal browser refresh

**PASS.** Covered by both the live Playwright pass above and an automated
test (`test_agent_update_tab_normal_refresh_never_starts_a_build_or_push`)
that opens the tab 3 times with `start_agent_package_build`/
`start_agent_update` monkeypatched to flag if called -- neither ever is.

## FILES CHANGED

- `agent.py` -- `DEPLOY_AGENT_SOURCE_DIR`, `AGENT_PACKAGE_BUILD_LOCK`,
  `agent_package_build_job_update()`, `_run_agent_package_build()`,
  `start_agent_package_build()`, enriched `_latest_agent_release()`
  (package size/SHA256), 2 new routes, `_agent_update_tab_context()`
  extended, `_release_live_status_payload()` + `_ORPHANABLE_JOB_KEYS`
  extended with `agent_package_build_job`.
- `scripts/build-agent-release.sh` -- source preflight, tests stage
  (on-demand pytest install), `manifest.json`, `BUILD_REPORT.md`,
  buildx switch, `$dist` created only once real.
- `docker/Dockerfile` -- added `zip`, `docker-cli-buildx`.
- `docker/compose.dev.override.yml` -- added `DEPLOY_AGENT_SOURCE_DIR`.
- `templates/release/_agent_update_tab.html` -- new package card, Build
  button wiring, display-label mapping, build-job polling folded into the
  existing gated poller (no second timer).
- `tests/test_agent_package_build_push.py` -- new, 27 tests (manifest
  read, real script guards, mocked job state machine incl. TESTS_FAILED/
  VERSION_ALREADY_RELEASED/timeout classification, routes, download,
  push gating/rollback/missing-artifact, UI identity + empty state +
  no-auto-trigger, shared live-status key, orphan reconciliation).
- `tests/test_orphaned_job_reconciliation.py` -- updated for the new job
  key.

## AUTOMATED TESTS

`tests/test_agent_package_build_push.py`: 27 passed. Full suite (fresh
isolated `WORKSHOP_AGENT_HOME`): **424 passed, 0 failed** (skip count
varies run-to-run for unrelated environment-contingent tests, as in every
prior pass this session).

## AGENT REBUILT: YES
`docker compose -f docker/compose.linux.yml -f docker/compose.dev.override.yml -f docker/compose.bootstrap.override.yml up -d --build mesflow-deploy-agent`,
several times while iterating on the 4 real bugs above, from the official
workspace. `mesflow-app`/`mesflow-postgres`/`mesflow-nginx` were not
restarted at any point (uptimes: 3h/15h/15h, unaffected by this session's
~40 minutes of deploy-agent rebuilds).

## AGENT HEALTH: PASS
`docker ps` → `healthy`. `GET /agent/live` → `{"ok":true,"agent_version":"2.24.2-docker-runtime",...}`.
`GET /agent/health` → HTTP 200.

## PRODUCTION DEPLOYED: NO
