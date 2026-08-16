# MESFlow V66 — Architecture & Reliability

Phase A assessment: `reports/V66_ARCHITECTURE_ASSESSMENT.md` (read first —
it explains why several V66 goals were already partially implemented in
this codebase before this task, which changed the scope of what needed to
be built).

## Architecture

**Old flow** (`/api/work-sessions/start`, `/api/work-sessions/<id>/finish`):

```
Route -> WorkSessionRepository().start(raw_dict) / .finish(id, raw_dict)
       -> single `with transaction()` block (idempotency, validation, mutation,
          reconciliation) -- already existed, unchanged
       -> raw dict returned straight to jsonify()
       (no audit row, no event, no typed shape anywhere in the path)
```

**New flow** (same two routes):

```
Route (mesflow.web.execution)
  -> Typed Command (StartSessionCommand / FinishSessionCommand, frozen dataclasses)
    -> SessionService (mesflow.services.session_service)
      -> structural validation (ValidationError on bad shape; business rules
         -- overlap, rework<=defect, PO/operation readiness -- stay exactly
         where they already lived, in WorkSessionRepository)
        -> WorkSessionRepository.start()/finish() (unchanged SQL/locking)
          -> single transaction (existing), now also writes the audit row
             on the SAME cursor before returning
            -> record_audit() (mesflow.domain.audit) -- SESSION_STARTED /
               SESSION_FINISHED, correlation_id = the request's X-Trace-ID
              -> event_bus.publish(SessionStarted / SessionFinished) --
                 only after the transaction has committed, only when the
                 mutation was not an idempotent replay
  <- typed Result (Start/FinishSessionResult) mapped back to the exact
     pre-existing JSON response shape
```

Service/domain boundaries introduced:

- `mesflow.domain.errors` — `DomainError` base + `ValidationError`,
  `PermissionDeniedError`, `InfrastructureError` (new), plus
  `NotFoundError`/`ConflictError`/`InvalidStateError` that are real
  subclasses of the pre-existing `mesflow.db.repositories.base` errors (so
  every existing `except NotFoundError`/`isinstance(..., ConflictError)`
  check anywhere in the app keeps working unchanged for the new types).
- `mesflow.domain.events` — `DomainEvent` base, `SessionStarted`/
  `SessionFinished` frozen dataclasses, `EventBus` (synchronous, in-process,
  a broken handler is logged and isolated, never propagates).
- `mesflow.domain.event_handlers` — default handlers, registered once in
  `create_app()`.
- `mesflow.domain.audit` — `record_audit(cur, ...)`, the transactionally
  consistent sibling of the pre-existing `AuditRepository.log()` (which is
  untouched and still used by its ~10 existing call sites).
- `mesflow.services.session_service` — `SessionService`,
  `StartSessionCommand`/`Result`, `FinishSessionCommand`/`Result`.

## Files changed

New:
- `app/mesflow/domain/__init__.py`, `errors.py`, `events.py`,
  `event_handlers.py`, `audit.py`
- `app/mesflow/services/__init__.py`, `session_service.py`
- `app/migrations/versions/0030_v66_audit_foundation.py`
- `tests/test_v66_domain_foundation.py`
- `tests/integration/test_v66_session_service.py`
- `reports/V66_ARCHITECTURE_ASSESSMENT.md`, this report

Modified:
- `app/mesflow/db/repositories/execution.py` — `WorkSessionRepository.start()`
  and `.finish()` gained three optional kwargs
  (`audit_actor_username='', audit_actor_user_id=None, audit_correlation_id=''`,
  all defaulted) and one additional `record_audit(cur, ...)` call inside
  their existing transaction, right before the return. No existing SQL,
  locking, or business-rule logic changed. The Kiosk-facing calls into
  these same methods (`mesflow.web.kiosk`, and the multi-session batch call
  in `web/execution.py`) now also get an audit row for free, with empty
  actor fields, since they don't pass the new kwargs.
- `app/mesflow/web/execution.py` — `start_session()`/`finish_session()`
  routes rewritten to build a typed command and call `SessionService`
  instead of calling `WorkSessionRepository` directly. Response shape/status
  codes unchanged (verified in tests below). Kiosk's own finish route
  (`mesflow.web.kiosk.kiosk_finish`) is untouched.
- `app/mesflow/web/errors.py` — `api_error_response` gained two additive
  `isinstance` branches (`PermissionDeniedError`->403, plus `ValidationError`
  folded into the existing 400 branch). Pre-existing branches/status codes
  unchanged (regression-tested, see below).
- `app/mesflow/web/app.py` — one line registering the default event
  handlers once at startup.
- `VERSION.txt`, `app/mesflow/__init__.py`, `release.json`, `compose.yml` —
  version bump `65.8.44.70` -> `65.8.44.71` via `scripts/bump-version.sh`
  (repo's existing convention; this is a new, never-before-packaged version).

## Database

- **Migration added**: `0030_v66_audit_foundation`, `down_revision =
  0029_kiosk_ota_fleet_safety` (the actual head at the time this task
  started). Purely additive:
  - `audit_logs` gains: `actor_user_id BIGINT REFERENCES users(id) ON
    DELETE SET NULL`, `employee_id BIGINT REFERENCES employees(id) ON
    DELETE SET NULL`, `correlation_id TEXT NOT NULL DEFAULT ''`,
    `before_json TEXT NOT NULL DEFAULT '{}'`, `after_json TEXT NOT NULL
    DEFAULT '{}'`, `source TEXT NOT NULL DEFAULT ''`, plus a partial index
    on `correlation_id`.
  - No table dropped, no column renamed, no existing column's type changed,
    no historical row rewritten.
  - `system_meta.schema_version` -> `65.8.44.71` (same convention as every
    prior migration).
- **Verified against a real, local, disposable PostgreSQL** (this
  project's own `compose.test.yml` stack, `tmpfs`-backed, destroyed after
  the run) — `alembic upgrade head` ran automatically on container start;
  the app's own `/api/system/ready`-equivalent startup check reported
  `"migration_head": "0030_v66_audit_foundation"` and listed
  `audit_logs`/`work_sessions`/etc. as present. This migration was **never
  run against the real production database** — production's migration head
  is still `0029_kiosk_ota_fleet_safety` (confirmed by reading the real
  `mesflow-app` container's own startup log during this task, which still
  reports `migration_head: 0029_kiosk_ota_fleet_safety`).

## Reliability

- **Transaction boundaries**: `WorkSessionRepository.start()`/`.finish()`
  already ran as one `with transaction()` block; the new audit insert was
  added *inside* that same block, on the same cursor, so a session can
  never exist without a matching `SESSION_STARTED`/`SESSION_FINISHED`
  audit row (or vice versa) — proven by the integration test that reads
  `audit_logs` back after a real HTTP call. No new commit boundary was
  introduced; no repository method calls `commit()` on its own outside the
  existing pattern.
- **Error handling**: service/domain errors are typed
  (`mesflow.domain.errors`), and HTTP status translation stays entirely in
  `mesflow.web.errors.api_error_response` — services never choose an HTTP
  status. Pre-existing error->status mappings (404/409/400/500) are
  regression-tested unchanged.
- **Audit**: `SESSION_STARTED`/`SESSION_FINISHED` are now recorded for
  every real (non-replay) start/finish, through both the newly-migrated web
  route and the still-unmigrated kiosk/batch call sites (since the audit
  insert lives in the shared repository method). An idempotent replay does
  **not** create a second audit row (tested).
- **Event handling**: `SessionStarted`/`SessionFinished` are published
  after the owning transaction commits, carrying the same `correlation_id`
  as the audit row. A handler exception is caught, logged, and does not
  propagate to the HTTP response or block other handlers (tested with a
  deliberately broken handler).
- **Tracing**: the pre-existing `g.trace_id`/`X-Trace-ID` (see
  `mesflow.web.action_logging`) is now the same value written as
  `audit_logs.correlation_id` and as the domain event's `correlation_id` --
  closing the HTTP request -> service -> DB mutation -> audit row -> event
  -> logs chain end to end for this flow, without inventing a second,
  competing ID or touching the separate ESP `session_trace_id` concept.

## Compatibility

- Existing APIs: **unchanged**. `/api/work-sessions/start` still returns
  HTTP 201 with `{"ok":true,"session":{...},"idempotent_replay":bool}`;
  `/api/work-sessions/<id>/finish` still returns HTTP 200 with the same
  shape. Verified by integration tests hitting the real HTTP endpoints.
- Kiosk protocol: **unchanged** — `mesflow.web.kiosk` was not touched.
- Frontend contract: **unchanged** — no response field removed/renamed/
  retyped; only additive DB columns.
- Database compatibility: **maintained** — additive migration only, old
  `audit_logs` readers (`AuditRepository.list()`, the admin action-log UI)
  keep working since every new column is nullable/defaulted.

## Testing

Ran the project's own isolated test stack (`compose.test.yml`, tmpfs
PostgreSQL + a real MESFlow API container, fully separate from the real
production `mesflow-app`/`mesflow-postgres` — no production database or
container was touched at any point in this task):

- **16/16 new V66 tests pass**, run twice for a clean final confirmation:
  - `tests/test_v66_domain_foundation.py` (9 unit tests, no DB): domain
    error codes and `isinstance` compatibility with pre-existing repository
    errors; `api_error_response` status codes for both new and pre-existing
    error types; event bus dispatch, correlation-ID propagation, handler
    failure isolation, idempotent re-subscription, event immutability.
  - `tests/integration/test_v66_session_service.py` (7 tests, real
    PostgreSQL + real HTTP): happy-path start->finish response contract
    unchanged; a transactionally-consistent `SESSION_FINISHED` audit row is
    created with the request's `X-Trace-ID` as `correlation_id`; idempotent
    replay does not duplicate the audit row; double-finish still 409;
    rework>defect still 400; finishing a missing session still 404; a
    second OPEN session for the same employee is still 409.
- **Full existing suite**: `182 passed` (unit+static), `30+35 passed` /
  4+1 failed (behavior+integration, before/after both isolated to
  NIGHT-shift/`cross_midnight` scheduling tests unrelated to this task's
  files).
- **Pre-existing baseline confirmed independently of V66**: with every V66
  file (`app/mesflow/domain/`, `app/mesflow/services/`, the new migration,
  the new tests, and the 4 modified files) temporarily set aside via
  `git stash`, rebuilding and re-running the exact same unit+static suite
  reproduced the **identical 62 failures** (same test names, same
  assertions) — proving they are pre-existing (mostly VERSION.txt-pinned
  historical test debt across ~50 files spanning versions 65.8.44.47
  through .58, plus an already in-progress, unrelated, uncommitted
  nav-bar/back-navigation UI change already present in the workspace
  before this task started). **Zero new failures were introduced by V66.**
- The NIGHT-shift/`cross_midnight` failures in the behavior/integration
  phases (`test_scheduling_time_p2.py`, `test_shift_dashboard.py`,
  `test_postgres_schema.py::test_default_day_and_night_shifts_are_seeded`,
  one retry test in `test_production_consistency_p1.py`) were not
  re-verified with the same stash technique, because a stray, unrelated
  migration file (`0031_v67_exception_center.py`, not authored by this
  task) was observed appearing and disappearing in the shared workspace
  during a rebuild — clear evidence another process/session is
  concurrently modifying this same repository. Repeating destructive
  `git stash` cycles against a shared working tree was judged unsafe to
  continue. These failures are about work-shift seed data/cross-midnight
  time math; this task never touched `scheduling.py`, `working_calendar.py`,
  `time_policy.py`, or any shift-seed migration, so they are almost
  certainly unrelated -- flagged here as an honest gap rather than silently
  assumed.
- **Deploy Agent / MESFlow production regression**: not applicable to this
  task (no deploy performed); the real `mesflow-app` container was
  confirmed still on image `mesflow-app:65.8.44.70@sha256:d65a0710b...`
  (unchanged digest) with `migration_head: 0029_kiosk_ota_fleet_safety`
  (i.e. this task's migration never reached it), and `mesflow-postgres`'s
  `StartedAt` is byte-for-byte unchanged from this session's own baseline
  (`2026-08-12T04:18:08Z`). `mesflow-app`'s `StartedAt` did change during
  this session (a restart, same image/version) — this was not caused by
  any command run in this task (no `docker restart`/`compose up` against
  the production compose was ever issued here); it is consistent with the
  same concurrent external session already evidenced by the stray
  migration file.

### Known gaps

- The NIGHT-shift integration failures above were not conclusively proven
  pre-existing (see explanation) -- next session should re-run the
  stash-diff check once the workspace is confirmed idle.
- No dedicated test yet asserts "rollback does not leave a misleading audit
  row" via a forced mid-transaction failure (e.g. a simulated
  `record_audit` exception) — the design guarantees it (same
  cursor/transaction as the mutation), but it is asserted by code review,
  not by an explicit failure-injection test.

## Remaining V66 work

```
DONE:
  - Service/Domain layer foundation (mesflow.domain.*, mesflow.services.*)
  - Typed commands/results for Start/Finish Session
  - Domain error hierarchy, backward-compatible with existing repository errors
  - In-process domain event bus + SessionStarted/SessionFinished
  - Transactional audit foundation (record_audit), applied to start() and finish()
  - Correlation ID unification: g.trace_id -> audit_logs.correlation_id -> event.correlation_id
  - Flagship vertical migrated end-to-end: /api/work-sessions/start and
    /api/work-sessions/<id>/finish now follow the full
    Route -> Command -> Service -> Domain validation -> Repository ->
    Transaction -> Audit -> Event pipeline (Definition of Done met)
  - Additive Alembic migration (0030), verified locally, single head
  - Version bump per repo convention (65.8.44.70 -> 65.8.44.71)
  - 16 new tests, all passing against a real local PostgreSQL

PARTIAL:
  - Structured logging / correlation ID (sections 9-10): most of this
    already existed in mesflow.web.action_logging before V66; this task's
    contribution was threading the existing trace_id into the audit/event
    layer, not building logging from scratch.
  - Idempotency preparation (section 11): already substantially present
    (kiosk_idempotency + request_id) before V66 for Start/Finish Session;
    not extended to any new endpoint in this task.

NOT STARTED / DEFERRED (explicitly out of this task's minimum scope, per
Definition of Done requiring only one flagship vertical):
  - Operation start/complete through the Service layer
  - Production Order start/complete through the Service layer
  - Kiosk production entry through the Service layer (device protocol
    intentionally left untouched for compatibility)
  - PermissionDeniedError is not yet raised by any real call site (the
    hook exists in mesflow.domain.errors and mesflow.web.errors; no
    route was changed to use it, since the existing roles_required/
    permission_required decorators already cover authorization and were
    not touched)
  - Dedicated failure-injection test for "rollback leaves no misleading
    audit row"
  - Re-confirming the NIGHT-shift integration failures are pre-existing
    (see Known gaps)
```

## Production mutation

None. No production deploy, restart, database migration, or destructive
Docker command was run against `mesflow-app`/`mesflow-postgres`. All
building/testing used the project's own disposable `compose.test.yml`
stack, torn down at the end of this task.
