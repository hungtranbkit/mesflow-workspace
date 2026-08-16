# System Log / Business Audit Separation

Date: 2026-08-14
MESFlow version: 71.0.0.1 → 71.0.0.3 (source tree only; see PRODUCTION DEPLOYED note below)
Deploy Agent version: 2.20.0-docker-runtime → 2.21.0-docker-runtime (source tree only, not deployed by this work)
Migration: `0037_v72_audit_operations_separation` (single Alembic head, applied cleanly in isolated test DB only)

Scope: MESFlow (`~/workspace/mesflow/mesflow`) and Deploy Agent (`~/workspace/mesflow/deploy-agent`), per AGENTS.md rules (no production mutation, no secrets in logs, no destructive Docker commands).

**Update (same day, follow-up request):** after this report was first written, the user asked to move the "System Health" tab (MESFlow's own Phase 1 health dashboard) over to Deploy Agent as well, so it stops duplicating Deploy Agent's Operations Center. Confirmed by explicit user choice: **only** System Health moves (becomes a link-out, like Operations Center); "Nhật ký nghiệp vụ" (Business Audit) stays exactly as-is in MESFlow, on its own data. See the updated OPERATIONS CENTER section below for what changed.

**Update 2 (same day, "monitoring ownership cutover" follow-up):** the "known reconciliation gap" flagged in LEGACY DATA PRESERVED below is now closed on the write side — MESFlow's legacy V69 health writer is off by default (creates zero new rows across all 8 legacy tables) while the tables/read APIs stay fully intact for history. "System Health" and "Operations Center" were further removed from MESFlow's menu entirely (not just linked out) since Deploy Agent's Operations Center is now the sole place to view them. MESFlow's "Nhật ký hệ thống" page was renamed to "Nhật ký ứng dụng" (it was always application-level HTTP tracing, not infrastructure logs — "Nhật ký hệ thống" now belongs to Deploy Agent's tab exclusively). Full detail, evidence, and exact test/Playwright results: `reports/MONITORING_OWNERSHIP_CUTOVER.md`.

---

## EXISTING LOG SOURCES

Audited before any change. Each source classified; nothing was moved until its classification was understood.

**BUSINESS_AUDIT:**
- `audit_logs` table (`mesflow.db.repositories.analytics.AuditRepository`) — PO/Part/Operation changes, work_session start/finish/cancel/correction, quantity/defect/rework corrections, exception Resolve/Ignore, manual corrections, employee/admin actions. Fields already include actor_user_id, employee_id, correlation_id, before_json/after_json, source (added in a prior V66 migration). Already the correct home for this data — kept, extended, never rewritten.
- `notifications` table — in-app business notifications (session/exception/PO events), `UNIQUE(source_type,source_id)`.

**SECURITY_AUDIT:**
- Login/session events. Previously **not recorded anywhere** — `/api/auth/login` failures and successes were silently unrecorded. This was the one real gap found in this classification step; closed by adding `LOGIN_SUCCESS`/`LOGIN_FAILED` rows to `audit_logs` (never the submitted password; failure reason distinguishes `inactive` vs `invalid_credentials`).
- Role/permission changes, user activation/deactivation — already recorded via existing `audit_logs` writes in the users/roles management code paths (unchanged).

**SYSTEM_LOG:**
- `action_logs` / `error_traces` tables (`mesflow.web.action_logging`) — technical HTTP request tracing (method, path, status, duration, `g.trace_id`). Already separate from `audit_logs`; already rendered on MESFlow's existing "Nhật ký hệ thống" (System Logs) page, gated by the pre-existing `logs.view` permission. Left as-is — this is legitimately MESFlow-side technical tracing of its own web layer (request-level, not infrastructure-level), distinct from Deploy Agent's server/Docker/deploy logs, and section 20 forbids unrelated refactoring.
- Deploy Agent `append_log()` → `AGENT_HOME/data/logs/*.log` — Agent-internal action log (deploy/build/upload actions taken through the Agent). Already Deploy-Agent-owned; unaffected.

**DEPLOY_LOG:**
- Deploy Agent's release/deploy state JSON (`load_state()`/`save_state()` job records: `job`, `qa_job`, `release_build_job`, `promote_test_job`, `agent_update_job`, etc.) and `RELEASES_DIR`/`agent_manifest.json`/`PROMOTION.json`/`release_gate` evidence. Already Deploy-Agent-owned; unaffected.

**HEALTH_EVENT / INCIDENT / DIAGNOSTIC (the actual conflict found):**
- `component_health_state`, `component_health_history`, `scheduled_job_health` (migration `0033_v69_system_health`)
- `health_alerts` (migration `0034_v69b_health_alerts`)
- `notification_deliveries`, `health_diagnostics_snapshots` (migration `0035_v69c_notifications_diagnostics`)
- `health_metric_samples`, `predictive_insights`, `ai_incident_analyses` (migration `0036_v69f_predictive`)

These were built into **MESFlow's own PostgreSQL** during this same working session's earlier Phase 1/2/3 tasks, before the current task's ownership rule ("MESFlow owns BUSINESS AUDIT, Deploy Agent owns SYSTEM/INFRASTRUCTURE OPERATIONS") was given. They are HEALTH_EVENT/INCIDENT/DIAGNOSTIC by content, not BUSINESS_AUDIT — a direct conflict with this task's architecture rule. See **LEGACY DATA PRESERVED** below for the resolution taken (not deleted; superseded going forward).

**UNKNOWN:** none left unclassified. Every log/audit/event source found maps to one of the above.

---

## MOVED/ROUTED TO DEPLOY AGENT

Nothing was moved out of an existing store (no destructive migration). Instead, new SYSTEM/INFRASTRUCTURE telemetry is now **created going forward** directly on Deploy Agent (JSON-file-backed, no database), which was previously missing:

- **New Incident model** — `deploy-agent/agent.py`: `INCIDENTS_FILE` (`AGENT_HOME/config/incidents.json`), a background poller (`_incident_monitor_loop`, default 30s via `MESFLOW_INCIDENT_POLL_SECONDS`) that evaluates `_incident_conditions()` (MESFLOW_DOWN, QA_DOWN, CONTAINER_DOWN/UNHEALTHY scoped to an explicit `EXPECTED_CONTAINERS` allowlist, DISK_CRITICAL, RAM_CRITICAL) and reconciles them via `sync_incidents()`.
- New read/write API: `GET /api/incidents` (list, `?status=` filter), `GET /api/incidents/<id>` (detail), `POST /api/incidents/<id>/acknowledge`, `POST /api/incidents/<id>/resolve` — all gated by login (CSRF-protected on the two mutating routes) or the existing internal-token mechanism for service-to-service calls.
- Deploy Agent's own Operations UI (`templates/ops.html`) extended with **Cảnh báo** and **Sự cố** tabs consuming these endpoints.

## REMAINING IN MESFLOW

- All of `audit_logs`, `action_logs`, `error_traces`, `notifications` — untouched in content and untouched in schema except the additive fields already present from prior work and one new index (`idx_audit_logs_created_employee`) added in `0037`.
- Login/security audit — newly added, but as BUSINESS_AUDIT/SECURITY_AUDIT rows in MESFlow's existing `audit_logs`, per section 3 ("security/account actions belong with MESFlow").
- New dedicated **Business Audit Trail** UI page ("Nhật ký nghiệp vụ") — see MESFLOW BUSINESS AUDIT below.

## LEGACY DATA PRESERVED

`component_health_state/history`, `scheduled_job_health`, `health_alerts`, `notification_deliveries`, `health_diagnostics_snapshots`, `health_metric_samples`, `predictive_insights`, `ai_incident_analyses` remain in MESFlow's PostgreSQL **exactly as they were**. Per section 16's own migration strategy and section 20's explicit prohibitions ("do not delete existing audit records", "do not combine with unrelated refactoring"), this task did **not**:
- delete or migrate that data,
- stop MESFlow's Phase 1/2/3 health-check background job from continuing to write to it,
- rip out the MESFlow-side Health Center UI that reads it.

**Known reconciliation gap, explicitly flagged for a follow-up task:** MESFlow's Phase 1/2/3 health/incident tables and Deploy Agent's new Incident model are two independent systems observing overlapping conditions (e.g. both can independently notice MESFlow is unreachable — one from the inside via scheduled self-checks, the new one from Deploy Agent's outside vantage point). They do not share state and are not deduplicated against each other. Going forward, **Deploy Agent's Incident model is the authoritative system for SYSTEM/INFRASTRUCTURE incidents** per this task's architecture rule; MESFlow's existing tables are left running read/write (not frozen) because a live cutover of a background job was judged out of scope for "heavily read-only, Phase 1" work and risked exactly the kind of unrelated refactoring section 20 forbids. A dedicated follow-up task should decide: freeze MESFlow's health-writer job vs. keep both, and how far back to retain the legacy tables before archiving.

---

## OPERATIONS CENTER

Deploy Agent's existing `/ops` page (already had Tổng quan/Services/Docker/Ports/Logs/Terminal) extended rather than replaced, per section 9's tab list and section 19 (avoid a second unrelated UI style):

`[Tổng quan][Cảnh báo][Sự cố][Chẩn đoán][Docker][Ports][Nhật ký hệ thống][Command/SSH]`

- **Tổng quan**: unchanged — Overall Health, Server (CPU/RAM/Disk/Uptime with raw byte fields now also exposed alongside the human-formatted strings), Services (MESFlow/PostgreSQL/Deploy Agent/QA Center/nginx-gateway). No fabricated metrics — every value already came from a real `psutil`/`docker`/HTTP probe.
- **Cảnh báo** (new): ACTIVE + ACKNOWLEDGED incidents, `loadAlerts()` polling every 30s.
- **Sự cố** (new): full filterable incident history table (`loadIncidents()`, status dropdown) with a detail drawer (`openIncident(id)`) showing evidence, technical_reason, occurrence_count, and Acknowledge/Resolve actions.

MESFlow's `Hệ thống → Operations Center` menu item does **not** duplicate this: it renders a link-out page (`renderOperationsCenter()` in `app.js`) that opens Deploy Agent's real Operations Center in a new tab via `MESFLOW_OPERATIONS_CENTER_URL` (server-rendered from `settings.operations_center_url`, empty by default with a "not configured" state) — no Agent monitoring data is duplicated into MESFlow's database or rendering path, per section 12.

**Follow-up (same day):** MESFlow's own "System Health" tab (`Điều hành → System Health`) — the Phase 1 dashboard that read `component_health_state`/`health_alerts`/etc. directly out of MESFlow's own database and rendered its own Server/Docker/Services/Kiosk Fleet/Incident History view — was converted to the same link-out pattern (`app/mesflow/web/static/pages/system-health.js`: `renderSystemHealth()` now shows the "opens in Deploy Agent" / "not configured" `.empty` state instead of its own dashboard). This closes the "known reconciliation gap" flagged above at the UI layer: there is now exactly one place a user looks at infrastructure health (Deploy Agent's Operations Center), not two overlapping dashboards.

Scoped narrowly, by explicit user confirmation: only the **front-end tab** changed. The backend `/api/system-health` blueprint, its background health-check writer, and the underlying `component_health_state/history`, `health_alerts`, `notification_deliveries`, `health_diagnostics_snapshots`, `health_metric_samples`, `predictive_insights`, `ai_incident_analyses` tables were **not** touched — they keep running and keep being written to, per the LEGACY DATA PRESERVED policy above. "Nhật ký nghiệp vụ" (Business Audit) was explicitly **not** moved and is unchanged. Deciding whether to freeze the legacy health-writer job entirely remains the same open follow-up item noted in LEGACY DATA PRESERVED, now purely a backend/data-retention decision rather than a UI one.

Old test coverage for the retired dashboard (`tests/e2e/system-health-v69.spec.js`) was rewritten to assert the new link-out behavior (1920×1080, zero page/console errors) instead of the removed drawers/kiosk-fleet/incident-history UI; the backend itself is still covered unchanged by `tests/test_v69_system_health_unit.py` and `tests/integration/test_v69_system_health.py`.

## SYSTEM LOG VIEWER

Already existed on MESFlow (`action_logs`/`error_traces`, "Nhật ký hệ thống", `logs.view` permission) and on Deploy Agent (`/ops` → Nhật ký hệ thống tab, tailing bounded log files). Both were already bounded (no unlimited raw log dumps) — confirmed, not changed.

## INCIDENT HISTORY

Deploy Agent `GET /api/incidents?status=` — persisted in `incidents.json`, one row per fingerprint per open/closed cycle, structured fields per section 7: `incident_id, incident_type, severity, source, server, service, started_at, last_seen_at, resolved_at, status, summary, technical_reason, impact, evidence, acknowledged_by, resolution_reason, occurrence_count, fingerprint`. No unlimited raw container logs stored — only the structured condition snapshot at each poll.

## DEDUPLICATION

Fingerprint = condition identity (e.g. `MESFLOW_DOWN`, `CONTAINER_DOWN:mesflow-postgres`, per-service `QA_DOWN`, `DISK_CRITICAL`). `sync_incidents()`:
- new fingerprint → one ACTIVE incident, `occurrence_count=1`.
- same fingerprint still present on a later poll → same incident row, `occurrence_count` increments, `last_seen_at` refreshes — never a duplicate row.
- ACKNOWLEDGED status is preserved across polls while the condition persists (does not silently flip back to ACTIVE).

Verified by test: `test_same_condition_repeated_does_not_duplicate_but_increments_occurrences`, `test_acknowledged_incident_persists_across_polls_without_reopening_status`.

## RECOVERY DETECTION

Condition absent on a poll → incident transitions ACTIVE/ACKNOWLEDGED → **AUTO_RESOLVED**, `resolved_at` set. If the same fingerprint reappears later, it reopens as a new ACTIVE cycle (fresh `occurrence_count`, `resolved_at` cleared) rather than silently resuming the old closed record.

Verified by test: `test_condition_no_longer_present_is_auto_resolved`, `test_recurrence_after_auto_resolve_reopens_as_new_active_cycle`.

---

## MESFLOW BUSINESS AUDIT

New dedicated page **"Nhật ký nghiệp vụ"** (`app.js: renderBusinessAudit()`), separate from the existing technical "Nhật ký hệ thống" page. Filter toolbar: Time (from/to), User (actor, ILIKE), Employee, Entity type, Entity ID, Action, Search — all passed through to `AuditRepository.list()`, which was extended with `entity_id`, `actor`, `employee_id`, `date_from`, `date_to`, `correlation_id` filter params (previously only `action`/`entity_type`). The page explicitly does not surface `action_logs`/`error_traces` vocabulary — confirmed by test (`test_business_audit_never_contains_technical_action_log_rows`) that no bare `ERROR/FAILED/SLOW/SUCCESS` HTTP-tracing action appears in its results.

`/api/audit-logs` (`mesflow.web.analytics`) changed from `@login_required` to `@permission_required('business_audit.view')`.

## PERMISSIONS

New RBAC permissions seeded by `0037_v72_audit_operations_separation` (matching the exact `op.execute(sa.text(...).bindparams(...))` pattern from the existing `0025_rbac_permissions.py`):

| code | granted to (this migration) |
|---|---|
| `business_audit.view` | manager, supervisor |
| `operations.view` | manager |
| `system_logs.view` | manager |
| `diagnostics.run` | (seeded, not yet granted to any role — Phase 1 keeps diagnostics read-only-and-ungranted by default) |
| `deploy.view` | manager |
| `deploy.execute` | (seeded, not yet granted — deploy execution stays behind existing Deploy Agent login, unchanged) |

Existing `logs.view` grants (technical System Logs page) were **not** touched — a production manager can now view Business Audit without gaining server/deploy access, and vice versa, per section 13. No existing authorization was weakened; all changes are additive grants plus one new `@permission_required` gate that replaced a weaker `@login_required` gate (strictly tightening, never loosening).

## MESFLOW-DOWN TEST

Section 18's "MESFlow unavailable → Agent remains accessible → incident visible" scenario was run without ever touching the real, production-critical `mesflow-app` container. A freshly-imported, isolated Deploy Agent test instance had `mes_status()` deterministically pinned to an offline result (see AGENT STILL ACCESSIBLE below for why env-var-only unreachability wasn't sufficient on this host), then:
1. Agent's own `/api/status` (behind its own login/session, nothing to do with MESFlow) returned 200 with `mes.online == false`.
2. `_incident_conditions()` correctly produced `MESFLOW_DOWN` (`CRITICAL`).
3. `sync_incidents()` produced an `ACTIVE` incident.
4. `GET /api/incidents?status=ACTIVE` (Agent's own API) surfaced it.

No event silently disappeared at any step.

## AGENT STILL ACCESSIBLE

Confirmed structurally and by test: Deploy Agent has no dependency on MESFlow for its own login, session, or API layer — it is a fully separate Flask process/container with its own auth. During the MESFlow-down test, login and `/api/status`/`/api/incidents` all worked normally. (Note found and fixed while writing the test: Deploy Agent's `mes_status()` has a documented fallback that also probes bare `http://127.0.0.1`/`localhost` in addition to the configured MES URL — correct production behavior for containers that don't expose port 8080 to the host — which meant pointing only `WORKSHOP_MES_URL` at an unreachable address wasn't sufficient to simulate "down" on a host that also runs a real gateway on port 80; the test now pins `mes_status()` directly for a deterministic, host-independent result.)

## TESTS

**Deploy Agent** (`.venv/bin/python -m pytest tests/ -q`, isolated `WORKSHOP_AGENT_HOME` scratch dir, real Agent's own persistent state never touched): **142 passed, 0 failed.** New this task: `tests/test_v72_operations_center_incidents.py` (9 tests) — new-condition-opens-one-incident, repeat-condition-increments-not-duplicates, auto-resolve-on-recovery, reopen-on-recurrence, independent-fingerprints, acknowledged-persists, container-allowlist-excludes-unrelated-containers, evidence-never-contains-secrets, MESFlow-unreachable end-to-end scenario.

**MESFlow**, run against a fresh, fully isolated Docker Compose project (`-p mesflow-p5`, discarded after):
- This task's + prior Phase 1/2/3 test files together (`test_v69_system_health_unit.py`, `test_v69d_phase2_notifications_unit.py`, `test_v69g_phase3_predictive_unit.py`, `test_v71_ui_foundation.py`, `tests/integration/test_v69_system_health.py`, `tests/integration/test_v69d_phase2_notifications.py`, `tests/integration/test_v69g_phase3_predictive.py`, `tests/integration/test_v72_audit_operations_separation.py`): **73 passed, 0 failed.**
- New this task: `tests/integration/test_v72_audit_operations_separation.py` (6 tests) — login success/failure creates an audit row without ever recording a password, `/api/audit-logs` returns 403 for a role without the grant and 200 for manager/supervisor, action-filter and future-date-range filtering behave correctly, no technical action_log vocabulary leaks into business audit results.
- Full repo `tests/` (434 tests): **366 passed, 68 failed.** All 68 failures were inspected individually and confirmed to be **pre-existing, unrelated legacy tests** hardcoded to a historical MESFlow version string (`65.8.44.x`, superseded long before this task — current is 71.x) or to removed/replaced UI markup from that era (e.g. `newTemplateOld`, `CA HIỆN TẠI`, an old po-control module layout). None of the 68 touch any file this task modified (`analytics.py`, `app.py`, `config.py`, `app.js`, `ui.css`, `app.html`, migration `0037`). This task introduces **zero new test failures**.
- Alembic: `alembic heads` → single head `0037_v72_audit_operations_separation` (confirmed in the isolated test database).

**Follow-up (System Health tab move):** same 8-file session-relevant selection re-run against a fresh isolated stack (`-p mesflow-p6`, discarded after) after the `system-health.js`/`app.js` edit: **73 passed, 0 failed** — unchanged, since the backend `/api/system-health` API and its own unit/integration tests were not touched by a front-end-only tab change.

## PLAYWRIGHT

`tests/e2e/audit-operations-v72.spec.js`, 1920×1080, run three times across this work (twice mid-session, once against the final fresh isolated stack): **2/2 passed every time.**
1. Business Audit Trail page renders with the filter toolbar visible (`#baList`).
2. Operations Center link page renders its configured/not-configured `.empty` state.

`tests/e2e/system-health-v69.spec.js` — rewritten for the tab-move follow-up (previously tested the retired in-page dashboard's drawers/kiosk-fleet/incident-history via mocked `/api/system-health` routes; now asserts the link-out `.empty` state, matching Operations Center's pattern). Run against the same fresh `mesflow-p6` stack: **1/1 passed.**

Screenshots: `test-results/v72-business-audit.png`, `test-results/v72-operations-center-link.png`, `test-results/v69-system-health-link.png` (all reviewed — correct layout, correct copy, correct nav placement under "Điều hành" and "Hệ thống" respectively; System Health's sidebar hint now reads "Server, Docker, dịch vụ, sự cố hạ tầng (Deploy Agent)").

## PAGE ERRORS

None. `page.on('pageerror', ...)` recorded zero events across all three Playwright test files.

## CONSOLE ERRORS

None. `page.on('console', m => m.type()==='error')` recorded zero events across all three Playwright test files.

## DATABASE MIGRATION

`app/migrations/versions/0037_v72_audit_operations_separation.py`, `down_revision="0036_v69f_predictive"`. Additive only: 6 new `rbac_permissions` rows, role grants (see PERMISSIONS), one new index `idx_audit_logs_created_employee`, `system_meta.schema_version` bumped to `72.0.0.0`. No table dropped, no column dropped, no data rewritten. Applied and verified only inside the isolated `mesflow-p5` test Postgres — never against production.

## PRODUCTION DATA MUTATED: NO

Verified: `mesflow-postgres` `StartedAt=2026-08-12T04:18:08.161154558Z`, `RestartCount=0` — identical before, during, and after this entire task (including the System Health follow-up), reconfirmed at the very end. No production migration was run; `0037` was applied only inside disposable test-stack Postgres instances (`mesflow-p4`, `mesflow-p5`, `mesflow-p6`), all fully torn down afterward along with their throwaway images.

## PRODUCTION DEPLOYED: NO (by this work) — but see note

This work never ran a build or deploy against production: no `scripts/build-release.sh`, no Deploy Agent upload/promote call was made from this session. Only source-tree version declarations were bumped (`VERSION.txt`, `release.json`, `compose.yml` image tag, `AGENT_VERSION`, Agent `VERSION.txt`, `AGENT_CAPABILITIES` +`operations_incidents`), MESFlow now at `71.0.0.3`, per AGENTS.md's "every modified deployable ZIP must use a new version" rule.

**Transparency note:** partway through this session's work, real `mesflow-app` was observed to have been redeployed — by something outside this conversation, not by any command run here — from `mesflow-app:71.0.0.1` to `mesflow-app:71.0.0.2` (`StartedAt` moved from `2026-08-13T22:21:14Z` to `2026-08-13T23:09:33Z`, `RestartCount=0`, container healthy). `71.0.0.2` was a version number this session had bumped in the source tree earlier (before any code in this task's diff existed at that version), so this reads as a legitimate external deploy of a prior snapshot — most plausibly the concurrent Claude Code session the user mentioned earlier in this workspace, or a manual deploy by the user/team — not a malfunction and not data loss (`mesflow-postgres` was untouched throughout). It is flagged here only so the user has an accurate picture of what changed in their infrastructure and by whom: **not** by this task's work, and **not** an action this session took or requested.
