# Business Audit Trail Redesign — "Nhật ký nghiệp vụ" for Normal Managers

Date: 2026-08-14
MESFlow version: 71.0.0.4 → 71.0.0.5 (source tree only; see PRODUCTION DEPLOYED note)
No schema migration — presentation-only, interprets existing `audit_logs` evidence without rewriting it (section 14).

Scope: `app/mesflow/domain/audit_presentation.py` (new), `app/mesflow/db/repositories/analytics.py` (`AuditRepository`), `app/mesflow/web/analytics.py` (`/api/audit-logs`), `app/mesflow/web/static/app.js` (`renderBusinessAudit()`), `app/mesflow/web/static/ui.css`.

---

## ACTIONS DISCOVERED:

Audited every `AuditRepository().log(...)` and `record_audit(...)` call site in the actual codebase (not assumed — grepped `mesflow/web/*.py` and `mesflow/db/repositories/*.py`), including a discovery that surfaced two **parallel** exception systems both still present in real historical data:

- **Live today**: `SESSION_STARTED`, `SESSION_FINISHED`, `SESSION_EDIT`, `SESSION_ADJUST` (execution.py); `EXCEPTION_ACKNOWLEDGED`, `EXCEPTION_RESOLVED`, `EXCEPTION_IGNORED`, `EXCEPTION_AUTO_IGNORED` (exceptions.py, the V67 "Exception Center" — `exception-center.js` is the page actually wired into the menu today, loaded *after* and deliberately overriding the older `session-exceptions.js`); `WORK_SHIFTS_REPLACE`, `SESSION_EXCEPTION_WORKFLOW_UPDATE`, `KPI_SNAPSHOT`, `KIOSK_EVENT_RESOLVE` (analytics.py); `OPERATION_CANCEL` (master_data.py); `KIOSK_APPROVE`, `KIOSK_STATUS_CHANGE`, `PRODUCTION_STATE_RECONCILE`, `QC_START`, `QC_COMPLETE` (execution.py route); `LOGIN_SUCCESS`, `LOGIN_FAILED` (app.py, added in the prior audit-separation task).
- **Legacy, superseded UI but real historical rows**: `SESSION_EXCEPTION_WORKFLOW_UPDATE` is exactly the fixture named in this task — confirmed it's the *older* `session_exception_reviews` workflow (`session-exceptions.js`), still present in real audit history even though the live "Trung tâm ngoại lệ" page now uses the newer `exception_records` model. Per section 14, both are catalogued and presented correctly — neither was rewritten or deleted.

20 action codes catalogued in total. A unit test (`test_every_real_audit_write_call_site_action_is_catalogued`) greps the source tree itself for every literal `action='...'` write and fails if a future call site is ever added without a catalog entry — this is a standing guard, not a one-time count.

## ACTIONS TRANSLATED:

All 20, each with a `{label, category}` entry in `ACTION_CATALOG` (`mesflow/domain/audit_presentation.py`). Examples matching the task exactly: `SESSION_EDIT` → "Chỉnh sửa Session", `SESSION_EXCEPTION_WORKFLOW_UPDATE` → "Xử lý Session bất thường", `WORK_SHIFTS_REPLACE` → "Cập nhật lịch làm việc". Unknown/future action codes never blow up or show blank — `action_label()` falls back to a Title-Cased readable guess from the snake_case code (e.g. `SOME_BRAND_NEW_ACTION` → "Some Brand New Action") while `row['action']` (the real code) stays fully visible in the technical section, per section 2's explicit fallback requirement.

Centralized in **one Python module**, not scattered JS switch statements — the frontend (`app.js`) only renders the already-translated `presentation` object the API returns; no per-page duplicate label maps were added.

---

## FIELD TRANSLATIONS:

`FIELD_LABELS` in the same module — every field named in the task (`started_at`→"Thời gian bắt đầu", `ended_at`→"Thời gian kết thúc", `good_qty`→"Sản phẩm đạt", `defect_qty`→"Sản phẩm lỗi", `rework_qty`→"Lỗi sửa được", `status`→"Trạng thái", `employee_id`→"Nhân viên", `operation_id`→"Công đoạn", `station_id`→"Trạm", `assigned_to`→"Người xử lý", `workflow_status`→"Trạng thái xử lý", `resolution`→"Kết quả xử lý", `note`→"Ghi chú") plus others discovered during the audit (`reason`, `severity`, `exception_type`/`exception_code`, `production_order_id`, `part_id`, `session_id`, `device_uuid`, `code`/`name`/`anchor_start`/`anchor_end`/`cross_midnight`/`target_minutes`/`active` for work shifts). No snake_case field name is ever shown in the normal card/drawer view — verified by test.

## ENUM TRANSLATIONS:

`ENUM_LABELS`, **namespaced by domain** — a real problem found during the audit: `work_sessions.status` (OPEN/CLOSED) and `exception_records.status` (OPEN/ACKNOWLEDGED/RESOLVED/AUTO_IGNORED/MANUAL_IGNORED) are the *same column name* with *completely different value universes* (`OPEN` means "Đang mở" on one, "Cần xử lý" on the other). Flattening them into one dict would have mistranslated one of the two. Domains implemented: `work_session_status` (OPEN→Đang mở, CLOSED→Đã kết thúc, CANCELLED→Đã hủy), `exception_status` (OPEN→Cần xử lý, ACKNOWLEDGED→Đã xác nhận, RESOLVED→Đã giải quyết, AUTO_IGNORED→Tự động bỏ qua, MANUAL_IGNORED→Đã bỏ qua), `workflow_status` (NEW→Mới, IN_PROGRESS→Đang xử lý, RESOLVED→Đã xử lý, IGNORED→Đã bỏ qua), `exception_code` (the task's own example: OPEN_TOO_LONG→Session mở quá lâu, plus OVERLAP/ZERO_QTY_LONG/MISSING_STATION/INVALID_TIME discovered from the actual detection SQL), `exception_type` (V67 Exception Center's own codes — reused the *exact* Vietnamese wording already live in `pages/exception-center.js`'s own `labels` map, so the two screens never disagree), `resolution` (reused the exact wording from the exception workflow's own `<select>` options), `severity`. An unrecognized enum value never crashes — falls back to the raw text.

---

## SESSION_EDIT:

Real shape confirmed by reading `execution.py`'s `edit_session()` — `details_json` = `{'reason', 'old': <full work_sessions row>, 'new': <full work_sessions row>}`. Diffed with `diff_fields()` restricted to real business columns (`employee_id/operation_id/station_id/status/started_at/ended_at/good_qty/defect_qty/rework_qty/note/device_uuid`) — `updated_at`/`id`/`row_version`/request-id columns are never treated as a business change. For the task's own example (only `started_at` differs by 7 seconds, everything else — including `updated_at` — identical or noise), the redesigned view shows **exactly one** changed field:

> **Chỉnh sửa Session #577**
> admin đã chỉnh sửa Session #577 — Phạm Xuân Dung · ĐỘT THÂN THÙNG RÁC
> Thời gian bắt đầu: 09/08/2026 17:39:07 → 09/08/2026 17:39:00
> Lý do: ok

When *no* business field actually changed (a real, tested case — "SESSION_EDIT #580"-style), the card shows a plain "Không có trường nghiệp vụ nào thay đổi." note instead of a confusing empty diff. `[Xem Session]` opens the existing `SessionDetailDrawer` (reused, not reinvented); `[Chi tiết thay đổi]` opens the new audit drawer in place.

## EXCEPTION_WORKFLOW:

Both the legacy `SESSION_EXCEPTION_WORKFLOW_UPDATE` and the live `EXCEPTION_ACKNOWLEDGED/RESOLVED/IGNORED/AUTO_IGNORED` transitions get dedicated presenters. Single-session case renders exactly the task's example:

> Xử lý Session bất thường
> admin đã nhận xử lý Session #572
> Vấn đề: Session mở quá lâu · Trạng thái: Đang xử lý · Người xử lý: admin

Bulk case (`items.length > 1`) renders "Đã cập nhật xử lý N Session bất thường" with an expandable affected-sessions list in the drawer (session id + resolved employee/operation name each). `OPEN_TOO_LONG:0` and `exception_fingerprint` are never shown in the normal view — verified by test (`assert 'exception_fingerprint' not in dump` against the full `presentation` JSON, both unit and live-HTTP).

## WORK_SHIFT:

`WORK_SHIFTS_REPLACE` details only ever contain the *resulting* shift list (no "before" was ever captured by the original write call — confirmed by reading the route), so this is a resulting-configuration summary, not a diff:

> Cập nhật lịch làm việc
> admin đã cập nhật cấu hình ca làm việc
> Ca ngày: 07:30 – 17:00 · Ca tối: 18:00 – 03:00 (or 00:00, matching whatever the real current interval data says — verified both a same-day and a genuinely cross-midnight interval render correctly via `% 24` wrapping, not naively capped)

No `interval_type`/`start_minute`/raw shift JSON in the normal view — confirmed by test on both a synthetic fixture and a real HTTP round-trip against a live `PUT /api/settings/work-shifts` call.

---

## ID ENRICHMENT:

`AuditRepository._enrich()` batch-resolves every employee/operation/station/session reference across an entire page of audit rows in **at most 4 extra queries total** (`work_sessions`, `employees`, `operations`, `stations`, each `WHERE id = ANY(%s)`) — never one query per row. Proven, not assumed: `test_enrichment_uses_bounded_query_count_not_n_plus_1` monkeypatches `fetch_all` to count real query calls while presenting 20 rows across 6 different sessions/employees/operations and asserts the total stays ≤ 5 (1 page query + 4 batched lookups). `employee_id`/`operation_id`/`station_id` diff entries resolve to real names ("Phạm Xuân Dung", "ĐỘT THÂN THÙNG RÁC") instead of bare IDs; an ID outside the batch-fetched map (never happens for real page data, but tested defensively) falls back to `#<id>` rather than crashing.

## DIFF ENGINE:

`diff_fields(old, new, enum_domains=..., include=...)` in the same module — generic, reused by both `SESSION_EDIT`/`SESSION_STARTED`/`SESSION_FINISHED` and the `EXCEPTION_*` transitions (not two separate implementations). Supports string/number/boolean/null/datetime/simple-array-or-object per section 11 (typed as `text`/`number`/`boolean`/`datetime`/`complex` respectively); complex nested values never render inline — they point to the technical section instead of pseudo-flattening. `updated_at`/`row_version`/`id`/request-id columns are always excluded as noise; every other field difference is always surfaced — a dedicated test (`test_diff_engine_never_hides_a_real_business_change`) asserts a real quantity change is never silently dropped.

## TIMEZONE:

No new timezone logic was written. `changes[].type === 'datetime'` entries pass the *raw* ISO timestamp through unmodified from the backend; the frontend formats them with the exact same `fmt()`/`HCM_DATE_TIME` (`Intl.DateTimeFormat('vi-VN', {timeZone: MESFLOW_TIMEZONE, ...})`) already used everywhere else in the app for `created_at` — the single existing project convention, not a second one. `2026-08-09T10:39:07.380249+00:00` renders as `09/08/2026 17:39:07`; the raw ISO string is still visible verbatim in the technical section.

---

## RAW JSON NORMAL VIEW: NO

## RAW EVIDENCE PRESERVED: YES

`AuditRepository._enrich()` returns `details_json`/`before_json`/`after_json` as parsed objects **alongside** (never instead of) `presentation` — every audit_logs column reaches the browser untouched. The card/list view never renders them. The detail drawer's collapsed "Thông tin kỹ thuật" `<details>` (closed by default, same pattern already used by `SessionDetailDrawer`'s own `technicalDetailsHtml()`) shows `action`, `entity_type`, `entity_id`, `correlation_id`, `source`, and the full raw `details_json`/`before_json`/`after_json` as formatted JSON — verified by Playwright: collapsed by default, page text before expanding contains no raw JSON fragment, and after clicking it open the full raw payload is genuinely present and non-empty.

No secrets: this task only *reads* existing evidence — the earlier audit-separation work already confirmed no password/token ever gets written into `audit_logs`.

---

## TESTS:

**Unit** (`tests/test_v74_audit_presentation_unit.py`, pure — no DB, runs directly on host Python too): **19 passed.** Covers the real SESSION_EDIT #577/#580 shapes, single/bulk SESSION_EXCEPTION_WORKFLOW_UPDATE, WORK_SHIFTS_REPLACE (including a genuine cross-midnight span), the catalog-completeness guard, unknown-action fallback, category taxonomy, field/enum translations, the domain-collision case (`status` meaning two different things), the diff engine's type coverage and noise-ignoring behavior, reference resolution, and a caught-and-fixed real bug (see below).

**Integration** (`tests/integration/test_v74_audit_presentation.py`, real Postgres + real HTTP against `mesflow-test-api`): **6 passed.** SESSION_EDIT and SESSION_EXCEPTION_WORKFLOW_UPDATE seeded through real `seeded_factory` employee/operation/session rows and asserted over the actual `/api/audit-logs` response; WORK_SHIFTS_REPLACE round-tripped through the real `PUT /api/settings/work-shifts` endpoint; category filter correctness; unknown category returns empty, not an error; the N+1 query-count bound.

**Regression**: full session-relevant selection (V69/V71/V72/V73/V74 unit+integration together): **107 passed, 0 failed.** Full repo `tests/` (445 tests): **401 passed, 68 failed** — the exact same pre-existing failure set already root-caused and documented in `reports/MONITORING_OWNERSHIP_CUTOVER.md` (stale hardcoded version strings, pre-V71-modularization assumptions, migration-0026 shift-data drift) — zero new regressions.

**Real bug found and fixed during this task** (not pre-existing): a `LOGIN_FAILED` audit row showed "Lý do: invalid_credentials" **twice** — once as the dedicated reason line, once as a generic key/value pair, because the generic fallback presenter's "show every remaining field" loop didn't know `reason` already had its own section. Found visually in the first Playwright screenshot, fixed in `_present_generic()` (exclude `reason` from the generic extra-fields loop), covered by a new regression test, and re-verified visually.

## PLAYWRIGHT:

`tests/e2e/business-audit-v74.spec.js`, 1920×1080, run against a fresh isolated Docker Compose stack: **2/2 passed.**
1. Seeds a real `WORK_SHIFTS_REPLACE` row via a genuine read-then-rewrite-same `PUT /api/settings/work-shifts` (never mutates the actual shift config any other test might depend on). Asserts: cards visible; no raw-JSON-shaped text and no `exception_fingerprint`/`details_json` substring anywhere in the initial list; every action badge is a translated label, never a bare `SNAKE_CASE` code; opens the detail drawer; `Thông tin chung` section present; the "Thông tin kỹ thuật" `<details>` is collapsed by default and the list body contains no raw JSON before it's expanded; expanding it reveals real, non-empty raw evidence; closing the drawer (Escape) preserves the active category filter and the list stays rendered; zero horizontal overflow at 1920×1080.
2. Category chips render exactly the 9 expected Vietnamese labels (Tất cả/Session/Sản lượng/PO/Công đoạn/Lịch làm việc/Nhân viên/Xử lý bất thường/Quản trị), filtering works, stays visually correct.

Screenshots captured and visually reviewed (`test-results/v74-business-audit-list.png`, `-drawer.png`, `-category-filter.png`): card list renders cleanly with real accumulated data (WORK_SHIFTS_REPLACE, SESSION_ADJUST with a "Xem Session" button, LOGIN_SUCCESS/LOGIN_FAILED under "Quản trị") — Vietnamese throughout, correct category color-coded badges, no raw JSON anywhere in the list; the drawer shows "Thông tin chung → Ca làm việc → Nguồn → Thông tin kỹ thuật (expanded on demand, full raw JSON present)" exactly matching the section 10 layout.

## PAGE ERRORS: 0

## CONSOLE ERRORS: 0

---

## FILES CHANGED:

- **New**: `app/mesflow/domain/audit_presentation.py` — the catalog/diff/presentation module.
- **New**: `tests/test_v74_audit_presentation_unit.py`, `tests/integration/test_v74_audit_presentation.py`, `tests/e2e/business-audit-v74.spec.js`.
- `app/mesflow/db/repositories/analytics.py` — `AuditRepository.list()` gained a `category` filter param; new `_enrich()`/`_safe_json()` batched-enrichment step.
- `app/mesflow/web/analytics.py` — `/api/audit-logs` passes through `category`; stale comment fixed ("Nhật ký hệ thống" → "Nhật ký ứng dụng", matching the earlier rename).
- `app/mesflow/web/static/app.js` — `renderBusinessAudit()` fully rewritten: category filter chips, redesigned cards (summary → context → changes preview → extra → reason → actions), new `openAuditDrawer()` using the existing shared `MFUI.openDrawer()`/`kvGrid()` primitives (not a new UI system).
- `app/mesflow/web/static/ui.css` — old flat `.business-audit-row` replaced with `.ba-card`/`.ba-categories`/`.ba-chip`/`.ba-action-badge` (+ 8 category color variants)/`.ba-changes-preview`/`.ba-extra`/`.ba-raw`, styled consistently with the app's existing `--brand`/`.badge`/`.drawer-*` conventions.

## MIGRATION: none (no schema change — read-only interpretation of existing `audit_logs`/`before_json`/`after_json`/`details_json`, per section 14's explicit "do not modify audit history to make it prettier")

## PRODUCTION DATA MUTATED: NO

Verified: `mesflow-postgres` `StartedAt=2026-08-12T04:18:08.161154558Z`, `RestartCount=0` — unchanged, reconfirmed at the end of this task. All testing happened against a disposable, fresh `mesflow-p8` Compose stack, torn down afterward along with its throwaway images.

## PRODUCTION DEPLOYED: NO

This task never ran a build or deploy against production. Source-tree version bumped to `71.0.0.5` only. As in the two prior reports this session: real `mesflow-app` was again observed to have moved (now `71.0.0.4`) by something outside this conversation during this task's work — not by any command run here; `mesflow-postgres`/`mesflow-nginx`/`mesflow-qa-center`/`mesflow-deploy-agent` remain unchanged.
