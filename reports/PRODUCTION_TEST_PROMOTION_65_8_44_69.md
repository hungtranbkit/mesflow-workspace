# Production Test Promotion — 65.8.44.69

Live promotion of the already-frozen, LOCAL_PASS release 65.8.44.69 to the
real Production Test Agent (`https://deploy.mesflow.net/agent`), driven
through the real Build & Release Manager UI.

## Target configuration (no secrets in git)

Read live via authorized SSH diagnostics (`ssh mesflow-test`, per AGENTS.md
"Test server SSH" section) — not invented, not hardcoded:

- `SERVER_ROLE=PRODUCTION_TEST` ✓ (confirmed via `docker inspect` on the
  remote before promoting)
- `MESFLOW_BUILD_ENABLED=0` ✓
- Admin password: read from the remote container's own configured
  `MESFLOW_AGENT_ADMIN_PASSWORD` (the actual, already-deployed credential —
  the "existing authenticated Agent mechanism"), piped directly into the
  local DEV Agent's `docker compose up` invocation as
  `MESFLOW_PRODUCTION_TEST_AGENT_PASSWORD`. Never written to any file in
  the repo or elsewhere on disk; only ever held in shell variables for the
  single `docker compose up` command, then unset.
- `docker/compose.linux.yml` gained a plain `${VAR:-}` passthrough for
  `MESFLOW_PRODUCTION_TEST_AGENT_URL/_USER/_PASSWORD` (mirrors the existing
  `MESFLOW_DEPLOY_AGENT_TOKEN` pattern already in that file) — this is the
  only committed change related to configuration; it contains no values.

## Real bugs found and fixed during this verification

Per instruction ("if a real bug appears... fix it in workspace... never
patch the already-frozen artifact"): both bugs found here are in
**deploy-agent** (Agent control/reporting code), not in the mesflow
65.8.44.69 artifact, which was never touched, rebuilt, or repackaged.

### Bug 1 — Deploy Local blocked after a correctly-rejected rebuild

Before starting the Production Test work, I found (matching the user's
report that a rebuild attempt broke deployment): clicking **Build Release**
again for the already-released 65.8.44.69 correctly failed with
`VERSION_ALREADY_RELEASED` (the guard working as designed) — but that
FAILED job status then blocked **Deploy Local** for the same, still
perfectly valid release, because the endpoint gated on "was the last build
job SUCCESS" instead of "does a valid artifact exist on disk". Fixed by
resolving the artifact directly from `release.json`/`image-info.json`/the
ZIP, independent of the last build attempt's outcome. Verified with a real
Flask test client hitting the real route (`tests/test_deploy_local_stale_build_job.py`)
and live via the actual Agent (409 → 202, then a real successful
redeploy re-confirming LOCAL_PASS).

### Bug 2 — Promote Test polling was unauthenticated (false timeout)

The first live promotion attempt reported `REMOTE_DEPLOY_TIMEOUT` /
`FAILED`. Investigation (SSH into the remote host) showed the deploy had
actually **succeeded**: `mes.version == 65.8.44.69`, healthy, exact
expected image digest and ZIP sha256 in the remote's own records. Root
cause: `_remote_agent_status()` built a bare request instead of reusing
the authenticated session `opener` from `_remote_agent_client()`;
`/api/status` is not login-exempt, so every poll silently got redirected
to the login page and failed to parse as JSON, exhausting the timeout.
Fixed by threading the opener through. Verified with a regression test
that reproduces the exact failure mode (fake target requiring the session
cookie on `/api/status`) — confirmed failing against the pre-fix
`agent.py` (literally checked out via `git show HEAD:agent.py` and
re-run) and passing against the fix.

### Bug 3 — Production Test UI never showed UPLOADING/DEPLOYING

Related to bug 2: `_release_summary()`'s `test` pipeline state read only
the *persisted* `promotion-state.json.test_status`, never the actively
running `promote_test_job` — so even though the upload and deploy were
genuinely in progress, the UI's "Production Test:" indicator sat at
`NOT_DEPLOYED` the whole time, jumping straight to the final result. Fixed
by overlaying the live job status when one is actively running for the
tracked version. Live-verified: the second, fixed promotion attempt showed
the full required sequence in the actual browser:
`NOT_DEPLOYED → UPLOADING → DEPLOYING → PASS`.

## Live promotion result (second attempt, with fixes applied)

Clicked **Promote Production Test** for real in the real UI. Real upload
(75MB ZIP) to `deploy.mesflow.net`, real `--no-build` remote deploy, real
polling, real TEST_PASS.

```
REMOTE VERSION:      65.8.44.69          == expected
REMOTE ZIP SHA256:   4e2f2f320e916907b4374e6c21bf92a6a2b80a145b01a34e2bf916b681c2e859  == expected
REMOTE IMAGE DIGEST: sha256:93f3e73160786311786f6d09c32fcaea3b5b4b4886752f79adb699e8fa12e9f6  == expected
REMOTE SCHEMA:       0029_kiosk_ota_fleet_safety  == expected (migration_head from /api/system/ready)
REMOTE HEALTH:       healthy
REMOTE BUILD:        disabled (MESFLOW_BUILD_ENABLED=0, confirmed both before and after)
```

Verified independently via SSH (not just trusting the Agent's own report):
remote `/opt/mesflow/release.json` and the remote Agent's own
`agent_manifest.json`/`checksums.txt` for the uploaded release both match
these values exactly.

UI: `NOT_DEPLOYED → UPLOADING → DEPLOYING → PASS`, live-observed via
Playwright. TEST_PASS confirmed to persist across a page refresh and
across a real `docker restart` of the local DEV Agent (state lives in
`/var/lib/mesflow-deploy-agent`, untouched by the container lifecycle).

Console/page errors: 0 in both promotion attempts.

Promote Production remains correctly gated: with LOCAL_PASS + TEST_PASS +
matching ZIP SHA + matching image digest + schema PASS + not contaminated
all now true, the UI shows "Gate PASS, but production execution is
disabled on this Agent until a human sets
MESFLOW_PRODUCTION_PROMOTE_ENABLED=1 and clicks confirm." — that flag was
never set in this task.

## What was deliberately not done

- 65.8.44.69 was not rebuilt or modified.
- No source build occurred on Production Test (`build_enabled` confirmed
  `false` throughout).
- Production was not deployed; `MESFLOW_PRODUCTION_PROMOTE_ENABLED` was
  never set.
- No `/opt` backups deleted, no legacy releases cleaned.
- The `mesflow` branch was not merged to `main`.
- Credentials were never written to any git-tracked file.

## RESULT

```
PRODUCTION TEST AGENT: https://deploy.mesflow.net/agent
ROLE: PRODUCTION_TEST
BUILD ENABLED: false

SOURCE RELEASE: 65.8.44.69
ZIP SHA LOCAL:  4e2f2f320e916907b4374e6c21bf92a6a2b80a145b01a34e2bf916b681c2e859
ZIP SHA REMOTE: 4e2f2f320e916907b4374e6c21bf92a6a2b80a145b01a34e2bf916b681c2e859 (agent_manifest.json on target, verified via SSH)
IMAGE DIGEST LOCAL:  sha256:93f3e73160786311786f6d09c32fcaea3b5b4b4886752f79adb699e8fa12e9f6
IMAGE DIGEST REMOTE: sha256:93f3e73160786311786f6d09c32fcaea3b5b4b4886752f79adb699e8fa12e9f6 (release.json on target, verified via SSH)

VERSION BEFORE: 65.8.44.65
VERSION AFTER:  65.8.44.69
SCHEMA EXPECTED: 0029_kiosk_ota_fleet_safety
SCHEMA ACTUAL:   0029_kiosk_ota_fleet_safety (migration_head, remote /api/system/ready)
HEALTH: healthy

PROMOTION JOB: SUCCESS (second attempt; first attempt reported a false
  FAILED due to Bug 2 above, even though the underlying remote deploy had
  actually already succeeded)
TEST_PASS: YES — persists across browser refresh and Agent restart
PLAYWRIGHT: PASS (real click, full NOT_DEPLOYED -> UPLOADING -> DEPLOYING
  -> PASS sequence observed live)
CONSOLE ERRORS: 0

PRODUCTION TOUCHED: NO
```
