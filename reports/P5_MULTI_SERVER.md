# P5 — Multi-server (Fleet Control Plane)

Date: 2026-08-14
Deploy Agent version: 2.23.8-docker-runtime → 2.23.9-docker-runtime (source tree only; see Safety section)
Scope: `deploy-agent/agent_backend/fleet.py` (new, 368 lines: `ServerRegistryService`, `FleetHealthService`,
`classify_health`, `RemoteCallResult`), wired into `agent.py` (server registry + fleet-health background
loop + 12 new `/api/servers*`/`/api/fleet/summary`/`/api/releases` routes + `_deploy_release_to_server` +
`_production_mutation_approved` + loopback safety guards), plus a new "Servers / Fleet" tab in
`templates/ops.html`.

Reused, not rebuilt (spec section 9: "use the project's existing secure communication mechanism if
already available"): the project's existing Agent-to-Agent session+CSRF client (`_remote_agent_client`,
`_remote_agent_get_json`, `_remote_agent_upload`, `_remote_agent_deploy` — the same code
`scripts/promote-test.sh` has used since before this task), `_agent_compatibility`/`AGENT_CAPABILITIES`
for version/capability discovery, the `_db_audit` structured audit trail from P4, and the
`incidents.json`/`notifications.json` JSON-file-store convention. The pre-existing two fixed
env-var-configured targets (`MESFLOW_PRODUCTION_TEST_AGENT_URL/USER/PASSWORD`,
`MESFLOW_PRODUCTION_AGENT_URL/USER/PASSWORD`) keep working completely unmodified alongside the new
registry — this task generalizes that pattern into an arbitrary, persisted, per-server credential store
rather than replacing it.

---

## Summary

| Area | Result |
|---|---|
| Server Registry (register/handshake/disable/enable/revoke) | PASS |
| Registration status vs. health status kept distinct | PASS |
| Credential redaction on every read path | PASS (bug found & fixed this task) |
| Production requires explicit confirmation to register | PASS |
| Duplicate agent-identity rejected | PASS |
| Fleet health polling — one failure isolated from the rest | PASS |
| Vertical slice 1 — TEST registration + health (real remote agent) | PASS |
| Vertical slice 2 — Remote TEST deployment (routing/authorization/digest self-check) | PASS |
| Vertical slice 3 — Remote backup (real pg_dump round trip via a real second Agent) | PASS |
| Vertical slice 4 — PRODUCTION registered read-only (health/storage/incidents/backups readable, mutations 403) | PASS |
| Central fleet-wide Active Incidents aggregation | PASS |
| Loopback deploy/backup guard (same-host target refused by default) | PASS (added after a real incident — see Safety Incident) |
| Real end-to-end remote deploy execution (upload → remote `start_deploy()` → running container) | **NOT exercised in automated tests** (see "What was not tested" — deliberate, safety-driven) |
| Real production containers mutated by any test in this task | **YES, once, by accident — fully disclosed below** |
| `agent_id` collision bug (all same-build agents shared one identity) | FIXED (found this task) |
| Decorator-placement bug (`/api/status` silently mis-routed) | FIXED (found this task, self-inflicted) |

---

## Architecture

**`ServerRegistryService`** (`agent_backend/fleet.py`) — one JSON-file-backed store (`servers.json`,
matching the `incidents.json` convention), keyed by an opaque `server_id` (`"srv-" + uuid4().hex[:16]`,
never derived from hostname/IP, so identity survives a hostname change for what is genuinely the same
host). Two states are deliberately kept separate (spec section 11): **registration status**
(`PENDING → ACTIVE`, plus `DISABLED`/`UNREACHABLE`/`REVOKED`) tracks whether an operator has vouched for
and successfully handshaken with a server; **health status** (`ONLINE`/`DEGRADED`/`OFFLINE`/`UNKNOWN`)
tracks live reachability, set only by the poll loop. A server is never marked healthy before a real
handshake has happened — registering only ever produces `PENDING`.

Two guards are structural, not just validated: `ProductionConfirmationRequired` (registering/promoting a
server to `PRODUCTION` without an explicit `production_confirmed: true` in the request is rejected before
any record is written) and `DuplicateAgentIdentity` (a handshake reporting an `agent_id` already claimed
by a different, still-active server is rejected — one physical Agent process can never silently end up
represented by two unrelated registry entries).

**Credential redaction**: every read path (`list()`, `get()`, and every mutation's return value) passes
through `self._redacted()`, which strips `agent_password`. A separate, explicitly-named `get_raw()` exists
only for the one legitimate internal use — resolving the credential to make the actual outbound HTTP call.

**`FleetHealthService`** — a bounded, per-server poll via an injected `poll_fn` callable (kept decoupled
from Flask/urllib for pure unit-testability). One server's exception or timeout is caught per-iteration and
converted to a normalized `RemoteCallResult(ok=False, error_code=...)`; it can never prevent the rest of
the fleet from being polled or block `fleet_summary()`'s counts. `classify_health(last_seen_iso)` is a pure
heartbeat-freshness function (`≤90s → ONLINE`, `≤300s → DEGRADED`, else `OFFLINE`, unit-tested at the exact
boundary values).

**Remote calls** are normalized into six error codes, never a raw exception string as the primary UI
signal: `REMOTE_AGENT_UNREACHABLE`, `REMOTE_AUTH_FAILED`, `REMOTE_TIMEOUT`,
`REMOTE_CAPABILITY_UNSUPPORTED`, `REMOTE_OPERATION_FAILED`, `REMOTE_VERSION_INCOMPATIBLE`.

**Deploy routing** (`_deploy_release_to_server`, agent.py): routes through a *registered server_id*, never
a raw host/IP from the request. Authorization order is: component check → server exists → enabled/
registration-status → environment-specific gate (PRODUCTION needs `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1`
env var **and** `confirm: true` in the request body; TEST proceeds without either) → same-host safety
guard (`LOOPBACK_DEPLOY_REFUSED`, see Safety Incident) → deploy lock for that server+component → local
artifact resolve + sha256 self-check → remote session + compatibility check → upload → digest readback via
the remote's own `/api/releases`. Every authorization refusal returns before any credential is resolved or
remote call attempted.

**Backup routing** (`api_server_backup_create`) mirrors the same shape: production-approval gate, then a
matching `LOOPBACK_BACKUP_REFUSED` guard, then local-vs-remote branching (`_db_backup_service.create()`
locally, a real HTTP round trip to `/api/ops/db-backups` for a remote server), with
`REMOTE_BACKUP_STARTED/COMPLETED/FAILED` written to the audit trail either way.

**Fleet-wide incident aggregation** (`/api/fleet/summary`): for every enabled registered server, reads
that server's own `/api/incidents?status=ACTIVE` (or the local file directly for `server_id=="local"`) and
returns a combined `active_incidents` list, each item tagged with `server_id`/`server_name`/`environment`.
This is a live federation (an on-demand fan-out read), not a single merged incident store — each server
remains the source of truth for its own incidents; DEV never writes to a remote server's incident file.

---

## Multi-server assumptions removed

| Single-server assumption (before P5) | What replaced it |
|---|---|
| Exactly two fixed remote targets, configured only via `MESFLOW_PRODUCTION_TEST_AGENT_URL`/`MESFLOW_PRODUCTION_AGENT_URL` env vars (`_production_test_target()`/`_production_target()`, agent.py:923-933) | Arbitrary number of registered servers, each with its own persisted credential, addressable by `server_id` |
| `SERVER_ROLE`/`environment_label()` (P3) assumed exactly one environment for the whole running process | A registry entry's `environment` (`DEV`/`TEST`/`PRODUCTION`/`OTHER`) is independent per *target*, not per *process* — DEV can hold TEST and PRODUCTION entries simultaneously |
| `_load_incidents()` / `db_audit.json` / `db_backups.json` implicitly meant "this machine's own" data | Same local files remain authoritative for local data; new `server_id`-scoped routes (`/api/servers/<id>/incidents`, `/health`, `/storage`, `/backups`) let DEV read any *registered* server's equivalent data on demand |
| No concept of "this server is PRODUCTION, treat it differently" anywhere in the registry/routing layer | `environment == "PRODUCTION"` is a first-class registry field that gates every mutation (deploy, backup-create) behind explicit env-var + per-request confirmation, while leaving all reads unrestricted |
| Agent identity had no genuine unique field — `/api/status` exposed only `agent_version`, shared by any two same-build agents | Persisted `agent_instance_id` (`"agent-" + secrets.token_hex(16)`, generated once, stored in `CONFIG_FILE`), exposed as `agent_id` in `/api/status`, enforced unique per active registry entry via `DuplicateAgentIdentity` |
| No fleet-wide view — health/incidents/storage/backups were each a single-server dashboard tile | Fleet Summary card (servers/online/degraded/offline/production/active-incidents counts) + a fleet-wide Active Incidents panel, both driven by `/api/fleet/summary` |
| Deploy/backup targets were implicitly trusted local infrastructure — no concept that "the target" could be a different, less-trusted machine | Registry `agent_url`/`agent_user`/`agent_password` per server, explicit production-approval gate, and (found the hard way — see Safety Incident) an explicit same-host refusal so "remote" can never silently mean "this same Docker daemon" |

---

## Real bugs found and fixed while building this

1. **Credential leak through `list()`/`get()`** — `ServerRegistryService.list()` and `.get()` originally
   returned raw records, including `agent_password`, to any caller (including the Fleet UI's own list
   response). Caught by a purpose-written unit test
   (`test_credential_never_leaks_through_get_or_list`), which failed on first run. Fixed by routing both
   through the existing `_redacted()` helper; a new `get_raw()` was added for the one legitimate internal
   caller (the code that actually opens the remote HTTP session).
2. **Agent-identity collision** — `/api/status` had no genuinely unique per-instance field;
   `record_handshake()`'s fallback (`agent_id or agent_version`) meant any two real agents on the same
   software build collided under `DuplicateAgentIdentity` the moment a second one was registered — caught
   live while seeding the Playwright screenshot fixtures (`DuplicateAgentIdentity: agent_id
   '2.23.9-docker-runtime' is already claimed by server 'srv-...'`). Fixed with a persisted
   `agent_instance_id` generated once in `ensure_config()` and exposed via `/api/status`; regression-tested
   in `tests/test_p5_fleet_routes.py::test_two_real_agents_same_version_get_distinct_identities` (two real
   spawned `agent.py` processes, same build, must hand back two different `agent_id`s).
3. **Self-inflicted decorator-placement bug** while fixing (2) — an edit inserted a new helper function
   between `@app.get("/api/status")` and its target function, silently re-routing the decorator onto the
   wrong function and breaking every downstream JSON parse of `/api/status`. Caught immediately by the
   same regression test failing with `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`; fixed by
   moving the helper to a separate, correct location.
4. **Deploy/backup status-code misclassification** — `api_server_deploy`'s exception handler originally
   mapped every non-`ALREADY_RUNNING` `_RemoteAgentError` to a blanket `502`, so a client-side authorization
   refusal (`PRODUCTION_DEPLOY_NOT_APPROVED`, `LOOPBACK_DEPLOY_REFUSED`) that never even attempted a remote
   call incorrectly returned `502 Bad Gateway` instead of `403 Forbidden`. Fixed with explicit substring
   classification (`ALREADY_RUNNING→409`, `NOT_FOUND→404`, `NOT_APPROVED|REFUSED|NOT_DEPLOYABLE|
   UNSUPPORTED_→403`, else `502`); three test assertions tightened from tolerant `(403, 502)` to strict.
5. **Check-ordering bug** — the loopback guard was initially placed *before* the production-approval gate
   in `_deploy_release_to_server`, so `test_production_deploy_blocked_without_approval` (which necessarily
   uses a loopback target, since all test fixtures run on this host) always hit `LOOPBACK_DEPLOY_REFUSED`
   first and never actually exercised the production gate. Fixed by reordering: authorization first, the
   loopback guard last (immediately before credential resolution).

---

## Safety Incident (full disclosure)

While building and testing vertical slice 2 (remote deployment), an early version of the deploy test
called the real MESFlow `/upload` endpoint against a spawned "throwaway" second `agent.py` process, using
the real, locally-built `71.0.0.4` release artifact. That endpoint **always** auto-triggers a real local
deploy job — this is existing, correct, unchanged behavior of the Agent. The problem: the spawned
"throwaway" process runs on the **same host** and shares the **same Docker daemon** as the real production
containers. Docker container names are global on a daemon, not namespaced per Agent process — the
release's own `compose.yml` names its container `mesflow-app` regardless of which Agent triggered the
deploy. The result: the real `mesflow-app` production container was stopped (SIGKILL, confirmed via
`docker inspect` showing `Status=exited ExitCode=137`) for roughly 20 minutes before this was noticed
(during an unrelated `docker inspect mesflow-app` check) and fixed.

A closely related incident happened on the same test run, before either fix existed: a spawned remote
agent's `MESFLOW_POSTGRES_CONTAINER` was left unset, which defaulted to the real container name
`mesflow-postgres` — producing a real, complete `pg_dump` (1.3 MB, real `db_revision:
"0037_v72_audit_operations_separation"`, a real migration revision) of the production database.

**Immediate remediation:**
- `mesflow-app`: restarted immediately (`docker start mesflow-app`), confirmed `Health=healthy` via
  `docker exec mesflow-nginx curl mesflow-app:8080/` returning `302`, full 5-container safety audit
  performed.
- The accidental production `pg_dump` file was `shred -u`'d immediately; the entire pytest tmp tree that
  had touched it was purged.

**Permanent fixes (code, not just test discipline):**
1. `LOOPBACK_DEPLOY_REFUSED` in `_deploy_release_to_server()` — refuses any deploy whose target
   `agent_url` hostname resolves to `127.0.0.1`/`localhost`/`::1`, unless the operator explicitly sets
   `MESFLOW_ALLOW_LOOPBACK_DEPLOY=1`.
2. `LOOPBACK_BACKUP_REFUSED` in `api_server_backup_create()` — the same pattern for remote backup
   creation, overridable only via `MESFLOW_ALLOW_LOOPBACK_BACKUP=1`.
3. `tests/conftest.py`'s `spawn_agent()` now defaults every spawned test process's
   `MESFLOW_POSTGRES_CONTAINER` to the literal nonexistent placeholder `p5-test-no-postgres-configured`,
   so any test that forgets to override it fails closed rather than silently reaching real infrastructure.
4. A persistent memory file (`deploy-agent-shared-docker-daemon-test-risk.md`) documents the incident and
   the checklist for any future test that lets a spawned Agent execute real deploy/container logic.
5. `tests/test_p5_deploy_backup_slices.py` was rewritten with a module-level SAFETY NOTE and the dangerous
   test replaced by `test_deploy_to_loopback_target_is_refused_by_the_safety_guard`, which asserts the
   guard fires (`403` + `LOOPBACK_DEPLOY_REFUSED`) and that no `REMOTE_DEPLOY_STARTED` audit entry was
   ever written — plus an explicit `assert os.environ.get("MESFLOW_ALLOW_LOOPBACK_DEPLOY") is None` as a
   standing safety assertion.

**What was not tested, as a direct consequence:** the real remote-upload → remote `start_deploy()` →
running-container execution path is **not exercised end-to-end by any automated test** after this fix,
because doing so on this shared-host sandbox is exactly the dangerous pattern that caused the incident.
What *is* tested end-to-end: the local artifact resolve + sha256 self-check (real, against the real
`71.0.0.4` artifact, no remote call), the loopback refusal itself, and — separately — a full real digest
readback contract exists in `_deploy_release_to_server` (upload → `GET /api/releases` on the remote →
compare `sha256`) that is exercised in the exact same shape by the pre-existing, long-standing
`scripts/promote-test.sh` path in production use, but not by a *new* P5 automated test against a
second real host. This is a deliberate, disclosed scope boundary, not an oversight — verifying it further
would require genuinely separate hosts or non-colliding container names, which this environment does not
have.

**Production containers, confirmed after all P5 work (including the second full baseline re-run and the
Playwright screenshot capture):**

```
mesflow-app:            running, health=healthy
mesflow-postgres:       running
mesflow-deploy-agent:   healthy
mesflow-nginx:          healthy
mesflow-qa-center:      healthy
```

---

## Vertical slices (tested, in spec priority order)

### 1. TEST registration + health — PASS
A real second `agent.py` process is spawned (`tests/conftest.py::spawn_agent`), registered via
`POST /api/servers` with `environment: TEST`, then `POST /api/servers/<id>/test-connection` performs a
real HTTP handshake (session login + CSRF + `GET /api/status`), moving `registration_status` from
`PENDING` to `ACTIVE` and recording the real `agent_id`/`agent_version`/capabilities. `FleetHealthService
.poll_once()` then classifies it `ONLINE`. Covered in `test_p5_fleet_routes.py::
test_register_and_handshake_real_remote_test_agent` and the Fleet UI screenshot (below).

### 2. Remote TEST deployment — PASS (routing/authorization real; execution guarded, see Safety Incident)
`POST /api/servers/<id>/deploy` for a TEST-registered server proceeds without any production flag;
`_artifact_for_release()` resolves the real, locally-built `71.0.0.4` package and its sha256 is verified
against the manifest before any remote call is attempted. Actual remote upload to a loopback target is
refused by the safety guard (proven in `test_deploy_to_loopback_target_is_refused_by_the_safety_guard`),
matching the safety-driven scope boundary above.

### 3. Remote backup — PASS
`tests/test_p5_deploy_backup_slices.py::test_remote_backup_full_lifecycle`: a real second `agent.py`
process with a real throwaway `postgres:17-alpine` container behind it is registered as a TEST server;
`POST /api/servers/<id>/backups` performs a real HTTP round trip to that remote's own
`/api/ops/db-backups`, which runs a real `pg_dump -Fc` against the throwaway database. The response comes
back `status: SUCCESS`, `verification_status: VERIFIED`, with a real `sha256`; DEV's own
`GET /api/servers/<id>/backups` lists it back, and `REMOTE_BACKUP_STARTED`/`REMOTE_BACKUP_COMPLETED` both
appear in DEV's audit trail. `test_remote_backup_routes_to_correct_server_only` confirms a second,
postgres-less remote server never receives or reflects that backup.

### 4. PRODUCTION registered, read-only — PASS
`test_p5_deploy_backup_slices.py::test_production_server_read_only_paths_all_work`: a server registered
with `environment: PRODUCTION` (requires `production_confirmed: true` to register at all) successfully
handshakes, and its health/storage/incidents/backup-inventory all return `200` normally — registering as
PRODUCTION does not mean inaccessible. The same server's `deploy` and `backups` (create) routes both
return `403` (`PRODUCTION_DEPLOY_NOT_APPROVED` / `PRODUCTION_BACKUP_NOT_APPROVED`) without
`MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` and `confirm: true` — proven in
`test_production_deploy_blocked_without_approval` and `test_production_backup_blocked_without_approval`.
Screenshot evidence: `reports/screenshots/p5/production-readonly-detail.png` — a real PRODUCTION-tagged
server's drawer showing live Health/Storage/Backups/Incidents, with no mutation controls present in that
view at all.

---

## Production: read-only vs. approval-gated

| Operation | PRODUCTION-registered server behavior |
|---|---|
| Register | Requires `production_confirmed: true` in the request, or `ProductionConfirmationRequired` is raised before any record is written |
| Test connection / handshake | Allowed — read-only, required to reach `ACTIVE` |
| Health / Storage / Incidents / Backup inventory (read) | Allowed unconditionally — `200` for any registered, enabled server regardless of environment |
| Deploy | **Blocked** (`403 PRODUCTION_DEPLOY_NOT_APPROVED`) unless the Agent process has `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` set **and** the request includes `confirm: true` |
| Backup (create) | **Blocked** (`403 PRODUCTION_BACKUP_NOT_APPROVED`) under the same two-part gate |
| Restore drill / retention apply (P4 mutations, routed via server) | Not implemented as remote operations in this task — remain local-only (see Scope discipline) |

No test in this task set `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1`; every PRODUCTION-path test in the suite
proves the *blocked* state, never a successful production mutation.

---

## Security confirmations

```
NO UNAUTHENTICATED REMOTE AGENT MANAGEMENT   CONFIRMED — every remote call opens a real session via
                                              _remote_agent_client (username+password login, CSRF token),
                                              the exact mechanism scripts/promote-test.sh has always used;
                                              no bearer-token-only or unauthenticated path was added
NO ARBITRARY REMOTE SHELL                    CONFIRMED — this task adds no remote command-execution route;
                                              all remote operations are the pre-existing, fixed set
                                              (/api/status, /upload, /api/releases, /api/ops/db-backups,
                                              /api/ops/storage, /api/incidents) — never an arbitrary path
                                              or shell string from the request
NO REQUEST-SUPPLIED ENVIRONMENT OVERRIDES    CONFIRMED — a server's `environment` (DEV/TEST/PRODUCTION)
                                              is read only from the REGISTRY record, never from the
                                              request body; proven directly by
                                              test_test_environment_deploy_never_requires_production_flags
                                              (a TEST-registered server ignores {"environment":"production"}
                                              in the request body and proceeds without the production gate)
NO SAME-HOST DEPLOY/BACKUP WITHOUT EXPLICIT OPT-IN   CONFIRMED — LOOPBACK_DEPLOY_REFUSED /
                                              LOOPBACK_BACKUP_REFUSED (added after the incident above)
CREDENTIALS NEVER LEAK THROUGH A READ PATH   CONFIRMED (after the fix in bug #1 above) —
                                              test_credential_never_leaks_through_get_or_list
```

---

## Deployment digest-match confirmation

`_deploy_release_to_server()`'s digest contract: local artifact resolved via `_artifact_for_release()`,
hashed with `sha256()`, compared against the release manifest's own recorded `package_sha256` as a
pre-flight self-check (this succeeds independent of any remote call — verified directly in
`test_deploy_artifact_self_check_uses_real_release_digest` against the real `71.0.0.4` artifact). The
second half of the contract — uploading, then reading back the remote's own `/api/releases` entry and
comparing `sha256` — is implemented and reuses the identical pattern the existing
`scripts/promote-test.sh`/PRODUCTION_TEST promotion path has always used, but per the Safety Incident
above, was **not exercised against a second real host by a new automated P5 test** in this sandbox. This
is stated plainly rather than implied as fully covered.

---

## UI evidence (1920×1080, full-page, zero console/page errors)

Captured against a real, locally-served DEV control-plane instance with two real spawned remote `agent.py`
processes registered and handshaken (one as TEST, one as a clearly-simulated PRODUCTION — never the real
`mesflow-deploy-agent` container), via Playwright (`{"consoleErrors": [], "pageErrors": []}` on every
capture).

- `reports/screenshots/p5/fleet-overview.png` — Servers / Fleet tab: Fleet Summary (3 servers, 3 online,
  0 degraded/offline, 1 production, 2 active incidents), the fleet-wide Active Incidents panel, the
  server-registration form, and the 3-row server table (local DEV, `mesflow-prod` PRODUCTION, `mesflow-test`
  TEST — all ACTIVE/ONLINE).
- `reports/screenshots/p5/test-server-detail.png` — `mesflow-test` drawer: TEST/ACTIVE/ONLINE badges,
  real `/api/status` JSON (agent_id, capabilities), Storage (3.5 GB / 7.4 GB · 46.9%), Backups, and a real
  aggregated Incident ("QA Center unreachable", HIGH) — all four panels populated from real remote calls.
- `reports/screenshots/p5/production-readonly-detail.png` — `mesflow-prod` drawer: same four panels,
  PRODUCTION badge, no mutation controls present in this read-only view.
- `reports/screenshots/p5/central-active-alerts.png` — the fleet-wide Active Incidents panel showing both
  `mesflow-prod` (PRODUCTION) and `mesflow-test` (TEST) each independently reporting "QA Center
  unreachable" (HIGH), tagged with server name and environment — proving central, cross-server alert
  visibility from one place.
- `reports/screenshots/p5/multiserver-health-storage-backup.png` — the same TEST-server drawer confirming
  Health + Storage + Backups + Incidents render together for a single remote server in one view.
- `reports/screenshots/p5/release-target-server.png` — the Release & Deploy page: Deployment Platform
  (image digest, schema revision), Build & Release Manager, and the legacy Target Agents panel (LOCAL /
  PRODUCTION TEST / PRODUCTION slots) — confirming the pre-existing single-target release view keeps
  working unmodified alongside the new fleet registry.

---

## Tests

```
$ .venv/bin/python -m pytest tests/test_p5_fleet_unit.py -v          # ServerRegistryService/
18 passed                                                             # FleetHealthService/classify_health,
                                                                       # pure logic, no HTTP/Docker

$ .venv/bin/python -m pytest tests/test_p5_fleet_incidents.py -v     # fleet incident tagging/aggregation
3 passed                                                              # (in-process, local server only)

$ .venv/bin/python -m pytest tests/test_p5_fleet_routes.py -v        # registry routes, real remote agent,
13 passed                                                             # auth-failure/isolation/duplicate-ID

$ .venv/bin/python -m pytest tests/test_p5_deploy_backup_slices.py -v  # vertical slices 2/3/4, production
10 passed                                                              # gating, safety guard

$ ./scripts/test-baseline.sh   # py_compile + full pytest -q + source package build/verify
308 passed, 8 subtests passed in 402.02s   # run 3 times total across this task (twice after the
                                             # agent-identity fix, once more after fixing an
                                             # accidental screenshot-in-source-zip mistake below),
                                             # all three clean, 0 failures
{"file_count": 117, "filename": "mesflow-deploy-agent-source-2.23.9-docker-runtime.zip",
 "sha256": "69fd288e4b4ca169b61de853c295726bd08308030c8dd5effe651ad380db2791",
 "size": 314611, "status": "PASS", "version": "2.23.9-docker-runtime"}
```

**Packaging bug found and fixed while preparing this report** (unrelated to the code, a documentation-step
mistake): the P5 screenshots were first saved to `deploy-agent/reports/screenshots/p5/` — *inside* the
scanned source tree — instead of the correct `mesflow/reports/screenshots/p5/` (sibling to `deploy-agent/`,
matching the P3/P4 convention). `tools/build_source_package.py`'s `EXCLUDED_DIRS` does not exclude
`reports/`, so the next baseline run silently packaged six ~200-250KB PNGs into the "source" ZIP
(`file_count` 117→123, `size` 314KB→1.9MB) — a real supply-chain hygiene issue (shipping build artifacts
inside a source package) caught by comparing this run's `file_count`/`size` against P4's own baseline
before writing this report, not by any dedicated test. Fixed by moving the screenshots to the correct
location and deleting the accidental `deploy-agent/reports/` directory; a fourth full baseline run (numbers
above) confirms the source ZIP is back to exactly 117 files / ~314KB, matching the expected +6-file delta
(only the six new P5 Python files) over P4's 111.

44 new P5 tests added (18 unit + 3 incident-tagging + 13 route + 10 vertical-slice/safety), zero
pre-existing tests broken. All spawned-process tests use isolated `WORKSHOP_AGENT_HOME` temp directories,
loopback-refused-by-default deploy/backup paths, and (after the incident) a safe nonexistent placeholder
Postgres container name by default — never `mesflow-app`/`mesflow-postgres` by name, except by the one
disclosed accident above, which is now structurally guarded against.

---

## Files changed

New: `agent_backend/fleet.py`, `tests/conftest.py`, `tests/test_p5_fleet_unit.py`,
`tests/test_p5_fleet_incidents.py`, `tests/test_p5_fleet_routes.py`,
`tests/test_p5_deploy_backup_slices.py`, `reports/screenshots/p5/*.png`.

Modified: `agent.py` (fleet wiring, server registry routes, `_deploy_release_to_server`,
`_production_mutation_approved`, loopback safety guards, `agent_instance_id` persistence, configurable
Waitress thread pool via `WORKSHOP_AGENT_THREADS`), `templates/ops.html` (new "Servers / Fleet" tab +
fleet-wide Active Incidents panel + ~150 lines of JS), `VERSION.txt`/`README.md`/`docker/Dockerfile`/
`docker/compose.linux.yml`/`docker/compose.windows.yml`/`docs/DEPLOY_DOCKER.md` (version bump, all 7
locations verified synchronized).

---

## Scope discipline

**Built** (all 4 required vertical slices): server registry with distinct registration/health states,
production-confirmation and duplicate-identity guards, credential redaction, fleet health polling with
per-server failure isolation, server-routed deploy (authorization + local digest self-check; execution
guarded off by design — see Safety Incident), server-routed real remote backup (full real `pg_dump` round
trip), server-scoped storage/incidents/backup reads, PRODUCTION read-only-by-default with explicit
two-part approval for the two mutation routes, fleet-wide Active-Incidents aggregation, a Fleet Overview
UI with per-server detail drawers.

**Explicitly deferred, not built**: remote restore-drill and remote retention-apply (P4's mutations stay
local-only in this task — the server-scoped read routes for backups exist, but triggering a *drill* or
*retention* on a remote server was not added; the same production-approval + loopback-guard pattern would
extend to them directly, but adding two more real-mutation remote code paths without equally careful
per-path safety testing was judged out of scope given the incident above); a UI control to add/edit a
server's role list or credentials after registration (currently register-once, disable/enable/revoke only);
automatic re-polling interval configuration from the UI (currently `FLEET_POLL_SECONDS` env-configured);
end-to-end verification of the real remote-deploy execution path against a genuinely separate host (would
require infrastructure this sandbox does not have — see Safety Incident).

## Safety

```
PRODUCTION READ-ONLY BY DEFAULT       CONFIRMED — every PRODUCTION-registered server's health/storage/
                                       incidents/backup-inventory reads succeed unconditionally; both
                                       mutation routes (deploy, backup-create) require
                                       MESFLOW_PRODUCTION_PROMOTE_ENABLED=1 (env, operator-set) AND
                                       confirm:true (per-request) — neither was set by any test in this task
NO UNAPPROVED PRODUCTION MUTATION     CONFIRMED for all automated tests in this task's final state — every
                                       PRODUCTION-path test proves the BLOCKED state, never a successful
                                       mutation. NOT true of one earlier manual test run before the safety
                                       guards existed — see Safety Incident above for full disclosure of
                                       the one accidental production container stop and accidental
                                       production pg_dump, both remediated, both now structurally guarded
NO AUTOMATIC PRODUCTION RESTORE       CONFIRMED — this task adds no remote restore-drill route at all
NO ARBITRARY FILE DELETE              CONFIRMED — no new file-delete code path was added in this task
```

**Transparency note (same pattern as every report this session):** unlike P3/P4, this task's own testing
process DID cause one real, disclosed production incident (see "Safety Incident" above) — a ~20 minute
`mesflow-app` outage and one accidental production database dump, both caught and remediated within the
same working session, both now prevented by permanent code guards rather than relying on test discipline
alone. `mesflow-postgres`, `mesflow-app`, `mesflow-deploy-agent`, `mesflow-nginx`, and `mesflow-qa-center`
were all confirmed `running`/`healthy` at the end of this task, including after the second full baseline
re-run and the Playwright screenshot capture. This task's own new code (source version
`2.23.9-docker-runtime`) has **not** been deployed anywhere — it exists only in this working tree and was
verified through isolated local test instances and throwaway processes/containers, all of which have been
stopped, removed, or (in the one accidental case) securely shredded.
