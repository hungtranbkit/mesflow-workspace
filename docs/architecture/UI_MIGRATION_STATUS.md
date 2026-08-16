# MESFlow UI Migration Status

Living parity matrix, updated after every migrated screen. See
`reports/FRONTEND_SEPARATION_AUDIT.md` (F0), `reports/MESFLOW_WEB_POC.md`
(F6), `reports/MESFLOW_WEB_BATCH2_READONLY.md` (Batch 2),
`reports/MESFLOW_WEB_BATCH3_CRUD.md` (Batch 3) for the work behind each
row. `READY_TO_RETIRE` stays `NO` for every row until **all** rows are
`YES`/`YES`/`PASS`/`PASS` — Classic UI is not retired page-by-page (see
AGENTS.md "Final Migration Gate").

| PAGE | CLASSIC | NEW | PARITY | PLAYWRIGHT | READY_TO_RETIRE |
|---|---|---|---|---|---|
| Overview | YES | YES | PASS | PASS | NO |
| Daily Dashboard | YES | YES | PASS | PASS | NO |
| Production Trace | YES | YES | PASS | PASS | NO |
| Business Audit | YES | YES | PASS | PASS | NO |
| Employees | YES | YES | PASS | PASS | NO |
| Templates / Parts / Operations | YES | YES | PASS | PASS | NO |
| Calendar / Work Shifts | YES | YES | PASS | PASS | NO |
| Users / Roles / Permissions | YES | YES | PASS | PASS | NO |
| QR Management | YES | YES | PASS | PASS | NO |
| Equipment | YES | YES | PASS | PASS | NO |
| Production Orders | YES | NO | — | — | NO |
| Session Management | YES | NO | — | — | NO |
| Session Exception Center | YES | NO | — | — | NO |
| Gantt & Material Flow | YES | NO | — | — | NO |
| Kiosk Admin | YES | NO | — | — | NO |
| Application Logs | YES | NO | — | — | NO |
| Tutorials / Help | YES | NO | — | — | NO |

## Route map (New UI)

```
/app-v2/                  -> redirects to /app-v2/overview
/app-v2/login
/app-v2/overview
/app-v2/dashboard
/app-v2/production-trace
/app-v2/business-audit
/app-v2/employees
/app-v2/templates
/app-v2/templates/:id
/app-v2/calendar
/app-v2/users
/app-v2/roles
/app-v2/qr
/app-v2/equipment
```

Every route above is a real React Router route: direct URL load, browser
refresh, and Back/Forward all work (verified per-page in Playwright, see
each batch report). Every sidebar entry not yet migrated links out to
Classic UI (`/app?page=<id>`) — there is no placeholder route for an
unmigrated screen (`src/app/nav.ts`).

## Shared component inventory (cumulative)

`src/components/`: `ui/` (button, badge, input, textarea, select, checkbox,
dialog, alert-dialog, tooltip), `PageHeader`, `StatusBadge`, `DetailDrawer`
(+`KvRow`/`DrawerSection`), `EmptyState`, `LoadingState`, `ErrorState`,
`FilterBar`/`FilterField`, `DateFilter`, `CategoryChips`, `CopyValue`,
`EventBadge`, `EntityLink`, `Timeline`, `SessionDetail` (shared read-only
drawer), `DataTable`, `ConfirmDialog`, `FormRow`, `Section`.

Not built yet (no real use case until a mutating/business-critical batch
needs them): a real TanStack Table integration (current `DataTable` is a
config-driven `<table>`, sufficient for every list so far), a
`SessionDetail` write/correction mode (F9 — see AGENTS.md "Session
correction" rules), Pagination (cursor "load more" has covered every case
so far).

## API modules (cumulative)

`src/api/`: `client.ts` (shared fetch wrapper), `auth.ts`, `audit.ts`,
`dashboard.ts`, `production-trace.ts`, `sessions.ts` (read-only
SessionDetail contract), `employees.ts`, `calendar.ts`, `users.ts`, `qr.ts`,
`equipment.ts`, `templates.ts`. Zero backend API changes across F6/Batch2/
Batch3 — every screen migrated so far used an already-sufficient endpoint.
