# mesflow-web Batch 3 — Master Data / CRUD

Date: 2026-08-15
Scope: Employees, Templates (+ Parts/Operations tree), Calendar/Work
Shifts, Users/Roles/Permissions, QR Management, Equipment migrated to
React with full CRUD parity. Production Orders, Sessions, Session
Exceptions, Kiosk, Application Logs, Gantt/Material Flow, Tutorials are
**not** in this batch — see "Next batch" at the end. Zero backend files
changed; zero database migrations.

See also: `reports/FRONTEND_SEPARATION_AUDIT.md` (F0),
`reports/MESFLOW_WEB_BATCH2_READONLY.md` (Batch 2),
`docs/architecture/UI_MIGRATION_STATUS.md` (parity matrix, updated).

## PAGES MIGRATED

| Page | Route | Classic module audited |
|---|---|---|
| Employees | `/app-v2/employees` | `renderEmployees()`/`employeeModal()` (app.js) |
| Templates (list) | `/app-v2/templates` | Template list portion of `renderTemplates()` (app.js) |
| Templates (Part/Operation tree) | `/app-v2/templates/:id` | `templateUi` tree editor (app.js) + `TemplateTreeRepository` (backend, read directly) |
| Calendar / Work Shifts | `/app-v2/calendar` | `renderWorkingCalendar()` (app.js) |
| Users | `/app-v2/users` | `renderUsers()`/`userModal()` (app.js) |
| Roles & permissions | `/app-v2/roles` | `renderRolePermissions()` (app.js) |
| QR Management | `/app-v2/qr` | `renderQrPrintCenter()` (pages/qr-print.js) |
| Equipment | `/app-v2/equipment` | generic resource CRUD (`resources.equipment` in app.js) |

## APIs used (all pre-existing, zero contract changes)

- Employees: `GET/POST /api/employees`, `GET/PATCH/DELETE /api/employees/<id>`
- Templates: `GET/POST /api/templates`, `GET/PATCH/DELETE /api/templates/<id>`, `GET/PUT /api/templates/<id>/tree`, `GET /api/templates/<id>/validate`, `POST /api/template-parts/upload-drawing`
- Calendar: `GET/PUT /api/settings/work-shifts`
- Users/Roles: `GET/POST /api/users`, `PATCH /api/users/<id>`, `POST /api/users/<id>/reset-password`, `POST /api/auth/change-password`, `GET /api/roles`, `PUT /api/roles/<code>/permissions`
- QR: `GET /api/qr-labels`, `GET /api/qr-image`
- Equipment: `GET/POST /api/equipment`, `GET/PATCH/DELETE /api/equipment/<id>`

## Permissions recorded (per screen, verified against auth.py's request→permission table)

- Employees: `employees.view` / `employees.edit`
- Templates: `template.view` / `template.edit`
- Calendar: `calendar.view` / `calendar.edit`
- Users: `users.view` / `users.manage`; Roles: `roles.manage`
- QR: `qr.view` (read-only screen, no edit permission needed)
- Equipment: `equipment.view` / `equipment.edit`

All UI-side (`src/app/permissions.ts`'s `EDIT_PERMISSION` map, new this
batch) — every one independently re-checked server-side per request
regardless of what the UI hides. Verified explicitly: a mocked
under-permissioned session gets an in-place "Không có quyền truy cập" on
Employees/Templates/Users (not a redirect); a cookie-less request to
`POST /api/users` gets a real `401` from the backend itself (Playwright
`users.spec.ts`), proving enforcement isn't only client-side.

## Validation rules recorded (server-authoritative; client mirrors are fail-fast UX only)

- Employees: `employee_no`/`name` required (`EmployeeRepository.create`/`update`); `active` is *derived* from `employment_status` server-side, not a separate field — there is no standalone "activate/deactivate" control in either UI, matching Classic exactly.
- Templates: full-tree validation is 100% server-side (`TemplateTreeRepository.replace_tree`/`.validate`) — duplicate part codes, missing names, negative time values, dependency cycles, unknown `input_source_code`. The React editor's own inline checks (required fields, non-negative numbers) are the same fail-fast-UX pattern used everywhere else in this project; every save still round-trips through the real validator and surfaces its message verbatim on rejection.
- Calendar: interval overlap/gap preview is computed client-side for immediate feedback (ported from Classic's `analyzeIntervals()`), but `PUT /api/settings/work-shifts` re-validates the entire payload server-side regardless (see `replace_work_shifts_setting` in analytics.py) — confirmed by a dedicated Playwright test that changing an interval mid-form correctly blocks Save via the client preview.
- Users: password rules (`>=8` chars, letter+digit) mirrored from `_password_error()`; self-lockout guard (can't deactivate/demote your own logged-in account) enforced server-side in `update_user`, mirrored in the form as a disabled control with an explanatory hint.

## Special browser behavior recorded

- QR printing: `window.print()` + a dedicated `.qr-print-sheet` stylesheet, ported **verbatim** (same class names, same mm-based label sizing) from Classic UI's `ui.css` into `mesflow-web/src/index.css`, so printed output is pixel-identical between the two UIs. Verified the print-sheet DOM builds correctly for a selection (Playwright asserts `.qr-print-label` count).
- Template drawing upload: `POST /api/template-parts/upload-drawing` (multipart) — implemented with a plain hidden `<input type="file">` triggered by a styled button, matching the "no fragile auto-submit-only path" spirit already required of Deploy Agent's upload UI (AGENTS.md).

## Implementation notes

- **Templates decomposition**: per this batch's explicit instruction ("avoid one giant form containing the whole Template graph"), the tree editor is Template page → Part sections → Operation add/edit via a shared `DetailDrawer`, instead of Classic's single large `templateUi` client object. Edits are staged locally (`features/templates/draft.ts`) and sent as one full-replace `PUT .../tree` on explicit "Lưu thay đổi" — the same wire contract Classic's own `saveTree()` uses, just a clearer component boundary. Verified live: added a real Part + Operation, saved, confirmed via a direct API read that both persisted with correct `part_id` linkage, then cleaned up the same way.
- **RolesPage** is its own route (`/app-v2/roles`) instead of Classic's in-place content swap (`AppNav.push` + re-render) — functionally identical navigation (a "← Người dùng" back action), just a real URL per this project's routing rule (F4).
- Role names/descriptions shown in Users/Roles come from the backend's own `GET /api/roles` (`name`/`description` fields) instead of Classic's hardcoded `userRoleText()`/`userRoleHint()` JS dictionaries — same information, sourced from the backend instead of duplicated, consistent with the project's "backend is the source of truth for labels" pattern established in Batch 1/2 (Business Audit, audit categories).

## SHARED COMPONENTS (new this batch)

`DataTable` (config-driven `<table>`, used by every list in this batch),
`ConfirmDialog` (Radix AlertDialog-backed), `FormRow`, `Section`,
`ui/select.tsx`, `ui/checkbox.tsx`, `ui/textarea.tsx`, `ui/alert-dialog.tsx`.
`AuditFilters`/`BusinessAuditPage` were **not** touched further this batch
(already refactored onto shared components in Batch 2).

**Bug found and fixed while building `ConfirmDialog`**: `AlertDialogContent`
initially reused `DetailDrawer`'s `DialogOverlay`, which is built on
`@radix-ui/react-dialog`'s context — but `AlertDialog` is a *separate*
Radix primitive with its own context, so mounting it crashed with
`` `DialogOverlay` must be used within `Dialog` ``. Fixed by giving
`AlertDialogContent` its own overlay built on
`@radix-ui/react-alert-dialog`'s primitives (same visual styling). Caught
immediately by the first live Employees delete test, before it reached any
committed report.

**Bug found and fixed in the Calendar shift editor**: the interval
overlap/gap preview used `useMemo` keyed on `watch('intervals')`'s return
value. React Hook Form does not guarantee a new array reference on every
render for a `watch()`'d array whose nested fields changed via
`useFieldArray` + `register()` — it can mutate the same object in place —
so `useMemo`'s reference-equality check silently kept serving a **stale**
validation result while the input itself displayed the new value. A
Playwright test (`calendar.spec.ts`, overlap-detection case) caught this:
the UI showed "Lịch liên tục, không trùng và sẵn sàng lưu." for an interval
that visibly overlapped its neighbor. Fixed by dropping the premature
`useMemo` — the computation is a handful of array items and is cheap
enough to run every render unconditionally; confirmed correct afterward
both via a scripted reproduction and the full Playwright run. This is
recorded here because it is a *correctness* bug a screenshot-only review
would not have caught (the stale text looked plausible) — only a real
interaction-then-assert test surfaced it.

## API CONTRACT CHANGES

**None.**

## BACKEND BUSINESS LOGIC MOVED

**None.** No calculation was found in the audited Classic JS for this
batch that qualifies as business logic requiring a move to Flask —
Employees/Equipment/Users are thin CRUD wrappers over repository
validation; Templates' entire structural validation (dependency cycles,
duplicate codes) was already 100% server-side before this batch and
remains untouched; Calendar's interval-overlap preview is UI-only
fail-fast feedback, mirrored from Classic, with the backend re-validating
independently on every save (same category as Batch 2's audit-category
mirroring — a duplicated *display* enum/preview, not a decision).

## TYPECHECK / BUILD / LINT

```
npm run typecheck  -> PASS (0 errors)
npm run lint         -> PASS (oxlint, 0 warnings)
npm run build         -> PASS (dist/assets/index.js 627.6 kB, gzip 187.98 kB)
```

Bundle size crossed Vite's 500 kB chunk-size warning threshold this batch
(was ~140 kB gzip after Batch 2, now ~188 kB gzip after adding
react-hook-form/zod/@radix-ui's select/checkbox/alert-dialog and six new
feature areas). Noted, not acted on this pass — no page has a real load-time
problem yet and premature code-splitting was explicitly out of scope
("Do not prematurely introduce complex state management" / performance
guidance). Flagged as a Batch 4/5 watch-item once Production
Orders/Sessions add more weight.

## PLAYWRIGHT

`mesflow-web/tests/e2e/{employees,templates,calendar,users,qr,equipment}.spec.ts`
(new, 20 tests) + the 11 Batch 1/2 specs, all against the same real local
backend + PostgreSQL sandbox with live mutations (create/edit/delete
round-trips verified against the real database, not mocked, except where a
test explicitly needs a controlled failure/permission state).

```
31/31 passed
```

Mandatory coverage from this batch's instructions, all present:
Employees CRUD (create → edit → delete, verified via UI + a follow-up API
read), Template CRUD (create Part/Operation, validate, save, verified via
a direct API re-fetch), Users permission state (mocked restricted-role
403-in-place **and** a real unauthenticated `401` against the live
`/api/users` endpoint). Calendar and QR got their own coverage too (not
explicitly mandatory, but both are stateful/interactive enough to warrant
it — QR's print-sheet DOM and Calendar's client-side validation preview
each needed a real correctness check, which is exactly what caught the two
bugs above).

PAGE ERRORS: **0**
CONSOLE ERRORS: **0**

## 1920 / 1366

Every new page reviewed at 1920×1080 (screenshots in
`reports/screenshots/mesflow-web-batch3/`); Employees and Calendar also
checked at 1366×768 with the same automated `scrollWidth <= clientWidth`
gate used in every prior batch — both clean.

## Environment used for verification

Same ProjectFlow local sandbox as Batches 1/2 (`127.0.0.1:18280`), same
seeded demo data (now also: one ad-hoc Playwright-created employee/user/
equipment/Part+Operation per test, each deleted or deactivated by its own
test — Users has no delete endpoint server-side, so the one Playwright-
created test user was deactivated rather than left active, matching this
project's "keep test fixtures clearly identifiable and cleanable" rule).

## CLASSIC UI PRESERVED: YES

Zero files changed under `mesflow/app/mesflow/web/`. Re-verified Classic's
own Employees/Templates/Calendar/Users/QR/Equipment screens against the
same sandbox+data after this batch: zero page/console errors.

## PRODUCTION DEPLOYED: NO

## Next batch

**Batch 4 (Business-Critical)** — Production Orders → Session Management →
Session Exception Center, migrated and tested one at a time per this
task's own instruction ("Do NOT migrate all three simultaneously before
testing"). Not started in this pass: these carry real audit/compliance
weight (session correction, PO Start, exception resolution) and deserve a
dedicated focused pass rather than being appended to an already-large
Batch 3, consistent with the phased gate structure the task itself
defines. `docs/architecture/UI_MIGRATION_STATUS.md` reflects this as the
next row group to fill in.
