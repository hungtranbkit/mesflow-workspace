# mesflow-web Batch 2 — Read-Only / Low-Risk UI

Date: 2026-08-15
Scope: Overview, Daily Dashboard, Production Trace migrated to React;
Business Audit (F6 POC) stabilized onto the now-shared component set. No
Master Data/CRUD, PO, Templates, Sessions, or Exception workflow migrated
in this batch. Zero backend files changed.

See also: `reports/FRONTEND_SEPARATION_AUDIT.md` (F0),
`reports/MESFLOW_WEB_POC.md` (F6), `docs/architecture/FRONTEND_BACKEND_SEPARATION.md`.

## PAGES MIGRATED

- `/app-v2/overview` — Tổng quan sản xuất
- `/app-v2/dashboard` — Dashboard theo ngày
- `/app-v2/production-trace` — Production Trace
- `/app-v2/business-audit` — Nhật ký nghiệp vụ (unchanged from F6, its
  internals refactored onto the shared components below — see "Business
  Audit" section)
- `/app-v2` index now redirects to `overview` (was `business-audit`),
  matching Classic UI's own first nav item.

## CLASSIC MODULES AUDITED

| Classic module | Lines | What it does |
|---|---|---|
| `pages/overview.js` | 24 (dense) | `renderOverview()`: merges `dashboard/overview` + `production-control`, client-side filter/sort/search, KPI tallies, repair plan, per-PO operation rows |
| `app.js:renderDashboard()` (+ helpers at top of file) | ~90 | Date/shift picker, KPI tiles, Operation time-progress panel (dual time/product bars), employee-day Gantt timeline, activity feed, attention table, 10s poll |
| `pages/production-trace.js` (`ProductionTrace` module) | 16 (dense) | PO picker, category-filtered cursor-paginated timeline, quantity reconciliation header, audit diff rendering for CHANGE events |
| `pages/session-detail.js` (`SessionDetailDrawer`) | 202 | Shared Session detail contract (`GET /api/session-management/<id>` + `GET /api/sessions/<id>/trace`), reused by Session Management/Exceptions in Classic — mesflow-web reuses the same two endpoints for its own shared, read-only drawer |

Per-page detail (filters, polling, permissions, drawers, navigation,
special formatting, and — critically — any business calculation found in
the JS) is recorded inline as code comments in each new file (cited below)
rather than duplicated here; every one references the exact Classic
function it mirrors.

### Business calculations found in Classic JS, and what happened to them

1. **Daily Dashboard's "current shift" default selection**
   (`currentShiftContext()`/`clockMinute()`/`hcmNowParts()` in `app.js`).
   The F0 audit (§8) flagged this as a possible business-logic violation.
   Batch 2 re-investigated against the actual backend surface: **no
   endpoint reports "the current shift"** — `GET /api/dashboard/shift`
   requires an explicit `shift_id` and returns correct real numbers for it
   regardless of how that id was chosen. This function only picks which
   shift/date a *picker* defaults to on first load; it has zero influence
   on any quantity, status, or permission the backend computes. Conclusion
   (correction to the F0 audit): this is UI default-selection logic, not a
   business rule, and does not need to move to Flask. It was ported
   verbatim into `src/features/dashboard/currentShift.ts` (same algorithm,
   documented as such) so both UIs agree on "what's current" by
   construction. No backend or Classic UI change made.
2. **Overview's PO/Operation merge** (`mergedPos`/`mergedOps` closures) —
   combining two already-computed read models (`dashboard/overview` +
   `production-control`) for display. Not a calculation; ported verbatim
   into `src/features/overview/hooks.ts`.
3. **Production Trace's CHANGE-event diff** (`auditDiff()`) — structural
   before/after key diff of already-fetched JSON for display, same
   category as Business Audit's own diff rendering. Ported verbatim into
   `src/features/production-trace/TraceEventCard.tsx`.
4. **Employee-day Gantt math** (position/duration formulas in
   `renderDashboard()`'s `timeline()` closure) — pure layout/visualization
   arithmetic (mapping timestamps to percentage positions), not a business
   rule. Reimplemented with the same core concept in
   `src/features/dashboard/EmployeeTimeline.tsx` (see "Functional parity"
   below for what was simplified).

No new business logic was found or moved to the backend in this batch;
no Flask/domain files were changed.

## SHARED COMPONENTS

Stabilized/added this batch (`src/components/`):

| Component | Status | Used by |
|---|---|---|
| `PageHeader`, `StatusBadge`, `DetailDrawer` (+ new `KvRow`/`DrawerSection` exports), `EmptyState`, `LoadingState` | Already existed (F6) | All pages |
| `ErrorState` | New | Overview, Dashboard, Production Trace, Business Audit, SessionDetail |
| `FilterBar`/`FilterField` | New | Business Audit's filter row (refactored to use it) |
| `DateFilter` | New | Business Audit, Daily Dashboard |
| `CopyValue` | New | SessionDetail's technical fields |
| `CategoryChips` | New — **promoted** from a Business-Audit-only component to shared, since Production Trace needed the identical single-select chip pattern with a different option list | Business Audit, Production Trace |
| `EventBadge` | New | Production Trace's timeline, SessionDetail's mini trace |
| `EntityLink` | New | Production Trace (session references open the shared drawer; PO/Operation render as plain text — no migrated detail view yet, never a dead link) |
| `Timeline` | New — generic grouped-or-flat event list shell | Production Trace (grouped by day), SessionDetail (flat mini trace) |
| `SessionDetail` (`SessionDetailDrawer` + `useSessionDetail` + `labels.ts`) | New — shared, **read-only** | Production Trace today; Session Management/Exceptions (F9/F10) will reuse this same component rather than building their own, per AGENTS.md's "one shared SessionDetail drawer" rule |

**Deliberately not built this batch** (no real use case yet — "do not
over-abstract"):
- `DataTable`/TanStack Table — every migrated page uses cards/rows, not a
  sortable/paginated grid. Revisit when Master Data/CRUD (next batch)
  needs one.
- `Pagination` — Production Trace uses Classic's own cursor "load more"
  pattern (`hasMore`/`next_before`), not page-number pagination; nothing
  in this batch needs the latter.
- `ConfirmDialog` — no mutating action exists in this batch (strictly
  read-only). Deferred to whichever batch first adds a destructive action.

`AuditFilters`/`BusinessAuditPage` (F6) were refactored in place to use
`FilterBar`/`FilterField`/`DateFilter`/`CategoryChips`/`ErrorState` instead
of their own one-off markup, and `AuditDetailDrawer` now uses the shared
`KvRow`/`DrawerSection` — no behavior change, verified by the existing
Playwright spec still passing unmodified.

## API MODULES

`src/api/` organized by domain, per this batch's instructions:

- `audit.ts` — renamed from `business-audit.ts` (F6) for naming
  consistency; no contract change, only the file name and its imports.
- `dashboard.ts` — `fetchOverview`, `fetchProductionControl`,
  `fetchWorkShifts`, `fetchShiftDashboard`. Types match the live API
  responses field-for-field (verified against a running backend with
  seeded data, not guessed from source reading alone).
- `production-trace.ts` — `fetchTrace` (PO/Operation/Session, cursor
  pagination), `fetchQuantityHistory`, `listProductionOrderOptions`.
- `sessions.ts` — `fetchSessionDetail`, `fetchSessionTrace` (the shared
  SessionDetail drawer's two calls).

All typed, no `any`. Central `apiFetch()` client (F6) unchanged.

## API CHANGES

**None.** Every endpoint consumed this batch already existed and was
already sufficient:
`/api/dashboard/overview`, `/api/production-control`,
`/api/settings/work-shifts`, `/api/dashboard/shift`,
`/api/production-orders/<id>/trace`, `/api/production-orders/<id>/quantity-history`,
`/api/production-orders` (list), `/api/session-management/<id>`,
`/api/sessions/<id>/trace`.

## OVERVIEW

Real functional parity: same two endpoints, same merge, same KPI set (no
new KPIs invented), same filters (search/PO/repair/priority/sort — all in
the URL, so a filtered view is a shareable/reloadable link), same repair
plan panel, same per-PO operation rows. `src/features/overview/`.

## DAILY DASHBOARD

Same one endpoint (`GET /api/dashboard/shift`), same KPI tiles, same
Operation time-progress panel (dual time/product bars, same three-state
color rule: slow/near/fast), same activity feed, same attention table.
Date/shift/employee-sort all live in the URL and get seeded from the
computed "current shift" default on first load. 10s auto-refresh,
matching Classic. `src/features/dashboard/`.

**Employee timeline — functional parity, not pixel parity** (explicitly
permitted by this batch's instructions): kept the core visualization
(session bars positioned on the real shift time axis, work/break/off-shift
shading, a live "now" marker) but dropped Classic's gap-highlight detection
and per-session color palette — polish, not the function. Worked duration
per employee now reads the backend's own `duration_seconds` per session
directly instead of re-deriving clipped work-window overlaps in the
browser, which is simpler and no less correct (the backend number was
already right).

## PRODUCTION TRACE

Same PO picker, same category filter set (7 categories + "Tất cả"), same
cursor-paginated timeline (`before`/`has_more`/`next_before`, "Tải thêm sự
kiện"), same quantity-reconciliation summary header, same CHANGE-event
diff rendering. `src/features/production-trace/`.

**New behavior beyond Classic** (explicitly requested by this batch):
Session references (`· Session #N`) are clickable and open the shared
`SessionDetailDrawer` in place — Classic only ever showed plain text there.
PO/Operation references remain plain text (no migrated detail view exists
for either yet — F8).

## BUSINESS AUDIT

Not rewritten. Internals refactored onto the newly-shared
`FilterBar`/`DateFilter`/`CategoryChips`/`ErrorState`/`KvRow`/
`DrawerSection` components (see "Shared components" above) with zero
behavior change — confirmed by its existing F6 Playwright spec passing
unmodified after the refactor. Raw JSON still only ever renders inside the
collapsed "Thông tin kỹ thuật" section.

## REPORTS

Not attempted this batch. `GET /api/reports/production-orders/<id>` and
`/api/reports/operations/<id>` exist and are stable, but nothing in
Classic UI's nav currently surfaces them as a standalone screen (they back
detail views inside pages not yet migrated) — there was no real "read-only
report screen" left to migrate this batch beyond Production Trace, which
already covers the same PO/Operation history in more depth. Candidates for
a future batch: KPI nhân viên / KPI Operation (`app.js`'s
`renderSimple('KPI nhân viên', '/api/kpi/employees')` and the Operation
equivalent) — both are already a flat read-only table today in Classic UI,
lowest-risk of what remains.

## FUNCTIONAL PARITY

Confirmed by side-by-side comparison against Classic UI on the same
backend/database (same seeded PO, same sessions): Business Audit list
matches row-for-row (see `reports/MESFLOW_WEB_POC.md`); Overview/Dashboard/
Production Trace render the same underlying numbers Classic shows for the
same PO (`PO-DEMO-1`) — screenshots in
`reports/screenshots/mesflow-web-batch2/`.

## PLAYWRIGHT

`mesflow-web/tests/e2e/{overview,dashboard,production-trace}.spec.ts`
(new) + `business-audit.spec.ts` (updated for the new `/app-v2` index
target). All against a real local backend + PostgreSQL with seeded demo
data (ProjectFlow local sandbox — see "Environment" below).

```
17/17 passed (1.1m)
```

Coverage per page: real render with live data, filter/date/category
changes reflected in the URL, browser Back (Production Trace's session
drawer), deep link reopening a drawer (Production Trace), 403/
permission-denied rendered in place (Overview, Business Audit), a real API
500 driving `ErrorState` + retry (Overview), 1920×1080 full render, 1366×768
with an automated `scrollWidth <= clientWidth` check, zero page/console
errors on every spec.

**Bug found and fixed during this pass:** the shared `loginViaForm()` test
helper clicked submit but didn't wait for the resulting navigation before
returning; a caller's immediate follow-up `page.goto()` could then race
and abort the in-flight login POST before the session cookie was set,
intermittently landing back on the login page. Fixed by waiting for
`page.waitForURL(/\/app-v2\/(?!login)/)` inside the helper. This was a test
bug, not an application bug — confirmed by the same login flow working
correctly under manual/scripted verification throughout this batch.

PAGE ERRORS: **0**
CONSOLE ERRORS: **0**

## 1920

Full-HD renders reviewed for all three new pages (see screenshots) —
correct information density, KPI tiles above the fold on Overview/
Dashboard, no unreadable/overlapping content.

## 1366

Automated `scrollWidth <= clientWidth` check passes on all three new
pages; visually reviewed (loaded-state screenshots in
`reports/screenshots/mesflow-web-batch2/`) — sidebar/content reflow
correctly, KPI grid drops to fewer columns, no text clipping.

## Environment used for verification

Local-only, no production involved: the same ProjectFlow local sandbox
from the F6 POC (`mesflow-app:71.0.0.5`, `127.0.0.1:18280`), still running
from that session. **Seeded real data this batch** (via direct API calls,
not fixtures baked into source): `POST /api/templates/demo/seed`, one PO
instantiated from the `DEMO-E10-FULL` template (`PO-DEMO-1`, 47
operations) and started, 5 work-sessions across 5 seeded demo employees
(mix of closed sessions with good/defect quantities and open/running
sessions) via the real `/api/work-sessions/start|finish` endpoints — real
application code paths, not database inserts. One genuine
`MISSING_STATION` session exception was produced naturally (no
`station_id` supplied) and is visible in the SessionDetail drawer
screenshot.

## BACKEND BUSINESS LOGIC MOVED

**None.** No business logic was found requiring a move to Flask this
batch (see "Business calculations found in Classic JS" above for the
audit and reasoning).

## DATABASE CHANGED

**None.** No migrations. The seeded demo data above lives in the isolated
ProjectFlow local sandbox database only (`runtime-projectflow-local/`),
never touched a real/deployed database.

## CLASSIC UI PRESERVED: YES

Zero files changed under `mesflow/app/mesflow/web/`. Classic UI's own
Overview/Dashboard/Production Trace/Business Audit pages were exercised
manually against the same sandbox+data during this batch and continue to
render correctly.

## PRODUCTION DEPLOYED: NO

## NEXT RECOMMENDED BATCH

**Master Data / CRUD** (Employees, Templates, Parts, Operations, Calendar,
Users/Roles, QR management — per the migration plan's F7). This is the
first batch that will need `DataTable` (sortable/paginated grids exist
here, unlike Batch 1/2's card-based pages), `ConfirmDialog` (delete
actions), and React Hook Form/Zod (create/edit forms) — build those
components when Master Data actually needs them, not before.
