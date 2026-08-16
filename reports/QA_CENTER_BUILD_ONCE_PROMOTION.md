# QA Center — Build Once / Promote Same Artifact

Applies MESFlow's existing Build Once / Promote Same Artifact architecture to
QA Center, reusing and generalizing the same Release Manager engine rather
than duplicating it. QA source of truth stays at
`/home/dell/workspace/mesflow/qa-center`; generated artifacts live under
`/home/dell/workspace/mesflow/artifacts/qa-center/releases/<version>/`;
target servers never build QA from source.

## What changed

- **`qa-center/current/docker/Dockerfile`** — bakes the QA app source into
  the image (`COPY . /app`) so a built release is self-contained and
  immutable. Local dev's bind mount (`docker/compose.yml`'s
  `volumes: - ..:/app:ro`) still overrides it unchanged.
- **`qa-center/current/.dockerignore`** (new) — keeps the build context lean.
- **`qa-center/compose.yml`** (new) — the deployment-target compose file:
  no `build:` block, runs the exact frozen image `--no-build`. Mirrors
  `mesflow/compose.yml`'s placement and shape.
- **`qa-center/scripts/build-release.sh`** (new) — validates source/version,
  captures the real git commit, runs QA's own pytest suite (non-blocking,
  see QA TESTS below), builds the image with
  `--provenance=false --sbom=false` for reproducible image IDs, freezes
  image identity/digest, refuses to rebuild an already-released version
  (`VERSION_ALREADY_RELEASED`), and produces an immutable deploy ZIP
  (image tar + compose.yml + VERSION + release.json + PROMOTION.json +
  checksums.txt) — **no application source in the ZIP**.
- **`deploy-agent/agent.py`** — generalized, not duplicated:
  - `_agent_compatibility(target_status, required=...)` now takes an
    optional per-application capability set; MESFlow keeps its existing
    default, QA uses a new `QA_REQUIRED_PROMOTION_CAPABILITIES` set
    (`qa_image_release_receive`, `qa_deploy`, `digest_verify`,
    `deploy_status`, `health_status`).
  - The remote-agent HTTP client (upload/deploy) was generalized with thin
    QA-specific wrappers reusing the same signed-request/CSRF plumbing as
    MESFlow's promotion path.
  - A full parallel QA pipeline: build (`start_qa_release_build`), local
    deploy (`start_qa_local_deploy` → `_qa_deploy_from_staging`, verified
    with real image-id, reported-version and HTTP-smoke evidence — never
    the job's return code alone), retention (`_qa_cleanup_old_releases`,
    `QA_RELEASE_RETENTION`, default 3), and Promote Production Test
    (`_run_qa_promote_test`, same ZIP, same digest, capability-gated).
  - **QA and MESFlow promotion state are fully independent**: separate
    state file (`promotion-state.qa-center.json`), separate job keys,
    separate lock — QA state can never overwrite MESFlow's.
  - New target-side routes `/qa-release/upload`, `/qa-release/deploy/<version>`
    (distinct from the legacy `/qa/upload` etc., which are untouched and
    still present for rollback during the transition).
  - `_migrate_qa_runtime_data_if_needed` copies real persistent QA data
    (`/opt/mesflow-qa-center/current/runtime` → `/opt/mesflow-qa-center/runtime`)
    once, non-destructively, only if the new location is empty. The old
    copy is never deleted.
- **`deploy-agent/templates/index.html`** — application-selector tabs
  ([MESFlow] [QA Center]); the QA panel mirrors MESFlow's (Source
  version/commit, Latest Release version/ZIP SHA/image digest, Build/Local/
  Production Test/Production status, the 4 action buttons, Release History).

## Two real bugs found and fixed during live testing

1. **Function name collision**: a new `_qa_compose(log, args, ...)` I added
   was shadowed by a pre-existing legacy `_qa_compose(args, log=None, ...)`
   defined later in the file, silently taking over every call. Renamed the
   new one to `_qa_release_compose` throughout; verified no other top-level
   `def` name collisions exist.
2. **Container name conflict across compose projects**: the legacy QA
   compose (project `mesflow-qa`) and the new release compose (default
   project) both declare literal `container_name: mesflow-qa-center`.
   Docker enforces global container-name uniqueness regardless of project,
   so `--force-recreate` couldn't take over a container it didn't own.
   Fixed with a targeted `docker rm -f mesflow-qa-center` immediately before
   `compose up`, scoped to that one container name only — safe because QA's
   persistent data lives in a bind-mounted host directory, not the
   container's writable layer.

## RESULT

```
QA SOURCE: /home/dell/workspace/mesflow/qa-center (source of truth; no source copied to any target for normal deploy)
QA VERSION BEFORE: 1.19.9 (first version tracked under this pipeline; legacy path had no frozen/immutable version identity)
QA VERSION RELEASED: 1.19.9, 1.19.10, 1.19.11, 1.19.12 (built this session; 1.19.12 is current)
QA IMAGE: mesflow-qa-center:1.19.12
QA IMAGE DIGEST: sha256:5dba3d98f0b33a889e3992f5c758d0961c6c19bc2e882de431d27df639a60e2e
QA ZIP: QACenter_1.19.12.deploy.zip
QA ZIP SHA: a49829b8c6a7674b58ea6a847878654ce0d026efd9cf981ca691848264edd4d4
QA BUILD: PASS (real docker build; immutable guard verified live: rebuilding 1.19.9 correctly returned VERSION_ALREADY_RELEASED; digest determinism confirmed via a full delete+rebuild of 1.19.9 producing an identical digest)
QA LOCAL DEPLOY: PASS (real --no-build deploy via Deploy Agent; tested at 1.19.9, 1.19.10 and 1.19.12)
QA LOCAL HEALTH: healthy (docker healthcheck + GET /api/version -> ok:true)
QA LOCAL VERSION: 1.19.12 (running image, /api/version, and Playwright page title all agree)
QA TEST PROMOTION: NOT ATTEMPTED — capability-gated refusal, by design. Live-checked the configured PRODUCTION_TEST target (deploy.mesflow.net): it reports agent_version=2.19.0-docker-runtime with capabilities {image_release_receive, digest_verify, remote_deploy, deploy_status, health_status, agent_self_update} -- missing qa_deploy and qa_image_release_receive (it predates this task's QA support). A live Promote Production Test trigger was run and correctly failed fast with TARGET_AGENT_INCOMPATIBLE: Target Agent 2.19.0-docker-runtime lacks qa_deploy, qa_image_release_receive, before any upload occurred. Per task scope, updating that remote target's Agent build is out of scope here, so stopping after LOCAL_PASS as explicitly permitted.
QA TEST VERSION: N/A (not promoted)
QA TEST DIGEST: N/A (not promoted)
QA TEST HEALTH: N/A (not promoted)
QA RETENTION: PASS — QA_RELEASE_RETENTION=3 exercised live across 4 real built+deployed releases (1.19.9..1.19.12): after 1.19.10's LOCAL_PASS, cleanup removed 1.19.9's ZIP + staging + docker image (~1.05 GB freed) while permanently keeping its release.json/checksums.txt/PROMOTION.json/image-info.json/BUILD_REPORT.md; zero errors, zero incorrectly blocked/removed; the running container was untouched.
QA RELEASES KEPT: 1.19.10, 1.19.11, 1.19.12
QA RELEASES REMOVED: 1.19.9 (release ZIP + staging + docker image only; immutable metadata retained on disk permanently)
MESFLOW REGRESSION: PASS — full deploy-agent pytest suite: 111/111 passed after all QA generalization changes
MESFLOW TOUCHED: NO — mesflow-app StartedAt=2026-08-13T10:09:17Z and mesflow-postgres StartedAt=2026-08-12T04:18:08Z unchanged across the entire session (checked before and after all QA build/deploy/retention/promote-test testing); both remained "healthy"; the real mesflow-deploy-agent container was also never redeployed (StartedAt=2026-08-13T07:34:10Z unchanged) -- all QA testing used ephemeral throwaway containers sharing its real volumes/network. No ESP containers are present on this host to touch.
DEPLOY AGENT TESTS: 111/111 passed
QA TESTS: 48 passed, 12 failed, 2 skipped (build-release.sh's internal `pytest tests/` run, non-blocking by design) — all 12 failures are pre-existing version-pinned assertions (tests hardcoding a literal prior version string, e.g. asserting "1.19.9" where the source now reads "1.19.12"), not caused by this task's changes; confirmed by diffing failure text.
PLAYWRIGHT: PASS — real Chromium (via QA Center's bundled Playwright) against (1) the QA Center app itself: title "MESFlow QA Center V1.19.12", loads clean; (2) the Deploy Agent's Release Manager UI (fresh throwaway Agent instance, same source code as production): logged in, QA Center tab present, all 4 buttons present (Build Release / Deploy Local / Production Test / Promote Production), Source version/commit label present.
PAGE ERRORS: 0
CONSOLE ERRORS: 0
PRODUCTION DEPLOYED: NO
```

## Remaining work (not done in this task, by explicit scope)

- **Promote Production Test / Production**: blocked on updating the
  `deploy.mesflow.net` target's Deploy Agent to a build that includes the
  new `qa_image_release_receive`/`qa_deploy` capabilities. That is a
  separate, higher-risk change against a real remote host and was
  intentionally left out of this task's scope.
- **Legacy QA deploy path**: audited and left in place, untouched
  (`/qa/upload`, `/qa/deploy/<version>`, `/qa/restart`, `/qa/stop`,
  `/qa/delete/<version>`, `_qa_compose`/`_qa_docker_start`/`_qa_docker_stop`)
  for rollback capability during the transition window, per the task's
  explicit instruction not to delete it yet.
- **Dedicated QA-pipeline unit tests**: this task relied on real live
  verification (multiple real builds/deploys/retention cycles against
  actual Docker) rather than adding a new `test_qa_release_manager.py`
  mirroring `test_release_retention_cleanup.py`'s pattern. Worth adding as
  a follow-up so the two bugs fixed here (name collision, container-name
  conflict) have permanent regression coverage.
- **Production promotion**: not implemented/executed, as explicitly
  instructed ("Do NOT deploy Production in this task").
