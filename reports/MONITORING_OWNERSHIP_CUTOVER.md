# Monitoring Ownership Cutover

Date: 2026-08-14
Follow-up to `reports/SYSTEM_LOG_AUDIT_SEPARATION.md` (same architecture: Deploy Agent = authoritative SYSTEM/INFRASTRUCTURE monitoring, MESFlow = BUSINESS/SECURITY audit + application-level tracing).

MESFlow version: 71.0.0.3 → 71.0.0.4 (source tree only; see PRODUCTION DEPLOYED note)
Deploy Agent version: 2.21.0-docker-runtime → 2.21.1-docker-runtime (source tree only, not deployed by this work)
No schema migration in this task — no DDL change, only a settings flag + write-site guards. `alembic heads` still resolves to the single existing head, `0037_v72_audit_operations_separation`.

---

## OLD MESFLOW HEALTH WRITERS:

Audited every write path into the 8 legacy tables. All of them trace back to exactly two entry points:

1. **Request-driven** — `SystemHealthService.summary()` (`mesflow/services/system_health_service.py`), previously invoked on every `GET /api/system-health` (the old System Health page polled this every 15s). On each call it wrote:
   - `component_health_state` / `component_health_history` via `self.persist()`
   - `health_alerts` via `self.sync_alerts()` (fingerprint-keyed upsert/resolve)
   - `sync_alerts()` in turn triggered, only on the newly-opened/newly-resolved edge:
     - `notification_deliveries` via `NotificationDispatcher.dispatch()`
     - `health_diagnostics_snapshots` via `DiagnosticService.snapshot()`
   - `/api/system-health/alerts/<id>/ai-analysis` (GET auto-capture / POST regenerate) → `ai_incident_analyses` via `IncidentAIService._record()`
   - `/api/system-health/notification-channels/<ch>/test` → `notification_deliveries` via `NotificationDispatcher.test()`
2. **CLI-driven, but never actually scheduled** — `python -m mesflow.cli run-predictive` (`mesflow/cli.py: run_predictive()`). Checked the real running `mesflow-app` container's entrypoint script directly (read-only `docker exec`): it runs `wait-db → alembic upgrade head → verify-schema → seed-admin → seed-default-users → record-deployment → waitress-serve`. **`run-predictive` is not invoked anywhere** — no cron, no supervisor entry, nothing in the entrypoint. This command writes `health_metric_samples`, `predictive_insights`, and reports its own status into `scheduled_job_health` — currently dormant in production, but still directly callable (`docker exec mesflow-app python -m mesflow.cli run-predictive`), so it needed the same guard as everything else, not just "it happens not to run."

No component of MESFlow's kiosk heartbeat, OTA readiness, or business exception processing touches any of this — confirmed by import search (`SystemHealthService` is only referenced from `system_health.py`, `metrics_service.py`, `predictive_service.py`).

## DISABLED WRITERS:

New setting `settings.legacy_health_writer_enabled` (`MESFLOW_LEGACY_HEALTH_WRITER_ENABLED`, default `"0"` — **off**). Guarded at every actual write site (not just the route layer, so a direct API call or manual CLI invocation can't bypass it either):

| Write site | Table(s) | Guarded behavior when disabled |
|---|---|---|
| `SystemHealthService.summary()` | `component_health_state/history`, `health_alerts` | Skips `persist()`/`sync_alerts()`; still computes and returns a live status (never raises), and reads currently-open alerts via a plain `SELECT` instead of upserting |
| `DiagnosticService.snapshot()` | `health_diagnostics_snapshots` | Runs the diagnostic collection live, returns it, does not `INSERT` |
| `NotificationDispatcher.dispatch()` / `.test()` | `notification_deliveries` | Short-circuits to `[]` / `{'status':'DISABLED'}` before any send attempt or insert |
| `IncidentAIService._record()` | `ai_incident_analyses` | Returns a synthetic `status:'DISABLED'` result; the cache-read path above it (unaffected) still returns any pre-existing cached row |
| `mesflow.cli run_predictive()` | `health_metric_samples`, `predictive_insights`, `scheduled_job_health` | Prints `[PREDICTIVE] legacy health writer disabled; skipped` and returns immediately, before touching `MetricsCollector`/`PredictiveService`/the DB at all |

Existing V69/Phase2/Phase3 tests still exercise the underlying write mechanism (proving it isn't rotted, for a deliberate future rollback) by explicitly re-enabling the flag: `compose.test.yml`'s `mesflow-test-api` service sets `MESFLOW_LEGACY_HEALTH_WRITER_ENABLED: "1"`; the 4 AI-analysis unit tests that call `IncidentAIService` directly (in-process, not over HTTP) now `monkeypatch` the flag on via the same frozen-`Settings`-`dataclasses.replace()` pattern already used elsewhere in this suite.

## READINESS PRESERVED:

`/api/system/health`, `/api/system/ready`, `/api/system/monitoring` (`mesflow/web/app.py`, backed by `SystemRepository`) are a **completely separate blueprint** from the retired `/api/system-health` service — different Python module, different DB queries (schema/migration-head/connection-stats, not component health rows), never touched by this task. Verified live: `test_application_readiness_and_health_endpoints_unaffected` hits both endpoints against the real running test-api container and gets `200`/`ok:true`. Deploy Agent's own `mes_status()` polls exactly these two endpoints (plus a Docker-level fallback) to decide MESFLOW_DOWN — unaffected, still works, per its own existing test suite (142/142, unchanged this task). Kiosk heartbeat, OTA readiness, and business exception processing do not import `SystemHealthService` at all (confirmed by search) — nothing to break.

## LEGACY TABLES PRESERVED:

No `DROP`, no `TRUNCATE`, no column removed, no migration touching any of the 8 tables in this task. `test_legacy_history_stays_readable` confirms every one of `component_health_state`, `component_health_history`, `scheduled_job_health`, `health_alerts`, `notification_deliveries`, `health_diagnostics_snapshots`, `health_metric_samples`, `predictive_insights`, `ai_incident_analyses` is still a plain, working `SELECT`. Their read APIs (`/api/system-health/history`, `/predictions`, `/recurring-incidents`, `/alerts/<id>/...`) are all unchanged and still return whatever history already exists.

## NEW INFRA INCIDENTS IN MESFLOW: 0

Verified directly, not assumed: `test_summary_creates_zero_new_rows_in_any_legacy_table` calls the real `SystemHealthService().summary()` three times in a row against the live test database — including once where a component genuinely reports a non-healthy status, the exact scenario that used to open a `health_alerts` row — and asserts row counts across all 8 tables are byte-identical before and after. `test_diagnostic_snapshot_and_ai_analysis_do_not_persist` and `test_notification_dispatch_and_test_send_do_not_persist` do the same for the other four write paths. All pass.

## AGENT INCIDENT DETECTION:

Unchanged from `reports/SYSTEM_LOG_AUDIT_SEPARATION.md` — Deploy Agent's Incident model (`incidents.json`, fingerprint dedup, ACTIVE/ACKNOWLEDGED/RESOLVED/AUTO_RESOLVED lifecycle) remains the sole authoritative system for SYSTEM/INFRASTRUCTURE incidents going forward. Deploy Agent's Operations Center (`Tổng quan/Cảnh báo/Sự cố/Chẩn đoán/Docker/Ports/Nhật ký hệ thống/Command-SSH`) is untouched functionally this task (only its CSS was polished — see below). Re-verified: Deploy Agent's own 142-test suite still passes unchanged.

## BUSINESS AUDIT:

Unchanged — "Nhật ký nghiệp vụ" stays exactly as it was (own page, own `audit_logs` data, own `business_audit.view` permission). Not touched by this task in any way, per the explicit instruction to keep it unchanged.

## APPLICATION LOG:

MESFlow's own technical page ("Nhật ký hệ thống" → renamed **"Nhật ký ứng dụng"**) is unchanged in function — still `action_logs`/`error_traces` (HTTP request tracing, `g.trace_id`), still gated by `logs.view`, still page id `system-logs`. Only the user-facing label and subtitle changed, to stop implying it's infrastructure logs: `title.textContent='Nhật ký ứng dụng'`, subtitle now reads "...application-level tracing, không phải hạ tầng." The sidebar hint and the Business Audit page's own cross-reference text were updated to match. "Nhật ký hệ thống" as a name now belongs exclusively to Deploy Agent's Operations Center tab.

## Tabs removed from MESFlow (moved to Deploy Agent)

Per explicit instruction: whichever tabs had already become pure link-outs to Deploy Agent were deleted from MESFlow outright, not just hidden.

- **"System Health"** (`Điều hành` group) — deleted: menu entry, `PAGE_PERMISSION` entry, nav icon, `pages/system-health.js` (the file itself, and its `<script>` include in `app.html`).
- **"Operations Center"** (`Hệ thống` group) — deleted: menu entry, `PAGE_PERMISSION` entry, nav icon, the `renderOperationsCenter()` function and its `openPage()` dispatch branch.
- Cleaned up the now-fully-unused plumbing that only existed to feed those two pages: `MESFLOW_OPERATIONS_CENTER_URL` window global, `operations_center_url` template var and `settings.operations_center_url` pass-through in `app_page()`. (`settings.operations_center_url` itself is left defined in `config.py` — unused today, harmless, cheap to resurrect if a future MESFlow-side link-out is wanted again.)
- Verified by test: `test_system_health_and_operations_center_removed_from_mesflow` (source-level) and a rewritten Playwright test asserting `[data-page="system-health"]`/`[data-page="operations-center"]` have zero matches and `window.renderOperationsCenter` is `undefined`.

**How to view these on Deploy Agent instead** (told directly to the user in chat, since MESFlow no longer links to it):
- Open Deploy Agent's own Operations Center directly: `https://<your-deploy-agent-host>/ops` (same host/port you use for Deploy Agent's other pages, e.g. `http://127.0.0.1:8090/ops` from the server itself, or whatever your reverse-proxy path is).
- Log in with your Deploy Agent account (separate from MESFlow's login — this is by design, so it stays reachable even when MESFlow is down).
- All 8 tabs live there now: **Tổng quan, Cảnh báo, Sự cố, Chẩn đoán, Docker, Ports, Nhật ký hệ thống, Command/SSH.**
- If you want a bookmark/shortcut from within MESFlow again later, `MESFLOW_OPERATIONS_CENTER_URL` and the `renderOperationsCenter()` pattern are fully documented in `reports/SYSTEM_LOG_AUDIT_SEPARATION.md` and easy to restore from git history / this report.

## Deploy Agent Operations Center — visual polish

Requested ("có thể chỉnh giao diện Agent Deploy cho dễ nhìn không?"). Scoped to `deploy-agent/templates/ops.html`'s `<style>` block only — zero HTML structure, id, or class renamed (nothing JS depends on could break), zero behavior change:
- System font stack (`-apple-system,'Segoe UI',Roboto,...`) instead of plain Arial, with antialiasing.
- Nav bar: pill-container with subtle shadow, hover states on inactive tabs, active tab gets a soft colored shadow instead of a flat fill.
- Top bar: subtle gradient instead of a flat color, nav-back link gets a hover background.
- Cards: softer border+shadow combo, gentle hover lift, section headers get consistent letter-spacing.
- Tables: uppercase muted column headers, zebra-free but row-hover highlight, sticky header gets a hairline shadow so it reads clearly over scrolled content.
- Badges/incident rows/buttons: unchanged colors/logic, refined padding/radius/hover transitions for a less flat feel.
- Terminal panel: monospace stack widened (`SFMono-Regular, Consolas, Liberation Mono`), subtle inset border.

Verified: `/ops` still renders 200 with full expected content via Flask's test client (byte-length and key strings checked), `node`-level tag-balance check on the template, and the full 142-test Deploy Agent suite still passes unchanged (no test asserts on `ops.html` styling, confirmed by search — none exist to break).

## TESTS:

**Deploy Agent** (`.venv/bin/python -m pytest tests/ -q`, isolated `WORKSHOP_AGENT_HOME` scratch dir): **142 passed, 0 failed** — re-run twice this task (after the version bump, and again after the CSS polish), no changes to test files needed since this task made no Deploy Agent *behavioral* changes.

**MESFlow**, fresh isolated Docker Compose project (`-p mesflow-p7`, discarded after):
- New `tests/integration/test_v73_monitoring_cutover.py` (10 tests, all in-process against the real shared test Postgres, run in the `tests` container which does **not** set the enable flag — i.e. the real, default-off production configuration): legacy writer confirmed off by default; `summary()` creates zero new rows across all 8 tables through 3 consecutive calls including a non-healthy component; `summary()` still computes and returns a live result without persisting; `run_predictive()` CLI is a no-op and prints the skip message; diagnostic snapshot / AI analysis / notification dispatch+test all skip their inserts; `/api/system/ready` and `/api/system/health` both still 200; every legacy table still exists and is queryable; System Logs page confirmed renamed in source; System Health/Operations Center confirmed removed from source. **10/10 passed.**
- Session-relevant regression (`test_v69_system_health_unit.py`, `test_v69d_phase2_notifications_unit.py`, `test_v69g_phase3_predictive_unit.py`, `test_v71_ui_foundation.py`, `tests/integration/test_v69_system_health.py`, `tests/integration/test_v69d_phase2_notifications.py`, `tests/integration/test_v69g_phase3_predictive.py`, `tests/integration/test_v72_audit_operations_separation.py`, `tests/integration/test_v73_monitoring_cutover.py`): **83 passed, 0 failed.**
  - Fixed 4 real test breaks found along the way (not pre-existing — caused by this task's own flag, in the `tests` container where these 4 AI-analysis tests call `IncidentAIService` directly and don't go through `mesflow-test-api`'s HTTP API): `test_ai_analysis_with_mocked_valid_provider`, `..._malformed_provider_is_invalid_output`, `..._timeout_provider`, `..._cache_avoids_regenerating_for_same_context` now explicitly monkeypatch the flag back on for their own scope, proving the underlying AI-analysis write mechanism still works when deliberately re-enabled.
- Full repo `tests/` (444 tests): **376 passed, 68 failed.** Investigated the failure set against the previously-established ~68-failure baseline (`reports/SYSTEM_LOG_AUDIT_SEPARATION.md`): the exact membership shifted slightly (some legacy tests now pass, ~10 different ones now fail), but every single failure was traced to a **pre-existing** cause unrelated to this task:
  - Old hardcoded version-string assertions (`65.8.44.x`) — same class as before.
  - `test_dashboard_running_card_contract.py`, `test_employee_management_v6563.py` — check for literal UI strings (`const runningCard=x=>`, `'Tổng SP đạt'`) that predate the V71 UI-foundation modularization and have never been in `app.js` since; unrelated to system-health/operations-center.
  - `test_action_error_logging_v65818.py::test_ui` — checks that `/api/system/action-logs` is inline in `app.js`; it has lived in the separate `pages/system-logs.js` since the same V71 refactor, also predating this task.
  - The 5 shift/scheduling tests (`test_postgres_schema`, `test_production_consistency_p1`, `test_scheduling_time_p2` ×2, `test_shift_dashboard`) — root-caused by direct inspection of migration `0026_night_shift_same_day_midnight.py` (from the old `65.8.44.46` version line, long predating this session): it deliberately sets the default NIGHT shift's `cross_midnight=false` going forward. The failing tests still assert the pre-0026 `cross_midnight=true` behavior. Confirmed reproducible on a **freshly recreated, empty-tmpfs Postgres**, run as the very first thing in the container (ruling out test-order pollution) — this is stale test/migration drift from a much older change, not anything in this task's diff.
  - **Zero** of the 68 touch any file this task modified (`config.py`, `system_health_service.py`, `diagnostic_service.py`, `notification_service.py`, `ai_incident_service.py`, `cli.py`, `app.js`, `system-logs.js`, `app.html`, `app.py`, `compose.test.yml`). This task introduces **zero new regressions**.

## PLAYWRIGHT:

`tests/e2e/audit-operations-v72.spec.js`, 1920×1080, run against the fresh `mesflow-p7` stack: **2/2 passed**, zero page errors, zero console errors.
1. Business Audit Trail page renders with filters (screenshot reviewed — sidebar now shows "Nhật ký nghiệp vụ" and "Nhật ký ứng dụng"; "System Health"/"Operations Center" are gone from both the "Điều hành" and "Hệ thống" groups).
2. Rewrote the second test (previously "operations center page shows configured/not-configured state") to assert **absence**: `[data-page="system-health"]` and `[data-page="operations-center"]` have zero matches, `window.renderOperationsCenter` is `undefined`.

`tests/e2e/system-health-v69.spec.js` (tested the now-deleted in-page System Health dashboard) was deleted outright rather than rewritten again — the feature it tested no longer exists in MESFlow at all (not even as a link-out), so there is nothing left to test on the MESFlow side; Deploy Agent's Operations Center is the only remaining UI for this, and it isn't a MESFlow Playwright spec's concern.

## PRODUCTION DATA MUTATED: NO

`mesflow-postgres`: `StartedAt=2026-08-12T04:18:08.161154558Z`, `RestartCount=0` — byte-identical to the established baseline, reconfirmed at the end of this task. No migration ran against production (none was needed — no schema change this task). All DB verification happened against disposable `mesflow-p7` test-stack Postgres, torn down afterward along with its throwaway images.

## PRODUCTION DEPLOYED: NO (by this work) — but see note

This work never ran a build or deploy against production — no `scripts/build-release.sh`, no Deploy Agent upload/promote call, from this session. Only source-tree version declarations were bumped (MESFlow `71.0.0.3→71.0.0.4`; Deploy Agent `2.21.0→2.21.1-docker-runtime`, `docker/compose.linux.yml` image tag).

**Transparency note (same pattern as the previous report):** real `mesflow-app` was again observed to have moved versions during this session — from `71.0.0.1`→`71.0.0.2` (noted previously) and now further to `71.0.0.3` (`StartedAt=2026-08-13T23:32:47Z`, `RestartCount=0`, healthy) — by something outside this conversation, not by any command run here. `mesflow-postgres`, `mesflow-nginx`, `mesflow-qa-center`, and `mesflow-deploy-agent` all remain untouched. Flagged again for the same reason as before: for an accurate picture of what's changing in the real infrastructure and by whom, distinct from this task's own (deploy-free) work.
