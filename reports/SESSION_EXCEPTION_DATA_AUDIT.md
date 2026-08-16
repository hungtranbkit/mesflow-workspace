# Session Exception Data Audit

Audit time: 2026-08-12 (Asia/Bangkok)  
MESFlow deployed/workspace version: `65.8.44.52`  
QA Center deployed version: `1.19.6`  
Database: PostgreSQL 17, container `mesflow-postgres`, database/user `mesflow`

## Safety and method

- Database inspection used explicit `BEGIN READ ONLY` transactions.
- The exact `ReportRepository.session_exceptions()` used by `/api/session-exceptions` was executed with PostgreSQL `default_transaction_read_only=on`. Direct HTTP was deliberately avoided during Phase 1 because MESFlow's request middleware would insert an `action_logs` row.
- No database `UPDATE`, `DELETE`, migration, cleanup, restart, or production deployment was performed during this audit.
- Reconciliation found no deployed source to import: MESFlow differences were only workspace `.pytest_cache`; QA Center difference was workspace-only `AGENTS.md`.

## Executive result

The current API-equivalent payload contains **28 exception rows over 25 distinct affected Sessions**:

- **20 rows / 20 Sessions are QA_BUG**, not intended anomalies. They are realistic-soak Sessions left OPEN after QA lost its persistent session map and then became permanently blocked by missing production credentials.
- **8 rows / 5 Sessions are TUTORIAL_DATA** deliberately seeded by `tutorial_data.py`. Two tutorial Sessions each produce both a completed historical occurrence and a new active occurrence because the seed claims a correction/ignore while deliberately leaving the underlying anomalous data unchanged.
- No current row has evidence of `REAL_USER`, `MESFLOW_RULE_BUG`, `MESFLOW_FLOW_BUG`, or `UNKNOWN` origin.

## Summary by exception type

Counts below are API rows (history occurrences included), not distinct Sessions.

| Exception type | Count | QA expected | QA bug | Tutorial | Real | MESFlow bug | Unknown |
|---|---:|---:|---:|---:|---:|---:|---:|
| OPEN_TOO_LONG | 21 | 0 | 20 | 1 | 0 | 0 | 0 |
| ZERO_QTY_LONG | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| OVERLAP | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| MISSING_STATION | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| INVALID_TIME | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| **Total** | **28** | **0** | **20** | **8** | **0** | **0** | **0** |

Current workflow states: `NEW=24`, `IN_PROGRESS=2`, `RESOLVED=1`, `IGNORED=1`. Active detector rows: 26; inactive history rows: 2.

## Session-by-session classification

| Session | Exception | Classification | Evidence |
|---:|---|---|---|
| 1–20 | OPEN_TOO_LONG | QA_BUG | Employee/PO/station/device all use `QAV65817-`; start IDs use `QA-REAL-START-*`; all 20 were opened within five seconds; all remain OPEN with no finish ID. QA persistent state now has zero Sessions. |
| 72 | ZERO_QTY_LONG (historical RESOLVED + new active occurrence) | TUTORIAL_DATA | `TUT-E05`, `TUT-PO-GUIDE-39`, `TUT39-ZERO-*`, note explicitly says `TUT39:ZERO_QTY_LONG`. Seed stores zero quantity while also inserting a synthetic RESOLVED review. |
| 73 | MISSING_STATION (historical IGNORED + new active occurrence) | TUTORIAL_DATA | `TUT-E06`, `TUT39-MISSING-*`, explicit tutorial note, intentionally null station/device. |
| 75 | OVERLAP with Session 74 | TUTORIAL_DATA | Both Session notes and request IDs are `TUT39-OVERLAP-*`; overlap is inserted directly by tutorial seed. |
| 76 | INVALID_TIME | TUTORIAL_DATA | `TUT39-INVALID-*`; tutorial seed explicitly inserts ended_at before started_at and documents it as synthetic. |
| 77 | OPEN_TOO_LONG and OVERLAP with Session 70 | TUTORIAL_DATA | `TUT39-LONG-*`, `TUT-KIOSK-LONG`; seed intentionally creates a 13-hour open Session. Its overlap with tutorial Session 70 is a side effect of using the same tutorial employee/time range. |

Session 70 and 74 are conflict counterparts but are not separate exception rows because the detector emits only the later Session in each pair.

## Most suspicious Sessions

1. **Sessions 1–20**: 20 workers all started at 10:41 local on 2026-08-11 and all remained OPEN for about 25.5 hours. With configured `forgot_finish_rate_percent=4`, all twenty cannot reasonably be expected forgot-finish cases. Their state was lost.
2. **Session 77**: deliberately long tutorial Session also overlaps Session 70, so one tutorial example produces two warnings. This is valid detector behavior but noisy tutorial design.
3. **Session 72**: history says quantity was corrected, but the real Session remains zero. The occurrence-aware detector correctly creates a new warning; the synthetic tutorial narrative is inconsistent.
4. **Session 73**: history says ignored as an intentional demo case while the underlying missing-station condition remains. The new occurrence is technically correct but duplicates a deliberate tutorial narrative.

## PostgreSQL evidence

The 20 QA Sessions have:

- `status=OPEN`, `ended_at=NULL`, `good_qty=defect_qty=rework_qty=0`;
- valid station and device (`QAV65817-ST-*`, `QAV65817-KIOSK-*`);
- `start_request_id=QA-REAL-START-<uuid>` and no finish request ID;
- action-log and idempotency evidence proving each initial start and replay succeeded exactly once;
- no evidence of duplicate open Sessions for the same employee.

The database has 28 Sessions total: 20 QA realistic-soak and 8 tutorial. Therefore none of the current exception rows are unmarked real production Sessions.

## API and UI comparison

The current UI consumes the fields returned by the repository correctly and separates `Cần xử lý`, `Đang xử lý`, and `Lịch sử`. It does not expose source classification. A reviewer sees natural Vietnamese employee names and can mistake `QAV65817-*` Sessions for real work unless they inspect codes/device/request IDs.

The API currently omits `start_request_id`, `finish_request_id`, Session note, and a normalized source classification from exception rows. Reliable source evidence exists in the database but is not surfaced.

## MESFlow detection rules

### OPEN_TOO_LONG

- Current rule: every OPEN Session older than 12 hours.
- The rule detects the current data correctly.
- The threshold is independent of configured shifts/day boundaries. That may deserve later product configuration, but there is no current false-positive evidence: all affected QA Sessions are over 25 hours and the tutorial Session is intentionally 13 hours.
- QA's intentional forgot-finish rate is 4%, capped at 20%. A forgot Session is scheduled for next-day entry and may legitimately cross 12 hours. None of the 20 current QA Sessions can be proven expected because their per-Session plan state was lost; collectively they are QA_BUG.

### ZERO_QTY_LONG

- Current rule: CLOSED, duration over four hours, `good_qty + defect_qty = 0`.
- MESFlow finish accepts zero quantities, so zero output can be a valid recorded outcome. The four-hour threshold makes this a review warning, not proof of invalid data.
- Current rows are explicit tutorial data; no real false positive is demonstrated.
- Tutorial Session 72 is internally inconsistent: its review says output was corrected while the Session still contains zero.

### OVERLAP

- Current runtime start prevents a second OPEN Session for the same employee; finish and supervisor edit also run overlap validation.
- Current overlap rows were inserted directly by the tutorial seeder and therefore do not demonstrate a MESFlow flow bug.
- Session 77's overlap is an unintended extra tutorial warning, not a detector false positive.

### MISSING_STATION

- Current rule requires either `station_id` or `device_uuid`.
- Kiosk-created QA Sessions have both. The only current row was explicitly inserted without both by tutorial data.
- Whether an administrator may legitimately create a manual Session without a station is a product-policy question; current data provides no real example to decide it.

### INVALID_TIME

- Runtime finish and supervisor edit reject end-before-start.
- The only row was inserted directly by tutorial seed with an explicit synthetic comment.
- No timezone, midnight, or night-shift defect is evidenced by current data.

## QA Center audit

Active run parameters:

- workers: 20; active POs: 2; run: 7 days; tick: 60 seconds;
- Session target: 120–1440 minutes; normal variance: 30%; anomaly rate: 2%; multiplier: 1.8–4.0;
- forgot-finish: 4%; night shift: 19:00–07:00; report interval: 60 minutes; seed: 65817.

Intended QA anomaly behavior:

- `FORGOT_FINISH_NEXT_DAY`: intentionally leaves a Session open until next workday entry time.
- `MACHINE_JAM` / `MATERIAL_WAIT` / `FORGOT_FINISH` profiles: duration multiplier scenarios, still capped by shift end.
- Invalid finish probes: negative quantity, repairable greater than defect, output over plan, and input mismatch; these are expected to be rejected and should not create stored Session anomalies.
- Double-open probe is expected to be rejected; action/idempotency evidence shows no duplicate Session creation here.

QA defects found:

1. `reconcile_state()` only removes stale local rows; it never adopts live `QAV65817-*` OPEN Sessions missing from local state.
2. The current persistent state has `sessions={}` while Sessions 1–20 remain OPEN, so `finish_due()` can never close them.
3. The active run is marked RUNNING/auto-resume but has been in `WAITING_MESFLOW` since start because production auto-login is disabled and the persisted password is empty.
4. Authentication configuration errors are retried forever as if MESFlow were temporarily offline.
5. Start trace `QA-REAL-START-<uuid>` proves QA ownership but does not encode run ID or whether an anomaly was expected.
6. QA report does not reconcile `expected anomaly generated`, `expected anomaly detected`, `unexpected anomaly`, and `anomaly not detected` against `/api/session-exceptions`.

## Source traceability assessment

Reliable evidence already exists without migration:

- QA realistic soak: `start_request_id LIKE 'QA-REAL-START-%'`, plus `QAV65817-` fixture codes.
- Tutorial: request/note/PO/employee/device prefixes `TUT39-` / `TUT-`.
- Real/unclassified: neither trusted trace family.

Prefix-only employee naming should not be the primary classifier. The start request ID is the strongest current Session-level evidence. Future QA IDs should include a stable run ID and expectation marker, for example `QA-RUN-<run>-EXPECTED-FORGOT-<uuid>` or `QA-RUN-<run>-NORMAL-<uuid>`.

No migration is required to expose source in Session Exceptions because `work_sessions.start_request_id` and `note` already exist.

## Root causes

1. **QA persistent-state loss/reconciliation gap** left 20 normal QA Sessions orphaned and OPEN.
2. **QA credential/configuration handling** treats a permanent missing-password condition as transient MESFlow downtime and retries indefinitely.
3. **QA trace metadata is incomplete**: ownership is identifiable, but run/expected-anomaly intent is not.
4. **Tutorial seed narratives conflict with underlying data** for resolved zero quantity and ignored missing station, producing legitimate repeat occurrences.
5. **MESFlow UI does not surface reliable source evidence** already stored in the Session.

## Proposed fixes after audit

Priority order:

1. QA Center: recover/adopt live QA-owned OPEN Sessions into persistent state; never silently lose them on restart.
2. QA Center: fail/block clearly on missing production credentials instead of infinite offline retry.
3. QA Center: encode run ID and expected/normal intent in existing request/note fields and add anomaly reconciliation counters.
4. MESFlow: return normalized `data_source` and `source_trace_id` from trusted Session trace prefixes; do not alter detector rules.
5. MESFlow UI: show/filter `Thực tế`, `QA Test`, `Tutorial/Demo`, `Không xác định` based only on backend evidence.
6. Tutorial data: make synthetic resolved narratives and underlying values consistent, or explicitly mark them as historical-demo occurrences.

## Migration required

**NO.** Existing `start_request_id`, `finish_request_id`, `note`, fixture prefixes, and review fields are sufficient.

## Database changed

**NO.** This audit did not alter data. Existing anomalous Sessions were not cleaned or edited.

## Implementation after audit

The following changes were made only after the read-only evidence and classifications above were recorded:

- MESFlow `65.8.44.53` exposes `data_source` and `source_trace_id` from trusted request IDs/notes, and adds a source filter/badge to Session Exceptions. Unclassified data remains `UNKNOWN`; it is not guessed to be real-user data.
- QA Center `1.19.7` persists every successful start immediately, identifies untracked QA-owned OPEN Sessions without inventing a missing finish plan, treats missing credentials as a configuration failure, adds run/intent to future request IDs, and reports expected-generated/detected/unexpected/not-detected anomaly counters.
- No detection threshold or MESFlow Session business rule was weakened. No migration was added.
- The 20 existing orphan QA Sessions and all tutorial/history records remain unchanged.

## Validation evidence

- PostgreSQL integration: **9 passed**. Covers normal Session with no exception; valid short zero-quantity Session with no exception; intentional forgotten Session; overlap correction/history; QA missing-station detection/source; manual missing-station as unknown; ignore reason; completed history; repeat occurrence without overwriting old history.
- Focused MESFlow static/unit validation: **8 passed, 2 deselected**; Python compile and JavaScript syntax passed.
- QA Center focused validation: **12 passed, 1 deselected**; Python compile and installer shell syntax passed.
- Browser/Playwright Session Exceptions flow: **1 passed**; source filter, queue/history controls, and browser page errors checked.
- MESFlow version declarations agree on `65.8.44.53`; QA Center declarations agree on `1.19.7`.
- `git diff --check` passed.
- Application restart persistence is covered by PostgreSQL-backed workflow/history retrieval; production application was not restarted.
