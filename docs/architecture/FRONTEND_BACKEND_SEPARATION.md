# MESFlow Frontend/Backend Separation

Status: F0–F6 delivered (audit, `mesflow-web/` foundation, design system
foundation, auth/API client, routing, Classic+New parallel mode, one POC
page). F7+ (remaining screens, gateway split, Classic UI retirement) is
future work. See `reports/FRONTEND_SEPARATION_AUDIT.md` and
`reports/MESFLOW_WEB_POC.md` for the work behind this document.

## Target architecture

```
Browser
   |
   v
nginx / gateway            (future — F15; not deployed yet)
   |
   +---  /app     -> Classic UI (Flask/Jinja, mesflow/app/mesflow/web/)
   +---  /app-v2  -> mesflow-web (React/TS, static build)
   +---  /api     -> mesflow backend (Flask, unchanged)
```

Today (F5), there is no gateway split yet: `mesflow-web`'s Vite dev server
proxies `/api` (and `/uploads`, `/tutorials`, `/esp-kiosk-tutorial`)
straight to the same Flask backend Classic UI already talks to. Both UIs
read/write the exact same PostgreSQL database through the exact same API —
there is no data or logic fork between them.

## Ownership boundary

**`mesflow/` (backend) owns:**
- business logic, domain/service/repository layers
- authentication/session (Flask session cookie, unchanged)
- authorization/RBAC (`mesflow/app/mesflow/web/auth.py`,
  `RBACRepository`) — the only place a permission decision is made
- the `/api/*` HTTP contract
- PostgreSQL and all migrations
- Classic UI (`templates/`, `static/`), until retired per the migration plan

**`mesflow-web/` (frontend) owns:**
- page layout, navigation, routing (React Router)
- forms, tables, drawers, dialogs
- frontend/UI state (open drawer, active filter, selected tab — all in the
  URL or component state, never persisted server-side)
- API consumption (TanStack Query) and presentation of whatever the
  backend returns

**Never:**
- mesflow-web talking to PostgreSQL directly
- business rules (quantity math, status transitions, exception
  classification, permission grants) implemented in React — if a page's
  Classic-UI JS is doing one of these today, it either already calls a
  backend endpoint that does the real computation (reuse that), or it is a
  bug to fix in `mesflow/` first, not something to port as-is (see the
  audit report §8 for the one confirmed case found so far — the Daily
  Dashboard's client-side "current shift" recomputation)
- two different implementations of the same decision (e.g. a page-level
  permission check in React must mirror, never replace, the server-side
  check — see `src/app/permissions.ts`'s own header comment)

## Auth

Unchanged Flask session-cookie auth (`HttpOnly`, `SameSite=Lax`, `Secure`
in production). mesflow-web's API client
(`mesflow-web/src/api/client.ts`) sends `credentials: 'include'` on every
request and centrally handles 401 (redirect to `/app-v2/login`), 403, 404,
409, 400/422, 500, and network failures as a typed `ApiError`. No JWT, no
new token type, no CSRF token invented — same-origin cookie auth is the
entire mechanism on both UIs. `mesflow-web/src/app/permissions.ts` mirrors
the backend's permission-code map for nav/page visibility only; the backend
independently re-checks every permission on every request regardless of
what the UI shows.

## Routing / parallel mode

- Classic UI: `/app`, content-swapping SPA-in-one-page (`openPage(id)`),
  documented as not supporting real browser Back (`core/nav.js`). Not
  modified by this work.
- mesflow-web: `/app-v2/*`, real React Router routes with deep links and
  working browser Back/Forward. Only migrated screens get a route;
  everything else is a plain link out to the equivalent `/app?page=...`
  Classic UI screen (see `mesflow-web/src/app/nav.ts`) — never a fake
  placeholder page.
- Both mount points can coexist indefinitely; retiring `/app` in favor of
  `/app-v2` (F19) only happens after full functional parity is proven per
  screen (Playwright parity matrix, RBAC parity, visual review).

## API contract

mesflow-web consumes the existing `/api/*` contract as-is. TypeScript types
are written from the actual backend response shapes (see
`mesflow-web/src/api/business-audit.ts` mirroring `mesflow/app/mesflow/
domain/audit_presentation.py` field-for-field) rather than assumed or
generated speculatively. Additive, backward-compatible contract
improvements (pagination, richer enums, consistent envelopes) are expected
as more screens migrate (F12) — Classic UI must keep working through any
such change; this task made zero API changes.

## Deployment (not yet changed)

`mesflow-web/` is not wired into any `compose.yml`, `Dockerfile`, or release
ZIP builder yet. First deployment step (future, F15 Option A) is building
`mesflow-web`'s static `dist/` and serving it through the existing MESFlow
release/gateway, before ever splitting into independent
`mesflow-api`/`mesflow-web` release artifacts (F15 Option B). No production
deployment has happened as part of this work.
