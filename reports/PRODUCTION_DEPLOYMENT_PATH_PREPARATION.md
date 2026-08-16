# Production Deployment Path — Preparation

Prepares (does not execute) Production promotion for 65.8.44.69, per the
task's explicit "Do NOT deploy Production" scope.

## 1. Freeze 65.8.44.69

`artifacts/releases/65.8.44.69/PRODUCTION_CANDIDATE.json` — a new file
only (`release.json`, `checksums.txt`, `image-info.json`, the deploy ZIP
were not touched; verified by mtime before/after). Records
`local_pass: true`, `test_pass: true`, `production_candidate: true`, the
frozen `package_sha256`/`image_digest`/`source_commit`/`schema_revision`,
and pointers to the LOCAL_PASS/TEST_PASS evidence reports.
`artifacts/releases/65.8.44.69/PROMOTION.json` already showed
`local.status: success` and `production_test.status: success` from the
prior session's live verification — unchanged.

## 2. Deploy Agent fixes — finalized and versioned

`deploy-agent` now at **2.18.0** (was 2.17.4 at the start of this task).
`docs/history/UPDATE_NOTES_V2.18.0_PRODUCTION_PREFLIGHT.txt` summarizes
the full 2.17.1→2.18.0 fix chain (git safe.directory, PROMOTION.json
sync, Deploy Local stale-job blocking, unauthenticated status polling,
live UI state) alongside this task's new Production preflight feature.
70/70 tests pass (63 prior + 7 new).

## 3. DEV / TEST / Production Agent compatibility

| | Version | Role | Build enabled |
|---|---|---|---|
| DEV (local) | 2.18.0-docker-runtime | DEV | true |
| Production Test (`deploy.mesflow.net`) | 2.16.10-docker-runtime | PRODUCTION_TEST | false |
| Production | **unknown — no access** | — | — |

Live-verified backward compatibility: ran the new read-only preflight
(`_run_production_preflight`, GET-only) against the real, older,
reachable TEST Agent. It returned real disk/Docker/PostgreSQL/MESFlow
data correctly, and gracefully reported `/api/ops/backups` as
`{"error": "404 Not Found"}` (that endpoint is new in 2.18.0) and an
empty schema (`migration_head` is new in 2.18.0) — neither crashed the
check nor incorrectly blocked the overall `healthy` verdict. This
confirms a ~15-version gap between DEV and a target Agent degrades
gracefully rather than breaking. Production's Agent version is unknown
(no access), so this specific compatibility claim is unverified for the
real Production host — flagged below.

## 4-6. Production target configuration + read-only preflight

**Implemented and working; the real target is NOT configured — this is a
genuine gap, not something skipped.**

- `MESFLOW_PRODUCTION_AGENT_URL/_USER/_PASSWORD` passthrough added to
  `docker/compose.linux.yml` (mirrors the existing
  `MESFLOW_PRODUCTION_TEST_AGENT_*` pattern — variable references only,
  no values committed).
- New `docker/compose.production.override.yml`
  (`SERVER_ROLE=PRODUCTION`, `MESFLOW_BUILD_ENABLED=0`).
- New read-only preflight (`POST /api/release-manager/production-preflight`,
  a "Production Preflight" button in the UI): logs in, then issues **GET
  requests only** — `/api/status`, `/api/ops/summary`, a new
  `/api/ops/backups`. Never calls `/upload` or `/deploy/<version>`.
  Reports:
  - Agent health, `server_role`, `build_enabled`, `deploy_enabled`, whether
    a deploy job is currently running
  - Current MESFlow version, health, and **schema** (`migration_head` —
    the real applied Alembic head, never the app-version-shaped
    `schema_version` label, per AGENTS.md)
  - PostgreSQL health
  - Disk usage
  - Docker container health counts
  - Backup/rollback readiness (count, most recent, free space; rollback
    mechanism description)
  - Release compatibility (`deploy_enabled` true, `build_enabled` false)
  - An overall `healthy` boolean

**NEED_USER — real Production target is not configured anywhere in this
environment:**
- No SSH alias exists for it (only `mesflow-test` does, per `~/.ssh/config`).
- No URL, no credentials, are stored or discoverable anywhere in the
  workspace or on this host.
- `deploy-agent/docker/release-targets.dev.json` already explicitly marks
  it `"status":"NOT_CONFIGURED"` with a placeholder URL
  (`https://deploy.example/agent`) — this is a pre-existing, deliberate
  placeholder, not an oversight on my part.
- To complete items 4-6 against the real host, I need either an SSH
  alias/access equivalent to `mesflow-test`, or the Production Agent's
  URL + admin credentials directly. I did not invent, guess, or reuse the
  Test credentials for this — nothing was configured against a
  potentially-wrong target.
- The mechanism itself is fully built, tested (against a fake server) and
  live-verified for graceful degradation (against the real, reachable
  TEST Agent) — the moment real access is provided, configuring it is a
  one-line `docker compose up` invocation with three env vars, exactly
  like Production Test was configured in the prior session.

## 7-9. Gate / human approval — unchanged and extended

Promote Production (`POST /api/release-manager/promote-production`)
still:
- Re-verifies the full gate on every call (never trusts a cached flag).
- **Now additionally requires** a cached preflight result that is both
  `healthy: true` **and** fresh (checked within the last 15 minutes) —
  added this task. A stale "healthy" no longer keeps the gate open
  indefinitely.
- Returns 403 unless `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` is set on
  this Agent **and** the request body carries `{"confirm": true}`.
- Returns 501 even then — this Agent build does not execute a production
  deploy. `MESFLOW_PRODUCTION_PROMOTE_ENABLED` was never set during this
  task.

Live-verified: with the real target unconfigured, the UI shows Promote
Production disabled with the exact reason "Blocked: Production target not
configured (set MESFLOW_PRODUCTION_AGENT_URL/_USER/_PASSWORD)" — 0
console/page errors (Playwright).

## 10. Exact promotion identity, verified

`_run_production_preflight()`/gate logic never rebuilds, repacks, copies
source, or triggers a server-side Docker build — it only ever reads
`artifacts/releases/65.8.44.69/` (frozen at step 1) and issues GET
requests to the target. The frozen identity that any future Production
promotion would use:

```
Version:      65.8.44.69
ZIP SHA256:   4e2f2f320e916907b4374e6c21bf92a6a2b80a145b01a34e2bf916b681c2e859
Image digest: sha256:93f3e73160786311786f6d09c32fcaea3b5b4b4886752f79adb699e8fa12e9f6
Schema:       0029_kiosk_ota_fleet_safety
```

matches `artifacts/releases/65.8.44.69/PRODUCTION_CANDIDATE.json`,
`release.json` and `checksums.txt` exactly (unchanged since the prior
session — verified by mtime).

## Tests

```
deploy-agent pytest: 70/70 PASS (was 63/63 at task start; 7 new for
  the preflight feature)
python3 -m py_compile agent.py: OK
docker compose config -q: dev / production / production-test all VALID
Jinja template parse: OK; both <script> blocks pass `node --check`
  (learned from the prior session's regression: Jinja parsing alone does
  not catch JS syntax errors)
Real Flask test-client render of / (authenticated): 200, contains the
  new Production Preflight panel
Playwright (real browser, real local Agent): logged in, both new/updated
  buttons render correctly disabled with exact reasons, 0 console errors,
  0 page errors
```

## What was deliberately not done

- 65.8.44.69 was not rebuilt, repacked, or modified.
- Production was not deployed; `MESFLOW_PRODUCTION_PROMOTE_ENABLED` was
  never set.
- The real Production Agent was never contacted (no access) and nothing
  was configured against it.
- No `/opt` backups deleted, no legacy releases cleaned.
- The `mesflow` branch was not merged to `main`.
- No credentials were written to any git-tracked file.

## RESULT

```
DEPLOY AGENT VERSION: 2.18.0-docker-runtime (was 2.17.4 at task start)
DEV AGENT:        2.18.0-docker-runtime, SERVER_ROLE=DEV, healthy
TEST AGENT:        2.16.10-docker-runtime, SERVER_ROLE=PRODUCTION_TEST, MESFLOW_BUILD_ENABLED=false, healthy
PRODUCTION AGENT: NOT CONFIGURED / NO ACCESS -- NEED_USER (see section 4-6)

PRODUCTION PREFLIGHT: implemented, tested, live-verified against the
  reachable TEST Agent (read-only, graceful degradation confirmed) --
  not run against real Production (no access)
CURRENT PROD VERSION: unknown (no access)
CURRENT PROD SCHEMA:  unknown (no access)
DB HEALTH:            unknown (no access)
BACKUP READY:         unknown (no access) -- mechanism implemented (/api/ops/backups)
ROLLBACK METADATA:    unknown (no access) -- mechanism implemented (automatic pre-deploy backup, reported by /api/ops/backups)

RELEASE:      65.8.44.69 (unchanged, frozen, PRODUCTION_CANDIDATE)
ZIP SHA:      4e2f2f320e916907b4374e6c21bf92a6a2b80a145b01a34e2bf916b681c2e859
IMAGE DIGEST: sha256:93f3e73160786311786f6d09c32fcaea3b5b4b4886752f79adb699e8fa12e9f6
SCHEMA:       0029_kiosk_ota_fleet_safety

PRODUCTION GATE: NOT PASSED -- blocked on "Production target not configured"
  (all other gate conditions -- LOCAL_PASS, TEST_PASS, ZIP SHA unchanged,
  image digest unchanged, schema PASS, not contaminated -- are already
  satisfied and verified)
READY FOR HUMAN APPROVAL: NO -- blocked on infrastructure access
  (Production Agent URL/credentials), not on anything code- or
  release-related. Once provided: configure the three env vars, click
  Production Preflight, confirm healthy, then Promote Production still
  requires MESFLOW_PRODUCTION_PROMOTE_ENABLED=1 plus explicit human
  confirmation -- neither is automated.

PRODUCTION DEPLOYED: NO
```
