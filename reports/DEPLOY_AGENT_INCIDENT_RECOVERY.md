# Deploy Agent → Server Incident Recovery Console

Upgrades Deploy Agent's existing `/ops` Operations Center with a curated,
safe MESFlow-stack recovery workflow — on top of the existing generic
Docker/systemd panels, without touching deployment logic
(`deployment_platform.py`, release upload/promote/rollback code is
unchanged).

Project: `deploy-agent/`. Files changed:
- `deploy-agent/agent_backend/incident_recovery.py` (new)
- `deploy-agent/agent.py` (wiring: import, `MANAGED_SERVICES`,
  `_recovery_service`, `_recovery_audit`, 11 new routes, `protect()`
  exempt list, `ops_page()` view/page_key, `api_incident_detail()`)
- `deploy-agent/templates/ops.html` (new "Dịch vụ" tab + JS, incident
  drawer recovery block)
- `deploy-agent/templates/_operations_shell_start.html` (sidebar link)
- `deploy-agent/tests/test_incident_recovery.py` (new, pure unit)
- `deploy-agent/tests/test_recovery_routes.py` (new, Flask route-level)

Behavior changed: adds a new allowlist-only recovery surface. No existing
route, template, or deployment/release code path was modified or
removed.

Migration: none (JSON-file store, same convention as `incidents.json`/
`db_audit.json`; new file `recovery_audit.json` created on first write).

Production action required: no.

---

## MANAGED SERVICES

Implemented as `MANAGED_SERVICES` in `agent.py`, container names
env-overridable (`MESFLOW_POSTGRES_CONTAINER` — pre-existing var, reused
— `MESFLOW_APP_CONTAINER`, `MESFLOW_NGINX_CONTAINER`,
`MESFLOW_QA_CONTAINER`, new). Deploy Agent's own container is
deliberately excluded.

## ALLOWLIST

Default (matches task spec exactly):

| id | container | depends_on |
|---|---|---|
| postgres | mesflow-postgres | — |
| mesflow | mesflow-app | postgres |
| nginx | mesflow-nginx | mesflow |
| qa | mesflow-qa-center | mesflow |

Every new route (`/api/ops/recovery/services/<sid>...`) rejects a `sid`
outside this table with `404 NOT_MANAGED` **before** issuing any Docker
call — enforced server-side, not just hidden in the UI. Verified live: a
non-allowlisted `sid` never reaches `run_fn` at all
(`test_scenario_f_unrelated_container_is_rejected`,
`test_unmanaged_service_id_is_rejected_everywhere`).

## SYSTEM CHECK

`GET /api/ops/recovery/system-check` → `recovery.system_check()`.
Reuses the existing CPU/RAM/disk score bands from
`agent_backend/system_health.collect_summary` (≥90/75 CPU, ≥90/80 RAM,
≥95/85 disk — the same thresholds the existing "Sức khỏe hệ thống" tab
already uses) plus per-managed-service HEALTHY/DEGRADED/CRITICAL, rolled
up to an overall HEALTHY/DEGRADED/CRITICAL. Postgres/MESFlow down is
always CRITICAL overall; nginx/QA down is DEGRADED (not the whole stack
critical) unless something else already is.

## SERVICES PAGE

New Operations → **Dịch vụ** page (`/ops?view=recovery`), sidebar entry
added to the VẬN HÀNH group in `_operations_shell_start.html`. Table
columns exactly as specified: Service / Container / Running / Health /
Version / Uptime / Dependencies / Last error / Action. Primary actions:
Xem (View, human-readable + collapsible technical `docker inspect`
detail — raw JSON never shown by default), Log, Khởi động (Start,
`.primary` blue). Restart/Stop live under `<details><summary>Thao tác
nâng cao</summary>`, same interaction pattern as the pre-existing
Docker/Services tabs — never a primary button.

## RECOVER STACK

`[ Khôi phục MESFlow Stack ]` → `POST /api/ops/recovery/stack` →
`RecoveryOrchestrator.recover_stack()`. Preflight (Docker daemon
reachable) runs first; if Docker is unavailable every step is reported
`BLOCKED: DOCKER_UNAVAILABLE` without attempting anything. Otherwise
walks postgres → mesflow → nginx → qa in order; per service: inspect →
already healthy? skip → dependency not healthy? block → guard refuses
(role policy)? block → port conflict? fail safely → `docker start` +
bounded health-wait → verify. A non-blocking lock refuses a second
concurrent stack run (`RECOVERY_ALREADY_RUNNING`, 409).

## POSTGRES START / MESFLOW START / NGINX START / QA START

Each is `POST /api/ops/recovery/services/<id>/start`, independently
callable (task scenario E). Guarded by `SafeStartGuard.can_start()`:
allowlist membership (structural — id must exist in `MANAGED_SERVICES`),
current state must not already be healthy-running, all `depends_on`
must be healthy, and SERVER_ROLE policy (DEV: allowed; PRODUCTION_TEST:
allowed by default, `MESFLOW_RECOVERY_ALLOW_TEST_START=0` to disable;
PRODUCTION: refused with `PRODUCTION_APPROVAL_REQUIRED` unless the
request body carries `confirm_production: true` — same
confirm-dialog-then-flag shape as the existing Release & Deploy tab's
`wireProdButton()`/Promote-to-Production flow, not a new UX pattern).

## PORT CONFLICT

`check_port_conflicts()` cross-references the container's own
`HostConfig.PortBindings` (from `docker inspect`, works even when
stopped) against `agent.py`'s existing `ops_ports()` (psutil listeners)
and a best-effort PID→container map (`docker ps` + `docker inspect
--format`). On conflict the UI shows port/protocol/owner
PID/process/owner container and a "Thử lại" (retry) button — nothing is
ever stopped/killed automatically. Verified with a fake conflicting
listener (`test_scenario_c_port_conflict_fails_safely_without_killing_owner`):
zero `docker start`/`stop`/`kill` commands issued once a conflict is
detected.

**Known limitation, inherited, not introduced by this task:** this
reuses the Agent's existing `ops_ports()` psutil-based listener scan.
When Deploy Agent itself runs inside a container without host
networking (the shipped `docker/compose.linux.yml` topology), that scan
sees its own network namespace, not necessarily the same one the
Docker daemon binds host ports in — the pre-existing "Network & Ports"
tab has this exact same characteristic. A live check on this dev host
(see PLAYWRIGHT/TESTS section) reproduced this: `docker inspect`
correctly reported a *previous* real bind-failure
(`mesflow-app`'s `State.Error`: "failed to bind host port
127.0.0.1:8080/tcp: address already in use"), while a live conflict
pre-check via `ops_ports()` came back empty in this environment. Noting
this rather than hiding it.

## LOG VIEW

`GET /api/ops/recovery/services/<id>/logs` — `docker logs --tail N
<container>`, scoped to the allowlisted container only (separate from,
and stricter than, the existing unrestricted `/api/ops/logs`). Rendered
in a `<pre class="terminal">` panel on the Dịch vụ page and reused
inline in the incident drawer.

## DIAGNOSTICS

All 9 required flows implemented as pure functions in
`incident_recovery.py` (`DIAGNOSIS_KINDS`): `mesflow_unavailable`,
`postgres_unavailable`, `gateway_502`, `container_stopped`,
`container_unhealthy`, `restart_loop`, `disk_high`, `ram_high`,
`docker_unavailable`. Each returns SUMMARY / EVIDENCE / PROBABLE CAUSE /
RECOMMENDED ACTION (Vietnamese text, English evidence keys), reachable
at `GET /api/ops/recovery/diagnose/<kind>?service=<id>` and rendered on
the Dịch vụ page with one button per kind. Read-only by construction —
no subprocess call happens inside the diagnose functions themselves,
only in the orchestrator's evidence-gathering wrapper
(`run_diagnosis()`).

## INCIDENT INTEGRATION

`GET /api/incidents/<id>` now attaches `item.recovery` (computed live,
not persisted into `incidents.json`) via
`recovery.service_id_for_incident()`, which maps the exact fingerprints
`agent.py`'s existing incident monitor already emits (`MESFLOW_DOWN`,
`QA_DOWN`, `CONTAINER_DOWN:<name>`, `CONTAINER_UNHEALTHY:<name>`) to a
managed service. The incident drawer renders the recommendation text and
only the buttons the server marked safe (`[Khởi động <service>] [Xem
log] [Chẩn đoán]`), matching the task's example format. Incidents this
console has no mapping for (`DISK_CRITICAL`, `RAM_CRITICAL`) show "Không
có hành động khôi phục cho loại sự cố này" instead of a fabricated
action.

## AUDIT

`RECOVERY_AUDIT_FILE` (`recovery_audit.json`, own file — separate from
the P4 DB-domain audit) via `_recovery_audit()`, same append-only JSON
convention as `_db_audit`. Every start/restart/stop attempt — success,
block, or failure, through both the single-service and stack paths —
records `who, when, server, service, action, previous_state, result,
reason, incident_id`. No secrets recorded (only service ids/container
names/state labels/free-text reason strings). Exposed read-only at
`GET /api/ops/recovery/audit`. Verified:
`test_audit_recorded_for_every_mutation_attempt`,
`test_start_on_missing_test_container_fails_safely_not_silently`.

## UNRELATED CONTAINER PROTECTION

Structural, not just UI omission: `/api/ops/recovery/services` always
returns exactly the 4 allowlisted rows; every other new route 404s on
an unrecognized `sid` before any Docker call. Verified against a real
Docker host with several genuinely unrelated running containers present
(`portainer`, `local-news-ai-app-1`, `english-coach-v1-ollama-1`) — none
appear in `/api/ops/recovery/services`, matching scenario F. The
**pre-existing** generic Docker/Services tabs (`/api/ops/docker-action`,
`/api/ops/service-action`) are unchanged by this task — they remain
available to any logged-in operator as before, per "do not redesign
[existing] logic"; this task adds a separate, stricter surface rather
than retrofitting the old one.

## PLAYWRIGHT

Not run — no browser automation was executed. Evidence instead:
- `node --check` on the extracted inline `<script>` block from a real
  server-rendered `/ops?view=recovery` response: **PASS** (valid JS).
- Server-rendered HTML for `/ops?view=recovery` confirmed to contain
  the new section, both button labels ("Khôi phục MESFlow Stack",
  "Kiểm tra toàn hệ thống"), and the sidebar "Dịch vụ" link.
- A genuine, **read-only** smoke check against this dev host's real
  Docker daemon (see next section) — not a browser test, but real data
  through the real stack, not fakes.

## TESTS

- `tests/test_incident_recovery.py` — 19 pure unit tests (fake
  `run_fn`/listeners, no Docker, no Flask): scenarios A–H from the task
  spec, concurrency lock, PRODUCTION approval gating, audit shape, guard
  reasons, `parse_expected_ports`, incident→service mapping, unknown
  diagnosis kind, `system_check` banding. **All pass.**
- `tests/test_recovery_routes.py` — 10 Flask-route tests (real `agent.py`
  loaded in-process, container names overridden to guaranteed-nonexistent
  test names — same safety convention as the pre-existing
  `MESFLOW_POSTGRES_CONTAINER` default and `tests/conftest.py`'s
  `spawn_agent()`, so this file can never touch a real container):
  login/CSRF required, `NOT_MANAGED` on every route for an unrelated id,
  services list is exactly the 4 rows in order, a start against a
  genuinely-missing test container fails safely with exactly one audit
  entry, stack recovery returns 4 ordered steps, incident detail carries
  `.recovery`. **All pass.**
- Regression: `tests/test_p5_fleet_routes.py`, `tests/test_p5_fleet_unit.py`,
  `tests/test_it_operations_ui.py`, `tests/test_p4_ops_page.py` — **51
  passed**, no new failures.
- Full suite (`pytest tests/ -q`): **336 passed, 15 skipped**, plus 3
  pre-existing failures (`test_authoritative_versions_are_synchronized`
  and 2 others) — confirmed **unrelated to this task**: they assert
  `VERSION.txt`/`AGENT_VERSION`/`docker/compose.linux.yml`'s image tag
  stay in sync, and `git status` shows `VERSION.txt`, `docker/Dockerfile`,
  `docker/compose.linux.yml` and several other files were already
  modified/out-of-sync in this working tree before this task started
  (this task touched none of them). Not fixed here — out of scope, and
  fixing a version-bump policy gate was not requested.
- **Live, read-only smoke test against the real local Docker daemon**
  (SERVER_ROLE=DEV, real container names, zero start/stop/restart calls
  issued): `preflight()` → Docker available; `list_service_views()`
  correctly reported the real live state — postgres running/healthy
  (image `17-alpine`), nginx running/healthy (image `1.28-alpine`),
  mesflow-app genuinely stopped (correctly `can_start=True`), QA Center
  stopped and correctly `can_start=False` with
  `DEPENDENCY_NOT_READY:mesflow`; `system_check()` correctly reported
  overall `CRITICAL` with MESFlow `CRITICAL`/QA `DEGRADED`; the real
  `mesflow-app` container's `State.Error` field
  (a genuine prior bind failure: "address already in use" on
  127.0.0.1:8080) was correctly surfaced as `last_error`. No mutating
  action was run against this live host — see the port-conflict
  limitation note above for why a live start was deliberately not
  attempted.

## PRODUCTION DEPLOYED: NO
