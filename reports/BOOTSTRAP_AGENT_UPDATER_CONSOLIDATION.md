# Bootstrap ← Deploy Agent Updater Consolidation

Consolidates Deploy Agent lifecycle ownership (install/update/rollback/
restart/status/logs) into `bootstrap/` (:8098), while the existing
`deploy-agent/updater/` service (:8099) — currently part of the live DEV →
target Agent update-push flow — is **kept running, unremoved**, per the
task's explicit instruction. Nothing in Production was touched.

```
Host/systemd
    ↓
Bootstrap :8098   <- NEW: owns install/update/rollback/restart/status/logs
    ↓
Deploy Agent :8090
    ↓
MESFlow / QA / application services

deploy-agent/updater/ :8099  <- UNCHANGED role, still live, hardened in place
                                 (downgrade guard + concurrency lock added)
```

==================================================
## 1. AUDIT — existing updater (`deploy-agent/updater/updater.py`)
==================================================

**Endpoints** (before this task; all preserved):
- `GET /updater/health` — no auth, liveness only.
- `GET /updater/status` — bearer auth; current `AGENT_IMAGE`/`SERVER_ROLE`/`MESFLOW_BUILD_ENABLED`.
- `POST /updater/update` — bearer auth; body = raw `AGENT_UPDATE_<version>.zip` bytes, `Content-Type: application/zip`.

**Authentication:** single shared-secret bearer token, read from
`updater/.env`'s `MESFLOW_AGENT_UPDATER_TOKEN` (or the env var of the same
name), compared with `hmac.compare_digest`. No session, no CSRF — the
bearer token is the entire auth+anti-forgery story, appropriate for a
machine-to-machine endpoint.

**Package format:** `AGENT_UPDATE_<version>.zip` → exactly one top-level
directory containing `agent-release.json` (manifest: `type`, `version`,
`image`, `image_id`, `bundle`) + `checksums.txt` + the image `.tar` named by
`bundle`. Built by `deploy-agent/scripts/build-agent-release.sh`.

**Checksum verification:** every line in `checksums.txt` is verified against
the actual extracted bytes (`hashlib.sha256`); any mismatch raises before
anything is touched. Unsafe zip paths (`..`, absolute) are rejected before
extraction.

**Version validation (found missing — added in this task):** the live
service had **no** downgrade check at all; any manifest version was
accepted. Added `version_key()`/`_installed_version_hint()` +
`DOWNGRADE_REJECTED` guard, default-on, overridable per-call via
`X-MESFlow-Allow-Downgrade: 1` (additive, backward-compatible — absent
header = old behavior's implicit safe default, not a new failure mode for
existing callers, which only ever push newer versions anyway).

**Downgrade protection:** now present (see above). Compares the manifest's
version against the tag portion of the currently recorded `AGENT_IMAGE` —
zero extra I/O, so it doesn't disturb the tested health-poll call sequence.

**Staging:** extract to a `tempfile.TemporaryDirectory()`, verify fully,
`docker load -i <tar>`, then verify the loaded image's **id** (not tag) via
`docker image inspect --format {{.Id}}` against the manifest's declared
`image_id` — never trusts the tag alone.

**Install mechanism:** `docker compose --env-file <ENV_FILE> -f <files> up
-d --no-build --force-recreate mesflow-deploy-agent` — always `--no-build`,
always scoped to exactly that one service name. Never touches
mesflow-app/postgres/qa-center/nginx (asserted by
`tests/test_updater.py::_assert_never_touched_other_services`, and by the
source-contract test `test_p1_deployment_platform.py::test_agent_updater_contract_has_staged_digest_health_and_rollback`).

**Restart mechanism:** the same `compose up --force-recreate` call is the
only restart primitive; no separate `docker restart`.

**Rollback:** on `compose up` failure or a failed post-update health poll,
`_rollback()` re-applies the previous `AGENT_IMAGE` (recorded before
mutation) via the same scoped compose call, then polls health again
(matching `server_role`, since the exact previous version string isn't
retained — only its image ref). Returns `ROLLED_BACK` or `ROLLBACK_FAILED`.

**Health verification:** polls `GET http://<bind>:<port>/agent/health` every
2s up to `HEALTH_POLL_TIMEOUT` (default 60s), requiring **both**
`agent_version == expected` **and** `server_role == expected`.

**DEV → remote target update flow:** `deploy-agent/agent.py`:
`POST /api/release-manager/update-agent` (login+CSRF; `PRODUCTION` also
requires `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` on the DEV Agent **and**
an explicit `{"confirm":true}` on every call) → `start_agent_update(role)`
(DEV-side `threading.Lock`, distinct from the target-side lock added in
this task) → background thread `_run_agent_update(role)` →
`_agent_updater_target(role)` reads
`MESFLOW_{PRODUCTION_TEST,PRODUCTION}_AGENT_UPDATER_URL/TOKEN` →
`_push_agent_update()` POSTs the latest built artifact
(`_latest_agent_release()`) to `{url}/updater/update` with
`Authorization: Bearer {token}`. Job status lands in
`state["agent_update_job"]`, surfaced in the Release Manager's "Agent
Update" tab (`templates/release/_agent_update_tab.html`, auto-polls every
3s) and recorded into deployment history.

**Persisted state:** `updater/.env` (bearer token, target dir, compose file
list, env file path — root-only, `chmod 600`); `updater/state/updater.log`
(plain append log); the compose-managed `ENV_FILE` (`AGENT_IMAGE`,
`SERVER_ROLE`, ...). **Found missing — added in this task:**
`update.lock` (new, `STATE_DIR/update.lock`, `fcntl.flock`).

**Security assumptions:** trusted network path or TLS-terminated in front
(plain HTTP + bearer token, `127.0.0.1`-bound by default — SSH tunnel or a
private network is assumed for cross-host use, per the historical live
update evidence below). Token never logged. **Found missing — added in
this task:** no protection against two concurrent `/updater/update` calls
racing each other's `docker load`/`.env` writes/`compose up` (the handler
is a `ThreadingHTTPServer`) — fixed with the update lock.

**Historical evidence this flow works for real:**
`reports/AGENT_VERSION_COMPATIBILITY_AND_SAFE_UPDATES.md` records a real,
live DEV → TEST update executed through exactly this path (2.16.10 →
2.19.0, health-verified, rollback-verified via `tests/test_updater.py`,
data preserved) — evidence the underlying mechanism this task reuses is
sound, though it does not by itself satisfy this task's new
Bootstrap-specific migration gate (see §8 below).

### CALLERS FOUND (dependency map)

| File | Role |
|---|---|
| `deploy-agent/updater/updater.py` | the service itself (:8099) |
| `deploy-agent/updater/install-updater.sh` | one-time SSH bootstrap of that service (systemd unit, token, layout detection) |
| `deploy-agent/agent.py` (`_agent_updater_target`, `_push_agent_update`, `start_agent_update`, `_run_agent_update`, `POST /api/release-manager/update-agent`, `row["updater_configured"]`) | DEV-side caller / push initiator |
| `deploy-agent/docker/compose.linux.yml` | passes the 4 `MESFLOW_{PRODUCTION_TEST,PRODUCTION}_AGENT_UPDATER_URL/TOKEN` env vars into the DEV Agent container |
| `deploy-agent/templates/release/_agent_update_tab.html`, `templates/release/index.html` | DEV-side UI (Release Manager → Agent Update tab) |
| `deploy-agent/agent_backend/fleet.py` (comment only) | notes this is a separate bearer-token protocol from fleet's own |
| `deploy-agent/tests/test_updater.py` | pure-logic tests of `updater.py` |
| `deploy-agent/tests/test_p1_deployment_platform.py` | source-contract test asserting specific safety strings exist in `updater.py` |
| `reports/AGENT_VERSION_COMPATIBILITY_AND_SAFE_UPDATES.md` | historical real-host execution evidence (see above) |
| `reports/RELEASE_DEPLOY_UX_CLEANUP.md`, `reports/P1_DEPLOYMENT_PLATFORM.md`, `reports/BUILD_ONCE_LOCAL_ARCHITECTURE.md` | docs mentioning the flow, no functional dependency |

**False positives excluded after inspection:** `deploy-agent/test_gateway_2127.py`/
`test_gateway_2128.py` (`test_standalone_gateway_updater`,
`test_updater_uses_sni_resolve`) are about the **nginx/gateway** self-update
script (`deploy-agent/installer/update-gateway.sh`), an unrelated concern —
not the Agent updater. `.reconcile/`, `tmp/reconcile/`, and
`tmp/agent-package-2.14.1/` hits are historical snapshot/package copies,
not live source.

==================================================
## 2–4. Bootstrap now owns Deploy Agent lifecycle
==================================================

`bootstrap/app.py` does **not** re-implement the update/rollback state
machine. `bootstrap/install.sh` vendors an **unmodified copy** of
`deploy-agent/updater/updater.py` into
`/opt/mesflow-bootstrap/agent_updater_core.py`; `agent_updater_core()`
loads it via `importlib` and overrides only its config attributes
(`TARGET_DIR`, `COMPOSE_FILES`, `ENV_FILE`, `STATE_DIR`, `LOG_FILE`,
`HEALTH_POLL_TIMEOUT`) to point at this host's real Deploy Agent — the same
override technique `deploy-agent/tests/test_updater.py` itself already uses
to test the file in isolation. Layout detection
(`_agent_compose_layout()`) mirrors `install-updater.sh`'s own bash logic
(single `compose.yml` vs legacy `docker/compose.linux.yml` +
`compose.bootstrap.override.yml`); Bootstrap keeps its **own** env file
(`/var/lib/mesflow-bootstrap/agent-updater.env`) rather than writing into
Deploy Agent's tree.

New capability, mapped to routes:

| Capability | Route(s) |
|---|---|
| Install Agent | `GET/POST /install-agent` (unchanged from the prior task — first-install/source-rebuild package) |
| Update Agent | `GET/POST /agent/update` (new — `AGENT_UPDATE_<version>.zip`, human upload) |
| Rollback Agent | `POST /agent/rollback` (new, confirm-gated) |
| Start/Restart Agent | `POST /docker/container/mesflow-deploy-agent/{start,restart}` (existing, reused, already allowlisted to just this container) |
| Agent status | Overview's Deploy Agent card (installed/version/runtime/health) |
| Agent logs | `GET /agent/logs` (new — Bootstrap's update log + `docker logs --tail 200`) |
| Agent diagnosis | Overview card surfaces `docker inspect --format {{.State.Error}}` (Docker's own recorded failure reason — deliberately not a live port scan; see `[[deploy-agent-incident-recovery-console]]`'s documented blind spot where a live listener scan misses a bridge-network container's real bind failure) |

**Remote update endpoint** (task §3), wire-compatible with the retiring
:8099 contract on purpose: `GET /updater/health` (no auth),
`GET /updater/status` (bearer), `POST /updater/update` (bearer, raw ZIP
body, optional `X-MESFlow-Allow-Downgrade` header) — same path, same
header, same body format, so `deploy-agent/agent.py`'s `_push_agent_update`
needs **zero code change** to target Bootstrap; only the configured
`..._AGENT_UPDATER_URL` value's port changes, when the gate below is met.
Never exposes arbitrary package execution — the body is always the
verified-then-loaded artifact, never a shell command.

**Update flow implemented exactly as specified:** receive → validate
(structure/unsafe-path) → verify SHA (checksums.txt, all files) → verify
version (downgrade guard) → stage (tempdir) → preserve
`/var/lib/mesflow-deploy-agent` (never referenced/written by this path at
all) → install/recreate (`compose up --no-build --force-recreate`, scoped
service) → poll `:8090/agent/health` → verify expected version (**and**
role) → `SUCCESS`. Failure path: `compose up` failure or failed health →
Bootstrap process itself never stops (`do_update`/`agent_do_update` run
in-request, not as a supervising process) → automatic rollback to the
previous image → restart via the same scoped compose call → re-poll health
→ `ROLLED_BACK` (or `ROLLBACK_FAILED` if that also doesn't come up).

==================================================
## 5. DEV caller
==================================================

**No code change needed or made to `agent.py`'s update-push mechanism** —
`_agent_updater_target()` already reads the target URL/token purely from
env vars with no hardcoded default, so "point DEV at Bootstrap" is
operationally just changing `MESFLOW_{PRODUCTION_TEST,PRODUCTION}_AGENT_UPDATER_URL`
from `http://<target>:8099` to `http://<target>:8098` once the gate below
passes — no credential change, same env var names, same secret preserved
(`MESFLOW_AGENT_UPDATER_TOKEN` can be copied byte-for-byte into Bootstrap's
`/etc/mesflow-bootstrap-secrets.env` at install time via
`MESFLOW_AGENT_UPDATER_TOKEN=<value> sudo ./install.sh`). Updated only
**comments** in `agent.py` (`release_manager_update_agent` docstring) and
`compose.linux.yml` (env var block) documenting this — no behavior change.

==================================================
## 6. Bootstrap UI
==================================================

Overview's Deploy Agent card now shows: installed/version/status(healthy),
last container error (if any), and buttons **Open Agent · Update · Logs ·
Restart**, plus a collapsed **Advanced → Rollback** (disabled until
Bootstrap has recorded a previous image, i.e. after its first Update run).
When Deploy Agent is absent: a single **Install Deploy Agent** button, per
spec.

==================================================
## 7. FAILURE TESTS
==================================================

Two layers, run this session (all against isolated scratch dirs + mocked
`subprocess.run` — no real Docker container was started, stopped, or
mutated, per the standing "never let a spawned test process touch a real
container" rule):

**`deploy-agent/tests/test_updater.py`** (12 tests, the vendored logic
itself — 8 pre-existing + 4 added this task):
valid update ✅ · image-id mismatch rejected before cutover ✅ · failed
health → rollback to previous image ✅ · rollback with no previous image →
`ROLLBACK_FAILED` ✅ · tampered checksum rejected ✅ · missing
manifest/unsafe zip path rejected ✅ · **downgrade rejected before any
mutation** ✅ (new) · **downgrade allowed with explicit override** ✅ (new)
· **same version is not treated as a downgrade** ✅ (new) · **concurrent
update rejected, then succeeds once the lock is released** ✅ (new).

**`bootstrap/tests/test_agent_lifecycle.py`** (13 tests, Bootstrap's wiring
only — vendored-core loading, config override, env-file bootstrap,
previous-image persistence, and the HTTP layer end-to-end via
`app.test_client()`): core loads and points at this host ✅ · missing
vendor file raises an actionable (not 500) error ✅ · successful update
persists previous image for rollback ✅ · downgrade rejected by default ✅ ·
concurrent update rejected ✅ · bad ZIP rejected ✅ · checksum mismatch
rejected ✅ · rollback with no previous image → `ROLLBACK_FAILED` ✅ ·
rollback after a recorded update → `ROLLED_BACK` ✅ · `/updater/health`
needs no auth ✅ · `/updater/status` requires bearer token (401 without) ✅ ·
full `/updater/update` round-trip over HTTP with a valid token → `SUCCESS`
✅ · wrong token → 401 ✅.

Also re-verified live (not mocked): Bootstrap boots and `/health` responds
with Deploy Agent absent (Bootstrap remains available while Agent is
stopped/missing); `/updater/health` reachable with no auth; `/updater/status`
401s with no token; full setup→login→Overview render shows the new Deploy
Agent card and Install button; `/agent/update` and `/agent/logs` pages
render. All 12 (updater) + 1 (source-contract) + 13 (bootstrap) = **26
tests pass**, plus the live boot smoke check.

**Not executed this session** (need a real second host — install failure
against a real Docker daemon, a real bad-SHA upload through the browser,
and the two real-target tests gating retirement below):

==================================================
## 8. MIGRATION GATE — result: NOT MET, 8099 not touched
==================================================

- Bootstrap update tests PASS — ✅ (mocked, this session; see §7)
- real DEV update PASS — ❌ not run (no second host available in this
  session; historical evidence in
  `reports/AGENT_VERSION_COMPATIBILITY_AND_SAFE_UPDATES.md` shows the
  *underlying* :8099 mechanism worked live before, but Bootstrap's own
  :8098 endpoint has not itself been exercised from a real DEV Agent)
- real Production Test target update PASS — ❌ not run
- rollback test PASS — ✅ mocked only; ❌ not run against a real container
- Bootstrap remains healthy throughout — ✅ demonstrated in mocked/live
  smoke tests this session, ❌ not demonstrated under a real update

Because the gate is not met, **`deploy-agent/updater/` (:8099) was left
completely untouched and running** — no removal, no disabling, no
`install-updater.sh` changes beyond none. This satisfies the task's "DO NOT
remove it first" instruction directly.

==================================================
## 9. RETIRE UPDATER — not performed
==================================================

Explicitly skipped: the gate in §8 is not met. No service was removed or
disabled, no port dependency removed, no "obsolete" code deleted (none of
`updater.py` is obsolete yet — it's still the load-bearing, live
DEV-push receiver, now also the *source* Bootstrap vendors from). The
stale-reference search below is provided for when retirement is eventually
performed, not acted on now.

### STALE REFERENCES (for the future retirement pass, not acted on now)

All current `8099`/`MESFLOW_AGENT_UPDATER_*` references are still live and
correct as of this task (see dependency map in §1). None are stale yet.
When retirement actually happens later, expect to touch: `deploy-agent/agent.py`
(comments already point at this report), `deploy-agent/docker/compose.linux.yml`
(comments already point at this report), `deploy-agent/updater/install-updater.sh`
(would be deleted/archived), `deploy-agent/updater/updater.py` (would be
deleted/archived, but only after confirming `bootstrap/agent_updater_core.py`'s
vendored copy is self-sufficient), and any real DEV/Production-Test host's
`MESFLOW_*_AGENT_UPDATER_URL` value (an infrastructure config change outside
this repo, not something this task can perform).

==================================================
## Files changed
==================================================

- `deploy-agent/updater/updater.py` — added downgrade guard + update lock
  (hardening; both applicable to the still-live :8099 service too), version
  bump 1.0.0 → 1.1.0.
- `deploy-agent/tests/test_updater.py` — 4 new tests for the above.
- `deploy-agent/agent.py` — comment-only update to `release_manager_update_agent`'s
  docstring (no behavior change; confirmed via `git diff` that this is the
  only hunk touched in an otherwise pre-existing, unrelated dirty working
  tree in this sibling repo).
- `deploy-agent/docker/compose.linux.yml` — comment-only update to the
  updater env var block (no behavior change).
- `bootstrap/app.py` — Deploy Agent lifecycle capability (§2–4 above);
  `BOOTSTRAP_VERSION` 1.0.0 → 1.1.0.
- `bootstrap/install.sh` — vendors `agent_updater_core.py`; adds
  `/etc/mesflow-bootstrap-secrets.env` (chmod 600) for
  `MESFLOW_AGENT_UPDATER_TOKEN`; prints migration status.
- `bootstrap/templates/agent_update.html`, `agent_logs.html` (new);
  `overview.html` (Deploy Agent card upgraded).
- `bootstrap/tests/test_agent_lifecycle.py` (new, 13 tests).
- `bootstrap/AGENTS.md`, `bootstrap/README.md`, `bootstrap/VERSION.txt` —
  updated for the new capability and the migration gate.

==================================================
## REPORT
==================================================

```
UPDATER ENDPOINTS AUDITED: GET /updater/health, GET /updater/status, POST /updater/update
CALLERS FOUND: deploy-agent/agent.py (_agent_updater_target/_push_agent_update/
  start_agent_update/_run_agent_update/POST /api/release-manager/update-agent),
  deploy-agent/docker/compose.linux.yml, deploy-agent/updater/install-updater.sh,
  deploy-agent/templates/release/_agent_update_tab.html,
  deploy-agent/tests/test_updater.py, deploy-agent/tests/test_p1_deployment_platform.py

BOOTSTRAP PARITY: YES (mocked/unit-tested this session; real-host not yet proven)
INSTALL: reused unchanged (deploy-agent/package_installer.sh installer package via /install-agent)
UPDATE: reused vendored deploy-agent/updater/updater.py logic (unmodified) via /agent/update
  and POST /updater/update (bearer, wire-compatible with :8099)
ROLLBACK: reused vendored _rollback(); Overview -> Advanced -> Rollback (confirm-gated)
START/RESTART: reused existing scoped docker_container_action (mesflow-deploy-agent only)
HEALTH VERIFY: reused vendored poll_health() (agent_version + server_role match)

DEV UPDATE TEST: NOT RUN (no second host in this session)
PRODUCTION TEST UPDATE: NOT RUN (no second host in this session)
ROLLBACK TEST: PASS (mocked, deploy-agent/tests/test_updater.py + bootstrap/tests/test_agent_lifecycle.py); NOT RUN against a real container

8099 STILL REQUIRED: YES
8099 RETIRED: NO -- migration gate not met (see section 8); left fully installed, running, untouched

STALE REFERENCES: none found -- all current :8099/MESFLOW_AGENT_UPDATER_* references are still
  live and correct; see "for the future retirement pass" list in section 9

PRODUCTION TOUCHED: NO
```
