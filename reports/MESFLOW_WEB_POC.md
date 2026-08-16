# mesflow-web Proof-of-Concept Report (F1–F6)

Date: 2026-08-15
Scope delivered: F0 audit, F1 project foundation, F2 design system
foundation, F3 auth/API client, F4 routing/navigation, F5 Classic+New
parallel mode, F6 one POC page (Business Audit). PO/Templates/Sessions/
Exceptions/Kiosk are explicitly **not** migrated in this pass.

See also: `reports/FRONTEND_SEPARATION_AUDIT.md` (F0),
`docs/architecture/FRONTEND_BACKEND_SEPARATION.md`.

## What was built

- **`mesflow-web/`** — new independent project. React 19 + TypeScript +
  Vite, React Router, TanStack Query, Radix UI primitives, Tailwind CSS v4
  for design tokens. `base: '/app-v2/'` in `vite.config.ts` so the built
  bundle is ready to sit behind a gateway at that path later (F15); dev
  server runs at `http://localhost:5173/app-v2/` and proxies `/api`,
  `/uploads`, `/tutorials`, `/esp-kiosk-tutorial` straight to the local
  Flask backend (`MESFLOW_API_PROXY_TARGET`, default `127.0.0.1:8080`).
- **Design tokens** (`src/index.css`) copied 1:1 from Classic UI's canonical
  token block (`mesflow/app/mesflow/web/static/ui.css`) so both UIs read as
  the same product: command-navy sidebar, industrial neutral palette,
  compact controls, 1px borders, no generic-SaaS shadows/rounding.
- **Design-system primitives** (`src/components/ui/`): Button, Badge,
  Input, Dialog (Radix), Tooltip (Radix) — only what the POC page and shell
  actually use; no unused Select/Tabs/DropdownMenu/Separator/Label
  scaffolding (installed, evaluated, then removed — see package.json
  history). Shared page-level components: PageHeader, StatusBadge,
  EmptyState, LoadingState, DetailDrawer (a right-anchored slide-in panel
  mirroring Classic UI's `MFUI.openDrawer`, reused by both the audit detail
  view and any future feature needing a drawer).
- **API client** (`src/api/client.ts`): one `apiFetch()` wrapper, same-origin
  `credentials: 'include'`, typed `ApiError` (401/403/404/409/422/500/
  network), auto-redirect to `/app-v2/login` on 401 (opt-out for the auth
  bootstrap check itself). `src/api/auth.ts` / `src/api/business-audit.ts`
  call the exact same endpoints Classic UI uses, with TypeScript types
  mirroring the backend's actual JSON shapes (including
  `mesflow.domain.audit_presentation`'s `presentation` object field-for-
  field) — no `any`.
- **Auth**: unchanged Flask session-cookie auth. `src/features/auth/
  LoginPage.tsx` posts to `/api/auth/login`, same error copy and `next`
  redirect as `login.html`. A dev-only, **user-triggered** "Đăng nhập nhanh
  (dev/test)" button calls the same `/api/auth/test-auto-login` endpoint
  the existing Playwright suite already uses (never fires automatically —
  an automatic attempt would 403-spam the console on any backend where
  `MESFLOW_TEST_AUTO_LOGIN` is off, which is most of them).
- **RBAC**: `src/app/permissions.ts` mirrors `app.js`'s `PAGE_PERMISSION`
  map exactly. This is UI-only defense in depth, documented as such —
  every API call is independently re-checked server-side
  (`mesflow/app/mesflow/web/auth.py`), unchanged.
- **Routing** (`src/app/router.tsx`): real React Router routes, not content
  swapping. `/app-v2/login`, `/app-v2` (redirects to the one migrated
  page), `/app-v2/business-audit`. `RequireAuth` redirects to login with
  `?next=`; `RequirePagePermission` renders an in-place "Không có quyền
  truy cập" message (not a redirect) when the session is valid but the
  permission is missing, exactly like Classic UI's `canOpenPage()`.
- **Parallel mode**: `AppLayout`'s sidebar (`src/app/nav.ts`) lists every
  Classic UI screen. The one migrated entry is a real `<NavLink>`; every
  other entry is a plain `<a href="/app?page=...">` full-navigation link
  into Classic UI (marked with an external-link icon) — there is no fake
  placeholder route for an unmigrated screen. Classic UI (`/app`) was not
  touched: zero files changed under `mesflow/app/mesflow/web/`.
- **POC page — Business Audit** (`src/features/business-audit/`):
  read-only, single endpoint (`GET /api/audit-logs`), server-built
  presentation rendered as-is (no label/enum translation done in React —
  see the audit report §8 on why that boundary matters). Category chips,
  date/actor/advanced filters, and the selected drawer id all live in the
  URL (`useSearchParams`) — filter changes replace the current history
  entry (matches Classic's `AppNav.setQuery`), opening the detail drawer
  pushes a new entry so browser Back closes the drawer instead of leaving
  the page.

## Test evidence

```
npm run typecheck   -> PASS (tsc -b --noEmit, no errors)
npm run build        -> PASS (dist/assets/index.js 398.67 kB, gzip 127.65 kB)
npm run lint          -> PASS (oxlint, 0 warnings/errors)
npm run test:e2e      -> PASS, 7/7 (Playwright, chromium)
```

Playwright coverage (`mesflow-web/tests/e2e/business-audit.spec.ts`,
against a real local backend + PostgreSQL — see "Environment" below):

1. Login (real form) → lands on `/app-v2/business-audit`, real audit cards
   render, **zero page errors, zero console errors** at 1920x1080.
2. Detail drawer opens on click, raw JSON only appears inside the collapsed
   "Thông tin kỹ thuật" `<details>` (never in the card list) — same
   contract as `mesflow/tests/e2e/business-audit-v74.spec.js`. Reloading a
   `?audit=<id>` URL reopens the same drawer (deep link). Browser **Back**
   closes the drawer and returns to the plain list URL.
3. Category filter click updates the URL (`?category=admin`) and refetches.
4. Logout returns to `/app-v2/login`; visiting a protected route afterward
   redirects to `/app-v2/login?next=...` (session gate proven both ways).
5. A simulated 401 mid-session (real error envelope shape) redirects to
   login — same handling path a real expired cookie would hit.
6. A simulated authenticated-but-under-permissioned session (mirrors the
   `operator` role, which the backend's default RBAC grants do not include
   `business_audit.view`) renders "Không có quyền truy cập" **in place**,
   not a redirect — proven without mutating any real user/role data.
7. 1366×768: renders, `scrollWidth <= clientWidth` (no horizontal overflow).

### Classic UI regression (unmodified)

Logged into Classic UI (`/app`) on the same backend/database, opened
Business Audit via `openPage('business-audit')`: **zero page errors, zero
console errors**. Confirms mesflow-web's presence does not affect Classic
UI (no shared files were touched) and the same live data renders
consistently in both UIs (screenshot comparison below).

### Backend

`tests/test_v74_audit_presentation_unit.py` (the presentation contract this
POC's types were derived from): 19/19 passed, unmodified — no backend files
were changed in this task.

### Environment used for verification

Local-only, no production involved: `mesflow/scripts/projectflow/
deploy-local.sh` against the already-built `mesflow-app:71.0.0.5` image
(ProjectFlow local sandbox, distinct containers/network/volumes from any
real deployment — see that script's header comment), `http://
127.0.0.1:18280`. mesflow-web's dev server proxied to it via
`MESFLOW_API_PROXY_TARGET`.

## Screenshots

`reports/screenshots/mesflow-web-poc/`:
- `login-1920x1080.png` — New UI login (split industrial gateway layout, mirrors `login.html`)
- `business-audit-1920x1080.png` — New UI Business Audit list
- `business-audit-1366x768.png` — same page, smaller viewport, no overflow
- `business-audit-drawer.png` — detail drawer open with "Thông tin kỹ thuật" expanded
- `classic-business-audit.png` — Classic UI's same page, same data, for side-by-side comparison

Two visual passes were done: the first pass surfaced a history-stack bug
(closing/back on the drawer navigated out of the app entirely) and console
noise from an auto-firing dev convenience login — both fixed before this
report (see "Issues found and fixed" below).

## Issues found and fixed during this pass

1. **Drawer open used `replace` instead of `push` for history.** Browser
   Back from an open drawer landed on `about:blank` instead of closing the
   drawer. Fixed: opening the drawer pushes a history entry; filter changes
   still replace (matches Classic's `AppNav.setQuery` behavior for filters
   specifically).
2. **Auto-firing dev test-login caused console noise.** The initial
   dev-convenience login attempted `/api/auth/test-auto-login`
   automatically on every visit to the login page, which 403s (expected,
   console-logged by the browser regardless of app-level `try/catch`) on
   any backend where `MESFLOW_TEST_AUTO_LOGIN` is off — the common case.
   Fixed: it is now a manual button, dev-build-only, never auto-fired.
3. **`/api/auth/me` fired from the login page.** Checking "already logged
   in" on page load 401'd for every normal (logged-out) visit — again
   browser-logged as a console error independent of handling. Fixed: the
   login page now only peeks at an already-cached session (no new
   request); the real guard (`RequireAuth`) still protects every actual
   route.

## Not done in this pass (by design)

- PO, Templates, Sessions, Session Exceptions, Kiosk admin, Users/Roles,
  Calendar, QR, Application Logs, Overview, Daily Dashboard: still Classic
  UI only, reached via the sidebar's external links. See the audit report's
  per-screen migration-risk ordering for F7+.
- No gateway/nginx changes, no production deployment, no image/release
  changes. `mesflow-web/` is not referenced by any `compose.yml`,
  `Dockerfile`, or release ZIP builder yet (F15 is future scope).
- No backend or Classic UI files were modified.
