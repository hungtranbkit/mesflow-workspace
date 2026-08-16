# ProjectFlow Standardization — Execution Report

Date: 2026-08-15
Host: this workspace's Ubuntu dev machine (see critical host-role finding in
`reports/PROJECTFLOW_STANDARDIZATION_ASSESSMENT.md` §5)

## What was added

| File | Purpose |
|---|---|
| `WORKSPACE.yaml` | root product manifest, 4 projects, dependencies, production policy |
| `mesflow/PROJECT.yaml` | MESFlow App logical-action manifest |
| `deploy-agent/PROJECT.yaml` | Deploy Agent logical-action manifest (local_deploy disabled, see below) |
| `qa-center/PROJECT.yaml` | QA Center logical-action manifest (local_deploy disabled, see below) |
| `esp-kiosk/PROJECT.yaml` | ESP32 firmware logical-action manifest |
| `mesflow/compose.projectflow-local.yml` | isolated local sandbox compose (new) |
| `mesflow/scripts/projectflow/{_common,preflight,build,test,deploy-local,smoke,status-local,logs-local,stop-local}.sh` | ProjectFlow contract entrypoints (new, thin wrappers over existing engines where one already existed) |
| `mesflow/.gitignore` | added `runtime-projectflow-local/` |
| `mesflow/Dockerfile.test` | **one-line fix**, see "Defect found and fixed" below |
| `docs/PROJECTFLOW_INTEGRATION.md` | integration reference |
| `reports/PROJECTFLOW_STANDARDIZATION_ASSESSMENT.md` | evidence-based scan (Phase 1) |

Nothing under `mesflow/app/`, `mesflow/scripts/build-release.sh`,
`scripts/deploy-local.sh`, `scripts/promote-test.sh`, `deploy-agent/agent.py`,
or any compose file other than the two listed above was modified. No
production system was touched. No SSH to any remote host was performed.

## Commands executed, in order, with real results

### 1. `./scripts/projectflow/preflight.sh` (in `mesflow/`)

```
PASS  docker available
PASS  docker daemon reachable
PASS  docker compose available
PASS  VERSION.txt / compose.yml / compose.projectflow-local.yml / Dockerfile / requirements.txt present
PASS  disk free: 353534668 KB (>2GB)
PASS  port 18280 free
PASS  compose.projectflow-local.yml config valid
PREFLIGHT PASS
```

### 2. `./scripts/projectflow/build.sh` → real `docker build` + real release

```
IMAGE RELEASE PASS
Version: 71.0.0.5
Image: mesflow-app:71.0.0.5
Digest: sha256:f926c1ee52db0a36d5c282f3431b22a528d1066daaea165f45cbe1e2f5ecf122
Schema: 0037_v72_audit_operations_separation
Package: artifacts/releases/71.0.0.5/MESFlow_71.0.0.5.deploy.zip
WROTE artifacts/latest/mesflow-app.json
BUILD PASS
```

`artifacts/releases/71.0.0.5/` did not previously exist (workspace
`VERSION.txt` was already bumped ahead of the running `71.0.0.4`), so this
is a genuinely new, previously-unbuilt version — not a rebuild of anything
already deployed. This only creates a new Docker image tag; it does not
touch any running container.

### 3. `./scripts/projectflow/deploy-local.sh` → isolated sandbox

```
Compose project: mesflow-projectflow-local
Image:           mesflow-app:71.0.0.5
Port:            127.0.0.1:18280
 Network mesflow-projectflow-local_network Created
 Container mesflow-projectflow-local-postgres Created/Started/Healthy
 Container mesflow-projectflow-local-app Created/Started
DEPLOY LOCAL PASS (app=healthy postgres=healthy)
```

Confirmed via `docker ps` immediately after that all five pre-existing live
containers (`mesflow-deploy-agent`, `mesflow-app`, `mesflow-postgres`,
`mesflow-qa-center`, `mesflow-nginx`) were untouched — still their original
`Up <N>` uptime, unchanged image tags/status.

### 4. `./scripts/projectflow/smoke.sh` → real HTTP readiness evidence

```
postgres: healthy
app:      healthy
health:  {"ok":true,"status":"healthy","version":"71.0.0.5","schema_version":"72.0.0.0", ...}
ready:   {"ok":true,"status":"ready","version":"71.0.0.5","migration_head":"0037_v72_audit_operations_separation", ...}
version: {"version":"71.0.0.5","deployment_id":"projectflow-local-sandbox", ...}
SMOKE PASS
```

### 5. `./scripts/projectflow/status-local.sh`

```
SERVICE=mesflow-app
ENV=local-sandbox
COMPOSE_PROJECT=mesflow-projectflow-local
STATUS=healthy
VERSION=71.0.0.5
APP_CONTAINER=mesflow-projectflow-local-app
APP_RUNNING=true
APP_HEALTH=healthy
POSTGRES_HEALTH=healthy
URL=http://127.0.0.1:18280
```

### 6. `./scripts/projectflow/logs-local.sh --tail 30`

Produced real Postgres/app boot logs (migrations applied, admin seeded,
waitress serving) — no secrets present in the output (admin password/secret
key are sandbox-only placeholders, never printed).

### 7. `./scripts/projectflow/test.sh` → real, isolated pytest + defect found

First run failed at **collection** (before any test executed):

```
FileNotFoundError: [Errno 2] No such file or directory: 'gateway/compose.yml'
  (tests/test_agent_nginx_contract_v6584412.py, imported at module load)
```

**Root cause (pre-existing, unrelated to this task):**
`mesflow/Dockerfile.test` copies `nginx ./nginx` into the test image but
never copies `gateway/` — yet a static contract test reads
`gateway/compose.yml`. This would fail identically today on `main` for
anyone running `mesflow/scripts/test/docker-test.sh` directly, with or
without any ProjectFlow changes.

**Fix applied** (one line, `mesflow/Dockerfile.test`):
```diff
 COPY nginx ./nginx
+COPY gateway ./gateway
```

Re-running after rebuilding the `tests` image:

```
54 failed, 240 passed, 175 deselected in 1.86s
```

All 54 failures are pre-existing, unrelated to this task: legacy
per-release "static contract" tests (`tests/test_v6584444_*.py` through
`tests/test_v6584454_*.py`, `tests/test_release_*`, `tests/test_po_control_*`,
etc.) that hardcode an *exact historical* `VERSION.txt` string from the
`65.8.44.xx` release era (the codebase is now `71.0.0.5`) and/or snapshot
exact UI text/markup from that same era. Example:

```
tests/test_v6584452_session_exception_history.py::test_version_declarations_are_synchronized
  AssertionError: assert '71.0.0.5' == '65.8.44.56'
```

This is test debt, not a regression from this task, and fixing it means
either rewriting dozens of historical contract tests or changing current
UI/business code to match assertions written for a version 5+ major
versions ago — explicitly out of scope
("Không refactor business logic MESFlow chỉ để đạt chuẩn"). Reported here,
not silently patched.

The `tests` container's cleanup trap (`down -v --remove-orphans`) ran
correctly on failure — `docker ps -a` confirmed no `mesflow-test-*`
containers left behind.

**Verdict: TEST — PARTIAL PASS.** 240/294 collected tests pass; 54 fail on
pre-existing legacy version/UI-snapshot assertions unrelated to this
standardization; 175 deselected by marker (as configured). The Playwright
leg of `docker-test.sh` was not reached because `set -e` stops the script
at the first failing step (the pytest run) — this is the existing script's
own behavior, unchanged by this task.

### 8. Clean-start / idempotency test (§22)

```
./scripts/projectflow/stop-local.sh     → containers/network removed
./scripts/projectflow/deploy-local.sh   → recreated, DEPLOY LOCAL PASS (app=healthy postgres=healthy)
./scripts/projectflow/smoke.sh          → SMOKE PASS (same evidence as run 1)
./scripts/projectflow/deploy-local.sh   → run again immediately: "Container ... Running" (no re-create),
                                           DEPLOY LOCAL PASS, container count still = 1
./scripts/projectflow/stop-local.sh     → left the host clean at the end of this session
```

Idempotent by construction (plain `docker compose up -d` against unchanged
config) and verified live.

## Summary against the Definition of Done (§23)

| Item | Status |
|---|---|
| Workspace/Product manifest exists | ✅ `WORKSPACE.yaml` |
| Child project mapping is evidence-based | ✅ (assessment §1-2; `server-agent`/`ai-loop` correctly excluded) |
| Deployable Projects have `PROJECT.yaml` | ✅ all 4 |
| `PROJECT.yaml` exposes logical actions | ✅ |
| Build command works | ✅ executed, real artifact produced (MESFlow App) |
| Local deploy command works | ✅ executed, isolated, idempotent (MESFlow App) |
| Local deploy uses intended artifact | ✅ `MESFLOW_IMAGE=mesflow-app:71.0.0.5` from the build just run |
| Test command works | ⚠️ PARTIAL — runs correctly, isolated, self-cleaning; 240/294 pass, 54 pre-existing failures (see §7) |
| Smoke command works | ✅ executed, real readiness/schema evidence |
| Health check works | ✅ `/api/system/ready` verified directly and via container healthcheck |
| Status command works | ✅ executed |
| Logs command works | ✅ executed, no secrets |
| Artifact metadata discoverable | ✅ `artifacts/latest/mesflow-app.json` |
| Production is explicitly protected | ✅ see assessment §5, integration doc, every manifest's `production` block |
| ProjectFlow does not need MESFlow-specific hard-coded commands | ✅ all actions resolve through `PROJECT.yaml` |
| Local deployment was actually performed and verified | ✅ MESFlow App, twice (clean-start test) |

Deploy Agent / QA Center / ESP32 Firmware: manifests exist and `build`/`test`
commands point at their real existing engines, but were **not executed**
in this pass (see `docs/PROJECTFLOW_INTEGRATION.md` "Known limitations") —
not claimed as PASS.

## Known limitations / follow-ups

1. Deploy Agent and QA Center `local_deploy` are disabled pending an
   isolated-sandbox design equivalent to `compose.projectflow-local.yml`.
2. ESP32 firmware build/test/package were not executed (needs `arduino-cli`
   + hardware for a real cycle).
3. The 54 pre-existing failing tests in `mesflow/tests/` are legacy
   version/UI-snapshot debt (see §7) — flagged, not fixed, as it would
   require touching business/UI code or rewriting historical contract
   tests, both out of scope for this task.
4. This host's real-world role (dedicated DEV box vs. also serving
   `mesflow.net` traffic) was not resolved — see assessment §9 — the
   isolated-sandbox design in this task is deliberately safe either way.
