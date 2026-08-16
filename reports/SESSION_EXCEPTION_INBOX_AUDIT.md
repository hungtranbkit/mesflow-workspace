# Session Exception Inbox Audit (read-only)

Date: 2026-08-13 (Asia/Bangkok)

## Scope and safety

This audit queried the local DEV database through the running PostgreSQL
container. No production database was accessed or mutated. No Session was
finished, cancelled, deleted, or edited. Sessions 577/580 were not changed.

## Current detector result

The current SQL detector produces **26 exception rows across 24 unique sessions**
(28 sessions exist in this local fixture database). The rows are:

| Source | Anomaly | Count | Inbox decision |
|---|---|---:|---|
| QA_TEST | OPEN_TOO_LONG | 20 | TEST_DATA |
| TUTORIAL | INVALID_TIME | 1 | TEST_DATA |
| TUTORIAL | MISSING_STATION | 1 | TEST_DATA |
| TUTORIAL | OPEN_TOO_LONG | 1 | TEST_DATA |
| TUTORIAL | OVERLAP | 2 | TEST_DATA |
| TUTORIAL | ZERO_QTY_LONG | 1 | TEST_DATA |

No `REAL_USER` row was found. The current fixture has no actionable production
exception to present to a manager. `start_request_id` values make the QA and
tutorial origin deterministic (`QA-REAL-START-*`, `TUT*`). QA orphan sessions
are therefore excluded from the manager Inbox, while remaining available in
history/detail APIs.

## Classification rules

1. `QA-REAL-START-*` or `QA-RUN-*` => `QA_TEST` / `TEST_DATA`.
2. `TUT*`, tutorial note/employee/PO => `TUTORIAL` / `TEST_DATA`.
3. Otherwise => `REAL_USER` only when a real employee/device trace exists;
   otherwise `UNKNOWN`.
4. An active detector row with a data-impacting anomaly is actionable only when
   a human decision is required. A missing/closed condition is `HISTORY_ONLY`.
5. A resolved/ignored review remains audit history and is never deleted.
6. Default Inbox includes only `ACTION_REQUIRED` and `CONFIRMATION`; test data,
   expected conditions and history are excluded from the default queue.
7. A completed fingerprint is a new occurrence only when the detector's base
   condition changes and produces a new occurrence fingerprint.

## Before / after

```text
OLD: 26 anomaly rows visible to an operator-oriented exception view
NEW: 0 ACTION_REQUIRED + 0 CONFIRMATION in this local fixture
      (26 TEST_DATA rows remain available under Lịch sử/Chi tiết)
```

## Human-impact fields

The classified API preserves employee, operation, start/end, quantity, station,
device, source trace and anomaly code. For a real case the UI must state the
impact on working time, quantity, KPI, PO progress and employee state. The
current fixture has no such real case; therefore there is no honest
ACTION_REQUIRED/CONFIRMATION case to list.

## QA Center safeguard

QA/Tutorial origin is classified from persisted request/fixture identity rather
than inferred from age or status. This prevents QA orphan sessions from filling
the manager Inbox without weakening the underlying anomaly detector.

## Implementation status

The deterministic classification is now implemented in the repository/API layer;
the default API view is Inbox-only and the History view requests all retained
detector rows. Production
deployment and production data mutation remain out of scope.
