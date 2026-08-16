# MESFlow V66 — Phase A: Architecture Assessment

Read before any refactor, per the V66 task's section 1. Findings below are
from direct code inspection of `mesflow/` as of `65.8.44.70` (pre-V66).

## 1. Entry points / stack

- Flask app factory: `app/mesflow/web/app.py::create_app()`. Waitress WSGI
  server in production. No ORM: `app/mesflow/db/connection.py` wraps
  **psycopg 3** directly (`dict_row`, hand-written SQL), not SQLAlchemy.
  SQLite is explicitly refused (`mesflow.core.config`).
- Blueprints: `master_data`, `execution`, `analytics`, `excel_io`,
  `template_excel_io`, `kiosk` (aka `web_kiosk`), `internal_ota`, `users`,
  `action_logging`.
- Alembic migrations: `app/migrations/versions/0001..0029`, linear chain,
  verified with `alembic heads` (single head) before this work started.

## 2. Business logic location — better than the generic V66 brief assumed

`app/mesflow/db/repositories/*.py` is **already** a repository layer with
real transaction boundaries, not simple CRUD wrappers:

- `WorkSessionRepository.start()` / `.finish()` (`db/repositories/execution.py`)
  each run **one** `with transaction() as conn:` block covering: idempotency
  key lock, replay check, business validation (overlap, PO/operation
  readiness, quantity dependency, rework<=defect), the mutation itself,
  `reconcile_operation_and_po()`, and the idempotency-response insert. This
  already matches most of section 4's "single transaction per command" goal
  for this specific vertical.
- Idempotency already exists end-to-end: every kiosk/API start/finish call
  carries a `request_id`; `kiosk_idempotency(request_id, action,
  response_json)` makes replays return the original response instead of
  re-running the mutation (`WorkSessionRepository._replay`). Section 11
  ("idempotency preparation") is materially already done for this vertical.
- `RepositoryError` / `NotFoundError` / `ConflictError`
  (`db/repositories/base.py`) already give a small, real error vocabulary,
  and `mesflow.web.errors.api_error_response` already translates them to
  stable HTTP codes (404/409/400) used by existing clients. Section 6's
  "standardize service-layer failures" was largely already true.
- **Structured request logging and correlation ID already exist**:
  `mesflow.web.action_logging` sets `g.trace_id` on every request
  (`X-Trace-ID` header, echoed back in the response), records
  `action_logs`/`error_traces` with actor, source (WEB/KIOSK), duration,
  outcome, sanitized request/response bodies (secrets redacted), and
  already suppresses noisy heartbeat/GET logging. Sections 9 and 10 were
  **largely already implemented** before this task, under a different name
  (`trace_id`, not `correlation_id`).
- A **separate**, real audit table already exists:
  `mesflow.db.repositories.analytics.AuditRepository.log()` writes to
  `audit_logs(actor_username, action, entity_type, entity_id,
  details_json)`, used by ~10 routes (`KIOSK_APPROVE`, `PRODUCTION_STATE_RECONCILE`,
  `QC_START/COMPLETE`, `SESSION_ADJUST`, `SESSION_EDIT`, ...).

## 3. Real gaps found (what V66 actually needed to add)

1. **No Service/Application layer.** Routes call
   `WorkSessionRepository().start(request.get_json())` / `.finish(...)`
   directly, passing/returning raw `dict`. There was no typed command/result
   boundary, and no single place a caller could depend on for "start a
   session" independent of the persistence module.
2. **`/api/work-sessions/start` and `/finish` had no audit trail.**
   Unlike `SESSION_ADJUST`/`SESSION_EDIT`, the two highest-frequency
   session mutations were never audited at all.
3. **Existing `AuditRepository.log()` is not transactionally consistent**
   with the mutation it describes — it opens its own transaction, called
   *after* the business mutation's transaction already committed. A crash
   between the two leaves a mutation with no audit row.
4. **No domain event mechanism** of any kind (in-process or otherwise).
5. **`g.trace_id` (the existing correlation ID) was not threaded into
   `audit_logs`** — an audit row could not be joined back to the
   `action_logs` row for the same HTTP request.
6. **Repository methods return raw dicts with no typed shape**; a caller
   has no static guarantee about what `WorkSessionRepository.finish()`
   returns beyond reading the code.

## 4. What V66 intentionally does NOT change

- `WorkSessionRepository`'s existing SQL, locking (`FOR UPDATE`/`FOR SHARE`),
  overlap guard, quantity-dependency validation, and rework<=defect rule:
  unchanged, still the single source of truth.
- The Kiosk device protocol (`mesflow.web.kiosk`,
  `/api/kiosk-web/start`, `/api/kiosk-web/finish/<id>`): untouched.
- `session_trace_id` (ESP offline-sync event tracing,
  `db/repositories/offline_sync.py`): a distinct, pre-existing concept, left
  as-is. V66's `correlation_id` (`g.trace_id`) is a separate, HTTP-request-scoped
  identifier; the two are not merged.
- `AuditRepository.log()` and all ~10 existing call sites: untouched,
  still work exactly as before. The new `mesflow.domain.audit.record_audit()`
  is an additive sibling for transactionally-consistent call sites, not a
  replacement.

## 5. V66 boundaries introduced

```
Route (mesflow.web.execution)
  -> Typed Command (mesflow.services.session_service.{Start,Finish}SessionCommand)
    -> Service (mesflow.services.session_service.SessionService)
      -> Domain validation (structural only; business rules stay in the repository)
        -> Repository (mesflow.db.repositories.execution.WorkSessionRepository, unchanged SQL)
          -> Single transaction (existing `with transaction() as conn:`, now also
             writes the audit row on the same cursor)
            -> Audit (mesflow.domain.audit.record_audit, transactionally consistent)
              -> Domain Event (mesflow.domain.events.event_bus.publish, after commit)
```

## 6. Files expected to change (as planned; matches what was actually changed)

- New: `app/mesflow/domain/{errors,events,event_handlers,audit}.py`
- New: `app/mesflow/services/session_service.py`
- New: `app/migrations/versions/0030_v66_audit_foundation.py`
- Modified (additive kwargs only): `app/mesflow/db/repositories/execution.py`
- Modified (2 routes migrated): `app/mesflow/web/execution.py`
- Modified (additive error mapping): `app/mesflow/web/errors.py`
- Modified (register event handlers once at startup): `app/mesflow/web/app.py`

## 7. Migration risk

Low. All new `audit_logs` columns are nullable or defaulted; no existing
column/table is dropped, renamed, or has its type changed. Verified with a
real `alembic upgrade head` against a fresh local PostgreSQL instance (see
final report) — chain resolves to a single head, `0030_v66_audit_foundation`,
down_revision `0029_kiosk_ota_fleet_safety`.
