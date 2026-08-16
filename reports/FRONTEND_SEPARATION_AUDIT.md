# MESFlow Frontend Separation Audit (F0)

Date: 2026-08-15
Scope: `mesflow/app/mesflow/web/` (Flask/Jinja shell + vanilla JS admin UI) audited
before creating `mesflow-web/` (React/TypeScript). Read-only audit; no backend or
Classic UI code was changed to produce this report.

## 1. Current shell

- Server: `app/mesflow/web/app.py` (Flask app factory), session-cookie auth via
  `flask.sessions.SecureCookieSessionInterface` (localhost/QA-aware subclass).
- Shell page: `GET /app` → `templates/app.html`, renders `window.MESFLOW_USER =
  {id, username, role, permissions}` inline, then loads, in order:
  `core/api.js` → `core/nav.js` → `core/ui.js` → `pages/session-detail.js` →
  `app.js` (964 lines, contains most page renderers directly) → the remaining
  `pages/*.js` modules → an inline bootstrap `<script>` that reads
  `?page=`/`?session=` from the URL and calls `openPage(id)`.
- **Not a router SPA.** `openPage(id)` replaces `#content.innerHTML` entirely.
  There is exactly one query param used for deep-linking (`?page=`, plus
  `?session=` for the shared Session Detail drawer). Real browser Back/Forward
  is explicitly documented as unsafe (`core/nav.js` header comment) because
  most transitions don't push a history entry; in-app "Back" buttons instead
  replay a hand-rolled `AppNav` stack that also snapshots every `#content
  [id]` form control + scroll position + active tab so returning to a list
  restores filters. **This state-preservation behavior is the one piece of
  "business" logic in `core/nav.js` worth deliberately reproducing in React
  Router (via URL search params + TanStack Query cache), not copying
  verbatim.**
- Auth/session: `app/mesflow/web/auth.py`. `permission_required(code)`,
  `login_required`, `roles_required(*roles)` (falls back to a hard-coded
  path→permission table, then to the role allow-list if unmapped),
  `production_client_required` (session OR kiosk token). RBAC codes are
  looked up per-request from `RBACRepository` (`role == 'admin'` always
  passes). No JWT, no separate API token for browser clients — same
  session cookie serves page loads and `/api/*` XHR/fetch calls.
- Global fetch helper: `core/api.js` (14 lines) — same-origin `fetch`,
  auto-`Content-Type: application/json` when a body is present, hard
  redirects to `/login` on any `401`, throws `Error(d.message||d.error)` on
  `!ok || d.ok===false`. Every page module calls this one helper; there is no
  retry/backoff, no request de-duplication, and no client-side caching (every
  `openPage()` call re-fetches from scratch).

## 2. Per-screen inventory

| PAGE | CURRENT JS MODULE | CURRENT API ENDPOINTS | AUTH/PERMISSIONS | READ/WRITE | COMPLEXITY | MIGRATION RISK | TARGET FEATURE MODULE |
|---|---|---|---|---|---|---|---|
| Overview | `pages/overview.js` (24 ln) | `GET /api/dashboard/overview` | `overview.view` | Read-only | Low | **Low** | `features/dashboard/overview` |
| Daily Dashboard | inline in `app.js` (`renderDashboard`, ~200 ln) | `GET /api/settings/work-shifts`, `/api/dashboard/summary`, `/api/dashboard/production-orders`, `/api/dashboard/active-sessions`, `/api/dashboard/daily-progress`, `/api/dashboard/daily-sessions`, `/api/dashboard/shift`, `/api/dashboard/recent-activity` | `dashboard.view` | Read-only, polls every 10s | High (shift picker, live timeline, KPI tiles, 10s poll) | Medium | `features/dashboard/daily` |
| Production Orders | inline in `app.js` (`renderProductionOrders`) | `GET/POST /api/production-orders` (generic `/<resource>`), `POST /api/production-orders/<id>/start`, `DELETE /api/production-orders/<id>/force`, `GET /api/templates/available-for-po`, `GET /api/production-orders/<id>/trace` | `po.view` / `po.edit` (+ admin force-delete gate) | Read + Write, business-critical | High | **High** — migrate last per F8, own batch | `features/production-orders` |
| Templates | inline in `app.js` (`templateUi` tree editor) | `GET/POST /api/templates`, `GET/PUT /api/templates/<id>/tree`, `GET /api/templates/<id>/validate`, `POST /api/templates/<id>/instantiate`, `POST /api/template-parts/upload-drawing`, `POST/DELETE /api/templates/demo`, `GET/POST /api/templates/<id>/export` (`excel_io.py`) | `template.view` / `template.edit` | Read + Write (Part/Operation tree editor) | High (unsaved-changes guard, drag/reorder, nested tree) | **High** | `features/templates` |
| Employees | resource table via `resources.employees` config in `app.js` | `GET/POST/DELETE /api/employees` (generic `/<resource>`, `/<resource>/<id>`), QR fields inline | `employees.view` / `employees.edit` | Read + Write CRUD | Low-Medium | Low | `features/employees` |
| Sessions (Session Management) | inline in `app.js` (`renderSessionManagement`, largest single render function) | `GET /api/session-management`, `GET /api/session-management/operations`, `GET /api/session-management/<id>`, `POST /api/supervisor/sessions/<id>/adjust`, shared drawer via `pages/session-detail.js` | `session.view` / `session.edit` | Read + Write, business-critical (quantities, times, edit reason required) | High (accordion list, edit modal, employee/PO/op filters) | **High** — migrate after Templates/PO stabilize (F9) | `features/sessions` |
| Session Exceptions | `pages/session-exceptions.js` (390 ln) + `pages/exception-center.js` (18 ln wrapper) + shared `pages/session-detail.js` (201 ln) | `GET /api/session-exceptions` (`analytics.py`), `GET /api/exceptions`, `GET /api/exceptions/<id>`, `GET /api/exceptions/<id>/history`, `POST /api/exceptions/<id>/acknowledge`, `POST /api/exceptions/<id>/resolve`, `POST /api/exceptions/<id>/ignore`, `GET /api/sessions/<id>/context` (`exceptions.py`) | `exceptions.view` / `exceptions.resolve` | Read + Write (workflow actions) | High (queue workflow: Nhận xử lý → open Session → correct → Hoàn tất/Bỏ qua) | **High** — migrate after Sessions (F10) | `features/session-exceptions` |
| Production Trace | `pages/production-trace.js` (15 ln, thin) | `GET /api/production-orders/<id>/trace`, `/api/operations/<id>/trace`, `/api/sessions/<id>/trace`, `/api/<kind>/<id>/quantity-history` | `session.view` (role-gated `admin/manager/supervisor` server-side in `trace.py`, independent of the RBAC table) | Read-only | Medium (timeline/category filters) | **Low** | `features/production-trace` |
| Gantt / Material Flow | `renderProductionSchedule` in `app.js` + `pages/material-flow.js` (72 ln) | `GET /api/production-schedule`, `/api/production-control`, `/api/operations/<id>/material-flow` | `material_flow.view` / `material_flow.edit` | Read + some Write | High (Gantt rendering, drag ranges) | Medium-High | `features/material-flow` |
| Kiosk (admin) | `renderKioskManagement` in `app.js` | `GET /api/kiosk-management/overview`, `/api/kiosk-management/<uuid>/events`, `POST /api/kiosk-management/<id>/status`, plus `/api/system-health/kiosks*` and `/api/internal/kiosks*` (OTA) | `kiosk.view` / `kiosk.manage` | Read + Write (status, OTA) | High (spread across 4 blueprints: `kiosk.py`, `execution.py`, `system_health.py`, `internal_ota.py`) | Medium — device firmware itself out of scope (ESP kiosk repo) | `features/kiosk-admin` (F11, last) |
| QR | `pages/qr-print.js` (45 ln) | `GET /api/qr-labels`, `GET /api/qr-image` | `qr.view` | Read + client-side print | Low-Medium | Low | `features/qr` |
| Calendar | `renderWorkingCalendar` in `app.js` | `GET/PUT /api/settings/work-shifts`, `GET /api/settings/working-calendar` | `calendar.view` / `calendar.edit` | Read + Write | Medium | Medium | `features/calendar` |
| Users/Roles | `renderUsers` in `app.js` | `GET/POST /api/users`, `POST /api/users/<id>/reset-password`, `POST /api/auth/change-password`, `GET /api/roles`, `PUT /api/roles/<code>/permissions` | `users.view` / `users.manage`, `roles.manage` | Read + Write, security-sensitive | Medium-High (RBAC permission matrix editor) | Medium-High | `features/users` |
| Business Audit | inline in `app.js` (`renderBusinessAudit` + `auditCardHtml`/`openAuditDrawer`, ~120 ln) | `GET /api/audit-logs` (`analytics.py`) | `business_audit.view` | **Read-only** | Medium (category chips, filters, card list, detail drawer) | **Lowest** | `features/business-audit` — **POC (F6)** |
| Application Logs | `pages/system-logs.js` (57 ln) | `GET /api/system/action-logs`, `/api/system/action-logs/stats`, `/api/system/action-logs/<id>`, `POST .../resolve`, `GET /api/system/error-traces*`, `POST .../resolve`, `GET/POST /api/system/log-retention/*` | `logs.view` / `logs.manage` | Read + occasional Write (mark resolved) | Medium | Low-Medium | `features/system-logs` |
| Tutorials | `renderTutorials`/`renderEspKioskTutorial` in `app.js` | `GET /api/tutorials`, `GET /tutorials/<file>`, `GET /api/esp-kiosk-tutorial`, `GET /esp-kiosk-tutorial/videos/<file>` | Login required only — **no RBAC permission gate** (absent from `PAGE_PERMISSION`) | Read-only (video/manifest) | Low | Lowest | `features/tutorials` (always last in nav, per UI standard) |

Not explicitly requested but present and worth naming: **Equipment** and other
generic master-data resources (`stations`, `sales-orders`, `parts`,
`operations`) share the same generic `/<resource>` CRUD route family as
Employees/Templates (`master_data.py`). They fold into `features/employees`
and `features/templates`-adjacent master-data modules in F7, not a separate
audit row.

## 3. RBAC / permission catalog observed

Permission codes seen wired to routes/pages (role `admin` always passes,
enforced server-side in `RBACRepository.has_permission`):
`overview.view`, `dashboard.view`, `po.view`, `po.edit`, `template.view`,
`template.edit`, `session.view`, `session.edit`, `exceptions.view`,
`exceptions.resolve`, `business_audit.view`, `material_flow.view`,
`material_flow.edit`, `kiosk.view`, `kiosk.manage`, `logs.view`,
`logs.manage`, `employees.view`, `employees.edit`, `equipment.view`,
`equipment.edit`, `qr.view`, `users.view`, `users.manage`, `roles.manage`,
`calendar.view`, `calendar.edit`. The Classic UI's own gate
(`app.js:PAGE_PERMISSION` + `hasPermission()`) is **UI-only defense in
depth** — every one of these is independently re-checked server-side per
route (`auth.py`), so React can reuse the same map for nav visibility without
becoming an authority.

## 4. Login / session behavior to preserve exactly

- `POST /api/auth/login {username,password}` → `200 {ok:true,user:{id,
  username,role,must_change_password,permissions}}` or `401
  {ok:false,error:'INVALID_CREDENTIALS'}`.
- `POST /api/auth/logout` → clears session.
- `GET /api/auth/me` → `401 {ok:false,error:'AUTH_REQUIRED'}` when logged
  out; otherwise same user shape as login.
- `POST /api/auth/test-auto-login` — non-production only, gated by
  `MESFLOW_TEST_AUTO_LOGIN`; used by every existing Playwright spec
  (`tests/e2e/*.spec.js`) via `page.request.post('/api/auth/test-auto-login')`
  after `page.goto('/login')`. **mesflow-web's own e2e tests should use the
  identical mechanism** rather than driving a login form, to stay consistent
  with the existing suite.
- Cookie is `HttpOnly`, `SameSite=Lax`, `Secure` in production
  (`LocalhostAwareSessionInterface` relaxes `Secure` only for direct
  localhost/QA-network traffic, never for public/proxied traffic). No CSRF
  token exists today (`SameSite=Lax` + same-origin `fetch` is the current
  mitigation) — mesflow-web must not invent one unilaterally; it only needs
  `credentials:'include'` behavior, which same-origin fetch already implies.

## 5. APIs already sufficient for migration

Business Audit, Production Trace, Overview, Tutorials, QR, Employees — the
JSON contracts already carry everything the current UI renders (including
Vietnamese labels/enum translation for Business Audit, done entirely
server-side in `mesflow/domain/audit_presentation.py`). No backend change is
required to build POC-equivalent React pages for these.

## 6. APIs requiring small (non-breaking) additions later

- `/api/audit-logs` and most list endpoints take only `limit` (default
  `200`), no cursor/offset — fine for a POC "top N" view, but true pagination
  should be added before Application Logs / Sessions (higher row counts) are
  migrated (F12 candidate, additive only).
- Session Exceptions functionality is split across two blueprints
  (`GET /api/session-exceptions` in `analytics.py` for the list,
  `/api/exceptions/*` in `exceptions.py` for the workflow actions) — works
  today, but worth a consistency pass (still additive, not a breaking
  rename) before F10.
- Kiosk admin is spread across four blueprints (`kiosk.py`, `execution.py`
  kiosk-management routes, `system_health.py`, `internal_ota.py`) — no gap,
  just fragmented; note for F11 only.

## 7. UI behavior currently implemented only in browser code

- **`AppNav`** (`core/nav.js`): drill-in/back stack + form-field/scroll/tab
  snapshot-restore. Pure presentation; React Router + component state is the
  correct replacement, not a port.
- **Session Management "Advanced" gate**: hides Operation/status change
  fields behind a `<details>` disclosure with a warning ("Chỉ thay đổi khi đã
  xác minh…") — presentational guardrail only; the backend still requires an
  edit `reason` and re-validates the transition, so this is safe to
  reproduce as-is in React without asking the backend for anything new.
- **Template unsaved-changes guard** (`confirm()` on navigating away while
  `templateUi.dirty`) — pure UI convenience.
- **QR batch selection + browser print** (`pages/qr-print.js`) — client-side
  selection/print orchestration over server-provided label images; no
  business logic.

## 8. Business logic accidentally living in the frontend (flagged, not migrated)

- **Daily Dashboard "current shift" resolution** (`app.js`:
  `currentShiftContext()`, `clockMinute()`, `hcmNowParts()`): the browser
  independently recomputes which shift window "now" falls into from
  `Asia/Ho_Chi_Minh` wall-clock time and the shift list, duplicating logic
  that already has a server equivalent (`GET /api/dashboard/shift`). This is
  domain logic (shift-window semantics), not presentation, and it is the one
  clear violation of "backend is the source of truth" found in this audit.
  **Do not port this calculation into React.** When Daily Dashboard is
  migrated (F6, batch 2+), the React page must call `/api/dashboard/shift`
  as the sole source of "current shift" and the client-side recomputation
  should be retired from Classic UI too at that point — tracked as a
  follow-up, out of scope for this task (no Flask/Classic UI change made
  here).
- **Business Audit `BA_CATEGORIES`** (`app.js` line 84-85): a client-side
  literal list of `[code, label]` pairs that mirrors
  `mesflow.domain.audit_presentation.CATEGORY_LABELS` exactly today. Not a
  business-logic violation (it's a fixed filter-chip list, not a decision),
  but it is a duplicated enum with no API source. mesflow-web's POC
  reproduces the same literal list (documented as mirroring the backend
  enum) rather than inventing an endpoint for it — flagged as an F12
  candidate (`GET /api/audit-logs/categories` or embed in a manifest), not a
  blocker.

No other accidental business logic (quantity math, status-transition rules,
permission decisions, exception classification) was found living in the
audited JS — those are consistently computed server-side and merely
rendered by the current pages, which is the correct starting point for
migration.

## 9. Playwright coverage already in place

`tests/e2e/business-audit-v74.spec.js` already covers the exact POC screen
(Classic UI): logs in via `test-auto-login`, seeds one real audit row via a
genuine read-then-rewrite `PUT /api/settings/work-shifts`, asserts card
rendering, no raw JSON, Vietnamese action labels, and a working detail
drawer at 1920x1080. mesflow-web's own parity spec follows the same login
and seeding pattern.

## 10. Conclusion — POC page selection

**Business Audit** is confirmed as the F6 proof-of-concept: single
already-sufficient read-only endpoint, all labels/enums pre-translated
server-side, existing detail-drawer interaction pattern, lowest migration
risk of any screen in this inventory, and an existing Classic-UI Playwright
spec to mirror for parity. Production Trace is the documented fallback if
needed; not required here.
