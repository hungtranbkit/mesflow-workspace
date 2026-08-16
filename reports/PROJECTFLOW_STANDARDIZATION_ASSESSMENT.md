# ProjectFlow Standardization — Assessment (Scan Phase)

Date: 2026-08-15
Scope: `/home/dell/workspace/mesflow` (workspace root). Evidence-based only — no
path below was guessed; every path was verified to exist before being cited.

## 1. Repository roots (evidence)

| Root | Git repo? | Purpose | Evidence |
|---|---|---|---|
| `mesflow/` | yes (`mesflow/.git`) | MESFlow core web/backend/PostgreSQL application | `mesflow/app/`, `mesflow/compose.yml`, `mesflow/VERSION.txt` |
| `deploy-agent/` | yes (`deploy-agent/.git`) | Deploy Agent (upload/validate/deploy/verify/rollback for MESFlow + QA) | `deploy-agent/agent.py`, `deploy-agent/docker/`, `deploy-agent/VERSION.txt` |
| `qa-center/` | yes (`qa-center/.git`) | Independent QA / soak / regression runner | `qa-center/current/agent.py`, `qa-center/compose.yml`, `qa-center/current/VERSION` |
| `esp-kiosk/` | yes (`esp-kiosk/.git`) | ESP32-S3 kiosk firmware + device UI | `esp-kiosk/esp/esp.ino`, `esp-kiosk/scripts/build.sh` |
| `server-agent/` | no | **Docs-only placeholder.** Contains only `AGENTS.md` (201 bytes), no source, no build/test/deploy script, no VERSION file. | `ls server-agent/` → single file |
| `ai-loop` / `ai-reviewer` | — | **Not present.** No directory named `ai-loop`, `ai_loop`, or `ai-review*` exists anywhere under the workspace root. | `find` returned nothing |
| `docs/`, `artifacts/`, `reports/`, `test-data/`, `scripts/`, `config/`, `prompts/` | no | Workspace-level shared docs/build-output/tooling, not independent projects | directory listing |

`server-agent/` and `ai-loop` are excluded from the Project/Component
classification below per the task's evidence rule (§2/§18: "Không hard-code
ví dụ nếu repository thực tế khác" / "Chỉ include project có evidence thực
tế").

## 2. Classification

All four have independent version files, independent build scripts,
independent artifacts and independent deploy targets → **Project**, not
Component:

| Project | Version evidence | Build evidence | Artifact evidence | Deploy evidence |
|---|---|---|---|---|
| MESFlow App | `mesflow/VERSION.txt` = `71.0.0.5` | `mesflow/scripts/build-release.sh` | `mesflow-app:<ver>` image + `artifacts/releases/<ver>/*.deploy.zip` | `mesflow/compose.yml` → `/opt/mesflow`, via Deploy Agent |
| Deploy Agent | `deploy-agent/VERSION.txt` = `2.23.14-docker-runtime` | `deploy-agent/scripts/build-agent-release.sh` | `mesflow-deploy-agent:<ver>` image | `deploy-agent/docker/compose.linux.yml` → `/opt/mesflow-agent` |
| QA Center | `qa-center/current/VERSION` = `1.20.0` | `qa-center/scripts/build-release.sh` | `mesflow-qa-center:<ver>` image | `qa-center/compose.yml` → `/opt/mesflow-qa-center` |
| ESP32 Firmware | `esp-kiosk/package.json` (`esp-kiosk` fw described inline; per-release `CHANGELOG_v*.md`, latest `v5.2.0`) | `esp-kiosk/scripts/build.sh` (arduino-cli) | `esp-kiosk/scripts/build-ota-package.sh` → `artifacts/esp-kiosk/ota/*.bin` + OTA zip | `esp-kiosk/scripts/flash.sh <port>` (physical device, no server deploy) |

`server-agent/` stays undeclared (no PROJECT.yaml) until it gets real
source/build/deploy evidence — creating a manifest for it now would violate
§18's evidence rule.

## 3. Existing build/release architecture (Build Once / Promote Same Artifact)

Already implemented and must be **preserved, not replaced** (`mesflow/AGENTS.md`
Rules 1–8, `docs/operations/BUILD_AND_PROMOTE.md`):

```
scripts/build-release.sh (root wrapper)
  → mesflow/scripts/build-release.sh
  → docker build (immutable, once-per-version guard, tag-contamination guard)
  → artifacts/releases/<version>/{release.json,PROMOTION.json,checksums.txt,*.deploy.zip,image-info.json,BUILD_REPORT.md}
  → scripts/deploy-local.sh          (drives the LOCAL Deploy Agent HTTP API, --no-build)
  → scripts/promote-test.sh          (uploads the SAME zip, --no-build on target)
  → Release Manager "Promote Production" (human-click only; this Agent build returns 501, wiring only)
```

Same pattern, independently, for QA Center (`qa-center/scripts/build-release.sh`
→ `artifacts/qa-center/releases/<version>/`) and Deploy Agent itself
(`deploy-agent/scripts/build-agent-release.sh` → `artifacts/deploy-agent/releases/<version>/`).

## 4. Compose files (evidence, workspace-tracked only — `tmp/`, `.reconcile/`,
`deploy-agent/docker/runtime/`, `.venv/` excluded as generated/backup data)

| File | Role |
|---|---|
| `mesflow/compose.yml` | **Deployment-target** compose for MESFlow (`container_name: mesflow-app`/`mesflow-postgres`, external network `mesflow-edge`, bind-mounts `/opt/mesflow`-style `./runtime/*`) |
| `mesflow/compose.local.yaml` | Tiny override (cookie-secure off, port re-publish) — layered on top of `compose.yml`, not standalone |
| `mesflow/compose.test.yml` | **Standalone, fully isolated** test stack (`name: mesflow-test`; own `Dockerfile`/`Dockerfile.test`/`Dockerfile.playwright` build; tmpfs Postgres; no host port bound) — already the correct pattern for safe local automation |
| `mesflow/compose.bootstrap.yml` | First-run bootstrap variant |
| `mesflow/gateway/compose.yml` | Gateway/nginx compose |
| `qa-center/compose.yml` | **Deployment-target** compose for QA Center (`container_name: mesflow-qa-center`, external `mesflow-edge`) |
| `deploy-agent/docker/compose.linux.yml` + overrides | **Deployment-target** compose for the Agent itself (`container_name: mesflow-deploy-agent`, `SERVER_ROLE`, mounts `/opt/mesflow`, `/opt/mesflow-qa-center`, `/var/run/docker.sock`) |

## 5. ⚠️ Critical finding — this host is not a clean "DEV LOCAL" sandbox

`docker ps` at scan time shows all three deployment-target stacks **already
running live** on this exact machine, under their real names:

```
mesflow-deploy-agent   mesflow-deploy-agent:2.23.14   healthy   127.0.0.1:8090
mesflow-app            mesflow-app:71.0.0.4           healthy   127.0.0.1:8080
mesflow-postgres       postgres:17-alpine             healthy
mesflow-qa-center      mesflow-qa-center:1.19.13      healthy   127.0.0.1:8095
mesflow-nginx          nginx:1.28-alpine               healthy   0.0.0.0:80, 0.0.0.0:443
```

And:
- `/opt/mesflow/.env` has `MESFLOW_ENV=production`.
- `mesflow/nginx/nginx.conf` (the config this `mesflow-nginx` container is
  running) has `server_name mesflow.net;` / `agent.mesflow.net;`, and the
  container publishes `0.0.0.0:80`/`0.0.0.0:443` — reachable from any
  interface, not just loopback.
- The running Deploy Agent has `SERVER_ROLE=DEV`, `MESFLOW_BUILD_ENABLED=1`
  (per `deploy-agent/docker/compose.dev.override.yml`), i.e. it is the
  documented **DEV LOCAL** Agent — and per `docs/operations/BUILD_AND_PROMOTE.md`
  its `deploy-local` action targets `/opt/mesflow` on this same box, which is
  what's currently running as `mesflow-app`/`mesflow-postgres`/`mesflow-nginx`.

In other words: on this specific host, the architecture's own "DEV LOCAL"
tier and the container set actually reachable at `mesflow.net`/production
ports **are the same running containers**, driven by the same live Deploy
Agent (memory: *"Shared Docker daemon test risk — spawned 'throwaway'
deploy-agent test processes can mutate real containers"* — this is exactly
that risk, structurally, not hypothetically).

**Decision for this task:** the existing `scripts/deploy-local.sh`,
`scripts/promote-test.sh`, and the live Agent at `127.0.0.1:8090` are
**not invoked** during this standardization. Per the task's own §8/§9
requirement ("Local deploy có namespace/container/project name riêng để
tránh đụng production"), the ProjectFlow `local_deploy` action is
implemented as a **new, fully isolated sandbox** (distinct compose project
name, container names, ports, and bind-mount directories — see
`mesflow/compose.projectflow-local.yml`) that cannot collide with
`mesflow-app`/`mesflow-postgres`/`mesflow-qa-center`/`mesflow-deploy-agent`/
`mesflow-nginx` no matter what this host's real-world role turns out to be.
This preserves the existing Build Once/Promote architecture unmodified
(nothing about `scripts/build-release.sh`, `scripts/deploy-local.sh`, or the
Deploy Agent was changed) while giving ProjectFlow a safe, idempotent local
lifecycle to drive.

## 6. Test commands (evidence)

| Command | What it does |
|---|---|
| `mesflow/scripts/test/docker-test.sh` | Isolated: `docker compose -f compose.test.yml up --build -d postgres-test mesflow-test-api` → `run --rm tests` (pytest, `pytest.ini` markers: unit/behavior/integration/postgres/static/slow) → `run --rm playwright`; self-cleans (`down -v --remove-orphans` in a trap) |
| `deploy-agent/scripts/test-baseline.sh` | `py_compile` + `pytest -q` + source-ZIP verification, in a scratch `mktemp -d` sandbox |
| `qa-center` | `current/tests/` (pytest, incl. `version_contract.py`), `playwright.config.ts` |
| `esp-kiosk` | `npm test` → `playwright test tests/ui/esp-ui-visual.spec.js` |

## 7. Health/version endpoints (evidence)

| Service | Endpoint |
|---|---|
| MESFlow App | `GET /api/system/health`, `/api/system/ready`, `/api/system/version` (`mesflow/compose.yml` healthcheck uses `/api/system/ready`) |
| Deploy Agent | `GET /health` (`agent.py:5646`) |
| QA Center | `GET /api/version` (`qa-center/compose.yml` healthcheck) |

## 8. VERSION files (evidence, workspace-tracked only)

```
mesflow/VERSION.txt          71.0.0.5   (ahead of the currently-deployed 71.0.0.4 — safe to build)
deploy-agent/VERSION.txt     2.23.14-docker-runtime
qa-center/current/VERSION    1.20.0
esp-kiosk/TUTORIAL_VERSION.txt  5.1.9.2  (tutorial-content version, not firmware version — see §2 note)
```

## 9. Known limitations of this scan

- `server-agent/` and any `ai-loop`-style project are intentionally left
  without a `PROJECT.yaml` — no build/test/deploy evidence exists yet.
- `deploy-agent/docker/runtime/`, `.reconcile/`, `tmp/`, `.venv/` were
  excluded from the compose/file inventory as generated or backup data, per
  `mesflow/AGENTS.md` Rule 8.
- This assessment does not determine with certainty whether this host is
  literally the internet-facing `mesflow.net` production server or a
  DEV box that happens to also expose nginx publicly; §5 treats it as
  "possibly production" and designs around that uncertainty rather than
  resolving it, since resolving it wrongly is the higher-risk error.
