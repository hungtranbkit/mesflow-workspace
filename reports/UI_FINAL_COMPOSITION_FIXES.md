# UI Final Composition Fixes

VERSION BEFORE: 71.0.0.24
VERSION AFTER: 71.0.0.25

Targeted fixes only, per explicit scope: no broad redesign, UI contract
**not** frozen. Five concrete composition defects fixed, all found from
real screenshots of the running 71.0.0.24 build, all re-verified with
DOM measurements (not visual impression) against the real deployed
71.0.0.25 build.

## TEMPLATES:

Page "Quy trình sản xuất mẫu". The three top-right actions (`+ Tạo
Template` / `Tạo Production Order` / `Công cụ`) previously sat in their
own `.page-header-actions` row, entirely empty of anything else, above
the search/filter row. Merged into the existing `MFUI.filterBar()` call
as its `actions` slot, so search and actions now render in **one** row:
`[Tìm nhanh…] ................. [+ Tạo Template] [Tạo Production Order] [Công cụ]`.
No standalone action-only row remains. `#tplSearch`, `#tplNew`,
`#tplCreatePO`, the `.template-tools` disclosure (Nhập từ Excel / Xuất
Excel / Nhân bản Template / Nạp dữ liệu mẫu / Xóa dữ liệu mẫu) are all
unchanged in wiring/behavior. At 1366px the row wraps cleanly (verified
screenshot below) — no orphan single-button row.

Also closes task item **8 (button hierarchy)**: while merging, an
initial attempt used an invented `.btn.secondary` class — caught before
shipping (`grep -c "\.btn\.secondary" ui.css` → 0, no such class exists
in this codebase) and corrected to plain `.btn`. This had the side
effect of actually fixing the hierarchy problem: `Tạo Production Order`
previously used `.btn.success`, which an existing `!important` rule
renders identical to `.btn.primary` (filled blue) — equally dominant as
the real primary action. Now `Tạo Production Order` and `Công cụ` both
render as plain `.btn` (bordered, secondary-weight), `+ Tạo Template`
alone is `.btn.primary` (filled).

## SESSION:

Page "Quản lý Session". `Làm mới` previously sat alone in its own
top-right `.page-header-actions` row. Moved into the existing filter
bar's `actions` slot (`MFUI.filterBar({..., clearId:'smReset',
actions:'<button class="btn" id="smReload">Làm mới</button>'})`), so the
filter row now ends with `... [Xóa bộ lọc] [Làm mới]`. No standalone
refresh row remains. `#smReload`, `#smReset`, and all filter fields
(`Ngày`/`PO`/`Nhân viên`/`Trạng thái`/search/`Thêm bộ lọc`) unchanged in
wiring. At 1366px the row wraps to two lines cleanly (date/PO/nhân viên
on line 1, trạng thái/search/thêm bộ lọc/xóa bộ lọc/làm mới on line 2) —
no isolated refresh row at either width.

## EXCEPTION:

Page "Trung tâm ngoại lệ". The full-width dark `.ec-command` hero strip
(`background:#10283f`, its own row, 56px tall) that only existed to
show "25 ngoại lệ / 23 mức cao/nghiêm trọng / Cập nhật …" was removed
entirely. `#ecSummary` (now `.ec-summary-compact`) moved to be a
trailing flex child inside the existing `<nav class="ec-tabs mf-tabs">`,
right-aligned on the same row as the 5 tabs:
`[Cần xử lý][Tất cả][Đã giải quyết][Đã bỏ qua][Lịch sử]   25 ngoại lệ · 23 mức cao/nghiêm trọng · Cập nhật HH:MM:SS`.
No full-width dark banner remains anywhere on the page. The
high/critical count now renders as a small semantic badge
(`.ec-severity-badge`, 22px pill, red-on-white) only when nonzero,
instead of colored inline text inside a hero — count/severity/updated
timestamp and all workflow semantics (tab counts, drawer, "Xem xét")
unchanged.

**Advanced filter (Business Audit's `.ba-advanced`, the actual owner of
the literal string "Bộ lọc nâng cao" in this codebase — Exception Center
itself has no such control)**: was `flex:1 1 100%`, rendering 1536.875px
wide — nearly the full row. Rewritten to a compact canonical disclosure
(`flex:0 0 auto`, bordered, canonical control height/padding), now
126.4px wide, sitting inline with the other filter fields instead of
consuming all remaining width.

## GANTT:

Page "Tiến trình sản xuất". Reproduced the reported overlap on the
actual running 71.0.0.24 build (not assumed fixed from a prior sticky
check) via `getBoundingClientRect()` measurements at 4 scroll depths
(0/300/700/1200px), both 1920×1080 and 1366×768.

**Root cause found**: `ui.css` has (had) three historical
`.workspace-header{height:…}` rules from different eras of the file; a
later "Industrial Soft-3D" polish-layer rule wins the cascade and
renders the Topbar at **68px**. Two page-specific sticky-offset values
were never updated to match and still assumed **72px**:
`.schedule-control-panel{--schedule-workspace-offset:72px}` (drives
`#scheduleStickyToolbar`'s sticky `top`) and, found as the same latent
bug elsewhere, `.overview-po-sticky{top:72px}` on the Overview page.

Confirmed by direct measurement on the frozen 71.0.0.24 files (restored
temporarily into the live container for a controlled before/after,
then put back — no separate infra spun up):

| | workspace-header bottom | sticky toolbar top | gap |
|---|---|---|---|
| BEFORE (71.0.0.24) | 68px | 72px | **4px** (scrolled content could show through) |
| AFTER (71.0.0.25) | 68px | 68px | **0px** |

Fix: both `--schedule-workspace-offset` and `.overview-po-sticky{top}`
changed from `72px` to `68px`, with a comment recording the root cause
for future maintainers.

**Post-fix verification** (real deployed 71.0.0.25 build,
`getBoundingClientRect()` at scrollY 0/300/700/1200, both viewports):
at every scrolled depth, `stickyToolbar.top === workspaceHeader.bottom
=== 68` exactly, and each `.schedule-po-head`'s top sits flush against
`stickyToolbar.bottom` with 0px gap and 0px overlap. Toolbar visible,
PO header visible, timeline labels unobstructed, Material Flow starts
below the Gantt correctly (`materialFlowTop` tracks scroll linearly,
never negative-overlapping toolbar bounds). Verified with vertical
scroll (all 4 depths) and horizontal scroll of `.gantt-wrap`
(`scrollLeft=300` and back), both 1920×1080 and 1366×768. Sticky
mechanics unchanged — only the offset value was corrected.

## KIOSK:

Page "Quản lý trạm Kiosk". The green "Online" status badge rendered
inside an oversized box (measured 48.234375×**39.703125**px) with the
text visually off-center. Root cause: `.kiosk-card-head{display:flex}`
uses the default `align-items:stretch`, which stretched the badge (a
flex item) to match its taller sibling (the 2-line title/subtitle
block); the badge itself had no internal flex-centering, so
`.badge{display:inline-block}` computed to `block` once blockified as a
flex child (correct, spec-mandated behavior — not a bug in itself) and
sat un-centered inside the stretched box.

Fix, scoped narrowly to avoid any blast radius on other pages' badges:
`.kiosk-card-head{align-items:flex-start}` (stop stretching) plus
`.kiosk-card-head .badge{display:inline-flex;align-items:center;
justify-content:center;flex:0 0 auto}` (self-size and center the text).
Result: 48.234375×**22**px — a tight pill matching the app's canonical
small-badge height (22px, same geometry as every other `.badge`/
`.status-pill` in the app), vertically aligned with the kiosk title,
consistent across all cards. Color/state logic (`online`/`offline`/
severity classes) untouched.

## BUTTON NORMALIZATION:

- Templates: `Tạo Production Order` and `Công cụ` normalized from
  effectively-primary (`.btn.success`, visually identical to
  `.btn.primary` via an existing `!important` rule) to plain `.btn`
  (bordered/secondary), so `+ Tạo Template` reads as the single
  dominant primary action.
- Business Audit `.ba-advanced summary`: rewritten to canonical control
  geometry — `min-height:36px` (`var(--control-height)`), `border-radius`
  from `var(--radius-control)`, bordered surface, no pill shape (it's a
  disclosure control, not a filter chip).
- Verified (measured, not assumed): Exception Center's `Áp dụng`
  (`#ecApply`) and `Xem xét` (`.ec-review`) were **already** canonical —
  36px/32px height, `var(--radius-control)` — before this pass. No
  change was needed or made to these two; any prior "too rounded"
  impression traced to visual context from the now-removed dark hero
  banner, not the buttons themselves. No semantic color changed
  anywhere.

## BEFORE/AFTER MEASUREMENTS:

All measured via Playwright `getBoundingClientRect()` at 1920×1080
unless noted, restoring the frozen 71.0.0.24 static files into the live
container for the BEFORE pass, then restoring the fixed files (both
confirmed by `grep -c ec-summary-compact ui.css` returning 0/4
respectively) — no parallel infrastructure touched.

| Metric | BEFORE | AFTER |
|---|---|---|
| Template standalone action row height | 36px (own row, 88–124px) | 0px — merged into filter row (single row, 83.15625px tall, search+3 buttons share `top:122.15625`) |
| Session standalone refresh row height | 36px (own row, 88–124px) | 0px — `#smReload` shares `top:122.15625` with `#smDate` in the same filter row |
| Exception summary row height | 56.015625px (`.ec-command` dark strip, its own row) | 0px as a separate row — folded into the 44.578125px tab row as a trailing flex child |
| Business Audit advanced filter width | 1536.875px | 126.40625px |
| Kiosk Online badge size | 48.234375 × 39.703125px | 48.234375 × 22px |
| Gantt: workspace-header bottom vs. sticky toolbar top | 68px vs. 72px (4px gap) | 68px vs. 68px (0px gap) |

## 1920x1080:

Captured and inspected for all 5 pages against the real deployed
71.0.0.25 build: Templates (`after-templates-1920x1080.png`), Session
Management (`after-session-management-1920x1080.png`), Exception Center
(`after-session-exceptions-1920x1080.png`), Production Schedule
(`after-production-schedule-1920x1080.png` +
`after-schedule-scrolled700-1920x1080.png`), Kiosk Management
(`after-kiosk-management-1920x1080.png`). All under
`reports/screenshots/final-composition-fixes/`. Every target defect
confirmed fixed by direct visual inspection, matching the DOM
measurements above.

## 1366x768:

Same 5 pages + scrolled Gantt captured at 1366×768
(`after-*-1366x768.png`, `after-schedule-scrolled700-1366x768.png`).
Templates and Session Management wrap cleanly to 2 rows with no orphan
action-only row; Exception Center keeps tabs+summary on one row with
the filter row compact below it; Kiosk badges stay tight pills; Gantt
scrolled view shows the PO header and timeline labels fully visible
directly under the sticky toolbar with no overlap.

## PAGE ERRORS:

2 occurrences of `TypeError: Cannot read properties of null (reading
'classList')` at `app.js:982`, reproduced identically on both the
preview container and the real deployed 71.0.0.25 build. **Confirmed
pre-existing and out of this task's scope** — `git diff` shows this
exact line untouched by any of today's edits. Root cause:
`renderSessionManagement()` registers a page-scoped
`document.addEventListener('keydown', …)` handler that closes over
`el('smModal')` but is never removed on navigation; if a user visits
Session Management, navigates to a different page (replacing
`#smModal` in the DOM), and later presses Escape anywhere, the orphaned
listener throws. Not one of the 13 listed defects, not caused by this
pass's changes, not fixed here per "only fix the issues listed below."

## CONSOLE ERRORS:

None across all 5 target pages, both viewports (0/0), confirmed on the
real deployed 71.0.0.25 build via the same Playwright pass that
triggered the page errors above (those are `pageerror` events at
`app.js:982`, not `console.error` output — 0 actual console errors).

## OVERFLOW:

0px horizontal overflow (`document.documentElement.scrollWidth -
clientWidth`) on Templates, Session Management, Exception Center,
Production Schedule, Kiosk Management — both 1920×1080 and 1366×768, on
the real deployed 71.0.0.25 build.

## FUNCTIONAL SMOKE:

44/44 checks pass (22 checks × 2 viewports) on the real deployed
71.0.0.25 build: Templates (search, create-template button present,
create-PO button present, tools disclosure opens), Session Management
(refresh present/works, clear-filters present/works), Exception Center
(5 canonical tabs, tab switch, filter apply, view-exception drawer),
Production Schedule (refresh present/works, Gantt present, Material
Flow present, horizontal scroll, PO selection), Kiosk Management
(search present/works, status filter works, refresh works, cards
present). Plus the pre-existing 39-check composition regression suite
(Production Order, Exception Center, Production Trace, Business Audit,
Production Schedule incl. `ps-sticky-toolbar-pinned top=68`, Kiosk
Management, Guidance) — 39/39 pass, re-run against the real deployed
build. `pytest tests/test_v71_ui_foundation.py tests/test_web_ui.py` —
7/7 passed.

## LOCAL BUILD:

`scripts/build-release.sh --bump` → `IMAGE RELEASE PASS`. Version
71.0.0.24 → **71.0.0.25**. Image `mesflow-app:71.0.0.25`, digest
`sha256:b9c2ac9462024afb2577a0dd428b1335ff3ebac1f11bddc26d362c170801e78f`,
schema `0037_v72_audit_operations_separation`, package
`artifacts/releases/71.0.0.25/MESFlow_71.0.0.25.deploy.zip`.

## LOCAL DEPLOY:

Deploy Agent `POST /agent/api/release-manager/deploy-local
{"version":"71.0.0.25"}` → job `success`. Steps: backup
(`source_20260817_033734_a3347f18`) → stage → install → restart ("MES
Docker stack started; PostgreSQL data preserved") → health ("Version
71.0.0.25 and health verified") → rollback skipped (not required).
`from_version: 71.0.0.24`.

## LOCAL HEALTH:

`GET /api/system/health` (via Deploy Agent status) → `{"ok": true,
"status": "healthy", "version": "71.0.0.25", "postgres_version":
"17.10", "schema_version": "72.0.0.0"}`. Container confirmed running
`mesflow-app:71.0.0.25` (healthy) via `docker ps`.

POSTGRES RESTARTED: NO
PRODUCTION TEST TOUCHED: NO
PRODUCTION TOUCHED: NO
