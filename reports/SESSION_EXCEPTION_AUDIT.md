# Session Exception Audit

Audit date: 2026-08-12  
Project: `mesflow/`  
Audited version: `65.8.44.51`

## Current data model

- `work_sessions` is the source of truth for the real production session. Exception handling must not delete or replace it.
- `session_exception_reviews` stores the operator workflow. It already contains `session_id`, `exception_code`, `exception_fingerprint`, `workflow_status`, `resolution`, `note`, `assigned_to`, `started_at`, `started_by`, `resolved_at`, `resolved_by`, `created_at`, and `updated_at`.
- The current unique key is `(session_id, exception_fingerprint)`.
- `audit_logs` stores explicit business audit events. `action_logs` stores HTTP/request outcomes and is operational telemetry, not the authoritative exception history.

## Current detection flow

`ReportRepository.session_exceptions()` calculates exceptions from `work_sessions` when `/api/session-exceptions` is requested:

- `OVERLAP`: time ranges for two sessions belonging to the same employee overlap.
- `OPEN_TOO_LONG`: an open session is older than 12 hours.
- `ZERO_QTY_LONG`: a closed session lasting over four hours has zero good and defect quantities.
- `MISSING_STATION`: both `station_id` and `device_uuid` are absent.
- `INVALID_TIME`: `ended_at` is earlier than `started_at`.

Unclaimed detections are dynamic rows and are not persisted. A review row is created when a workflow action is first saved.

## Current workflow

1. A dynamically detected item is returned as `NEW`.
2. `Nhận xử lý` upserts a review with `IN_PROGRESS`, assignee, starter and start time. It does not modify the real Session.
3. The UI opens the exact Session through `MESFLOW_SESSION_EXCEPTION_CONTEXT`; Session editing uses the normal Session edit endpoint.
4. `Hoàn tất` changes the review to `RESOLVED`; `Bỏ qua` changes it to `IGNORED`. Both require a note in the backend.
5. Completed review rows remain stored and are returned through the history union.

The current UI is already master/detail, but it mixes workflow concepts in the quick filter (`Cần xử lý`, all active, done, all) instead of presenting the requested three user states directly.

## Where records are stored

- Real Session: `work_sessions`.
- Exception workflow and durable history: `session_exception_reviews`.
- Explicit workflow and Session-edit audit: `audit_logs`.
- Request/response operational trace: `action_logs`.

## What happens after Session correction

The detector may stop matching the Session. Existing review rows are added back by the `review_only` branch with `is_active=false` and the message `Bất thường không còn được phát hiện sau khi dữ liệu Session thay đổi`.

Therefore an `IN_PROGRESS` item no longer disappears after correction. A purely dynamic `NEW` item can disappear if the Session is corrected before anyone claims it; no workflow/history row exists in that case.

## What happens after RESOLVED

The review is not deleted. `workflow_status`, resolution, note, assignee, starter and resolver timestamps remain in `session_exception_reviews`, and the row is displayed through the history result.

The current implementation has a repeat defect: if the same rule becomes active again with the same fingerprint, the detector joins the old `RESOLVED` row. The repeated occurrence is therefore not presented as a new actionable item. Reopening the same row would also overwrite the meaning of the completed occurrence.

## Existing audit trail

- Workflow updates write `SESSION_EXCEPTION_WORKFLOW_UPDATE` to `audit_logs`.
- Real Session edits write `SESSION_EDIT` (including old/new values and reason) or `SESSION_ADJUST` to `audit_logs`.
- The request middleware writes API request outcomes to `action_logs`.

This separation is appropriate: the review table owns workflow state, the Session owns real data, and audit logs identify who changed what.

## Problems found

1. A resolved/ignored fingerprint suppresses a later occurrence of the same anomaly.
2. Reopening a history row can overwrite a completed occurrence instead of creating a distinct occurrence.
3. The UI does not expose exactly three clear user states: `Cần xử lý`, `Đang xử lý`, and `Lịch sử`.
4. History lacks dedicated filters for date, employee, PO, exception type, result, and handler.
5. History details do not show all trace fields (detected/recorded time, starter, resolver, resolution, completion time) clearly.
6. Dashboard wording currently mixes active detection counts with workflow counts.
7. Backend accepts direct `NEW` transitions for a completed review, which permits destructive history reopening.
8. Workflow audit currently records the submitted assignee instead of the actor fallback actually saved when the client omits it.

## Proposed UI

- Replace the quick filter with three tabs, defaulting to `Cần xử lý`:
  - `Cần xử lý`: active `NEW` occurrences.
  - `Đang xử lý`: every `IN_PROGRESS` review, including one whose underlying detector no longer matches.
  - `Lịch sử`: `RESOLVED` and `IGNORED` reviews.
- Keep the compact master/detail layout.
- Show Session, employee, operation, PO, detection time, severity and next action in the queue/detail.
- Add history filters for date, employee, PO, exception type, result and handler.
- Show `Bất thường không còn được phát hiện` without removing an in-progress review.
- Require a reason for Ignore and retain the normal receive → exact Session → return → finish workflow.

## Proposed backend changes

- Generate a new occurrence fingerprint when a currently detected base anomaly has only completed historical reviews. Keep the first fingerprint compatible; suffix later occurrences deterministically using the prior review id.
- Prefer an existing `NEW`/`IN_PROGRESS` occurrence fingerprint while it is active, so edits and reloads keep addressing the same review.
- Return completed prior occurrences separately in history even while a new occurrence is active.
- Disallow changing a completed review back to `NEW`; repeated anomalies must create a new occurrence and preserve old history.
- Return `review_created_at` as the durable recorded/detection proxy for history.
- Record the effective assignee and resolution in the workflow audit event.
- Add focused repository/API/UI tests for correction persistence, ignore reason, reload/restart persistence contract and repeated occurrences.

## Migration required NO

The existing table has all required workflow/audit fields. Multiple occurrences can be preserved using distinct occurrence fingerprints under the existing unique constraint. This avoids schema churn and preserves all current records.

The trade-off is that an unclaimed, dynamic `NEW` detection has no durable first-detected timestamp. Once claimed, `created_at` is its durable recorded time. If the product later requires a complete history of every transient unclaimed detection, a separate detector/materialization design and migration should be reviewed rather than writing to the database from a report GET endpoint.
