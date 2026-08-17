# UI Remaining Defects Fix

VERSION BEFORE: 71.0.0.25
VERSION AFTER: 71.0.0.26

Focused UI correction only, no unrelated redesign, no backend/business-logic/API
changes, no Production Test/Production touch.

## BUSINESS AUDIT BUTTONS:

**Semantic-role check first, per the task's own decision tree**: the 9
category controls ("Tất cả", "Session", "Sản lượng", "PO", "Công đoạn",
"Lịch làm việc", "Nhân viên", "Xử lý bất thường", "Quản trị") narrow which
records the same audit-log list below shows (`role="group"`, exclusive
`.active` selection, re-fetches the same list) — they do **not** switch
to a different page/view, so per the task's own rule they stay filter
chips, not `.mf-tabs/.mf-tab`. This exact reasoning was already recorded
in `ui.css` from a prior pass (`/* Filter chips ... not .mf-tab */`), so
no reclassification was made — confirmed correct, not changed.

**The real defect**: `.ba-chip` had `padding:7px 13px` with no working
height cap, rendering **33.875px** tall — a *previous* attempt at
`.ba-chip{min-height:32px}` had zero effect because `min-height` cannot
shrink a box whose padding+line-height already exceeds it. Fixed at the
source: `.ba-chip` now uses `display:inline-flex;align-items:center;
height:32px;padding:0 12px` — an explicit, guaranteed **32px** height
matching the app's canonical compact-control height (`.btn.mini`),
radius unchanged at `999px` (legitimate — these are filter chips).
Removed the now-dead, ineffective `.ba-chip{min-height:32px}` override.

**Verified, not changed** (already canonical before this pass):
"Bộ lọc nâng cao" — 126.4×38px compact disclosure (fixed in the prior
71.0.0.25 pass, re-confirmed still holding); "Lọc" — 36px height, 5px
radius; "Chi tiết thay đổi" — 32px height, 5px radius (`.btn.mini`).

## GANTT CONTAINER:

**Root cause, found from the DOM, not assumed**: `#schedulePanel`
(`.schedule-control-panel`) carried the shared `.panel` class — the
same class used for small bounded cards (KPI tiles, settings panels) —
but this particular element wraps the **entire** page body: the sticky
toolbar *and every PO's full Gantt and Material Flow section*, ~12,000px
tall on this dataset. `.panel` gives every element it's applied to
`border:1px solid`, `box-shadow`, `background:#fff`, `padding:16px
!important` — so the whole page became one giant bordered/shadowed white
frame, with the compact Production Order filter bar sitting 16px inset
inside it (each PO block, `.gantt-po`, already draws its *own* correct
compact card border independently — so this was genuinely "a giant white
card wrapping smaller white cards", exactly as reported). A negative
margin hack on `.schedule-sticky-toolbar` (`margin:0 -18px 12px`) existed
specifically to bleed the sticky toolbar back out past that same 16px
padding, which is itself evidence of the double-boxing problem.

**Fix**: dropped `.panel` from `#schedulePanel`'s class list (kept
`.schedule-control-panel` for its layout-only CSS: sticky-offset custom
properties and `overflow:visible`). Removed the now-unneeded
negative-margin bleed hack on `.schedule-sticky-toolbar` and replaced it
with normal `margin:0 0 12px;padding:12px 0 0` since there is no more
padding to counteract. Each PO's own card border, the sticky toolbar's
own background/border-bottom (needed so scrolled content doesn't show
through while pinned), the Gantt coordinates, and Material Flow are all
unaffected.

**Verified via `getBoundingClientRect()`** (real deployed 71.0.0.26,
1920×1080 and 1366×768): the panel's box now sits `background:transparent;
border:0;box-shadow:none;padding:0px` and matches `.page-shell`'s
bounding box **exactly** at both widths (1920px: panel `272–1896` =
shell `272–1896`; 1366px: panel `248–1346` = shell `248–1346` exactly)
— 0px protrusion beyond the content edge. No overlap: sticky
toolbar's bottom edge (225.3px) sits a clean 13px above the first PO
header (238.3px) at both scroll positions checked. Sticky toolbar still
pins at `top:68px` (the fix from the prior 71.0.0.25 pass), vertical
scroll (4 depths) and horizontal scroll of `.gantt-wrap` both verified
working, Material Flow renders inside each PO card as before.

## TEMPLATE COMPOSITION:

Already fixed in 71.0.0.25 (the immediately prior pass merged the
action row into the filter bar). Re-verified holding on this real
71.0.0.26 build: `#tplSearch` and `#tplNew` render on the same row
(top offset match, `tpl-search-actions-same-row` check), no standalone
action-only row, tools disclosure opens/closes correctly.

## SESSION COMPOSITION:

Already fixed in 71.0.0.25. Re-verified holding: no
`.page-header .page-header-actions` element exists on the page at all
(`sm-reload-in-filter-row` check) — "Làm mới" lives in the filter row,
refresh still works.

## EXCEPTION COMPOSITION:

Already fixed in 71.0.0.25. Re-verified holding: no `.ec-command`
hero banner exists (`ec-no-hero-banner` check), 5 canonical
`.ec-tabs .mf-tab` tabs present with the summary compacted alongside
them, "Áp dụng" works.

## KIOSK BADGE:

Already fixed in 71.0.0.25 (`.kiosk-card-head .badge` given
`inline-flex` self-centering instead of being stretched by the card
head's flex `align-items:stretch`). Re-verified holding on 71.0.0.26:
badge measures **48.2×22px**, tightly wrapping "Online", matching the
canonical small-badge height, consistent across all kiosk cards, status
color/state logic untouched.

## RBAC SAMPLE USERS:

**Authoritative model inspected first** (not assumed): `rbac_roles`
table + `mesflow.web.users.ROLES` define exactly **5** real roles —
`admin` (Quản trị viên), `manager` (Quản lý), `supervisor` (Quản đốc),
`operator` (Vận hành — "Thao tác sản xuất và kiosk"), `viewer` (Chỉ
xem). No "QA Inspector"/"Maintenance"/"Kiosk User" role exists in
`rbac_roles`, `rbac_permissions`, or `rbac_role_permissions` — per "do
not invent new roles unless already defined by MESFlow", no new role
was created. Each requested persona was mapped to its **closest real
role** instead:

| Persona | Username | Real role used | Why |
|---|---|---|---|
| System Admin | `admin` | `admin` | already existed — preserved, not duplicated |
| Production Manager | `manager` | `manager` | direct match |
| Supervisor | `supervisor` | `supervisor` | direct match |
| Operator | `operator` | `operator` | direct match (kept, not renamed to `operator1`, for backward compatibility — see below) |
| Operator (2nd, kiosk-facing) | `operator2` | `operator` | operator's own permission set already covers `kiosk.view` |
| QA Inspector | `qa` | `viewer` | closest real fit: read-only across granted screens, no edit rights — matches an inspector who reviews but doesn't mutate data |
| Maintenance | `maintenance` | `operator` | `equipment.edit` in the real RBAC is `admin`/`manager`-only; there is no dedicated low-privilege maintenance-edit scope. `operator` is the closest floor-level role without over-granting `manager`'s wider access (kiosk.manage, business_audit.view, session.edit) |
| Kiosk User 01/02 | `kiosk01`, `kiosk02` | `operator` | operator's description is literally "Thao tác sản xuất và kiosk" |

**Mechanism used**: extended the **existing** `mesflow.cli.seed_default_users()`
(already wired into `scripts/docker-entrypoint.sh`, already the
project's established seed path — no ad-hoc SQL written). Added 5 new
`(username, display_name, role, password_env_var)` entries; kept the
original 4 (`manager`/`supervisor`/`operator`/`viewer`, one per role)
byte-for-byte unchanged so any environment that already ran this with
the old spec list stays compatible. Behavior, unchanged and re-verified:
gated behind `MESFLOW_SEED_DEFAULT_USERS` (off by default — LOCAL/DEV
only, never touched Production Test/Production config), passwords come
only from environment variables (never hard-coded), idempotent
(`repo.get_by_username()` check — existing users are always preserved,
never overwritten/duplicated), and every seeded account is created with
`must_change_password=True`.

**Invoked once for this LOCAL box** via the official CLI entrypoint
(`docker exec ... python -m mesflow.cli seed-default-users` with the 9
password env vars and `MESFLOW_SEED_DEFAULT_USERS=1` passed inline —
not written into `/opt/mesflow/.env`, since editing deployed config
under `/opt` directly was denied by this session's own permission
guard and conflicts with AGENTS.md's "never develop directly under
`/opt`"). Re-ran the same command a second time immediately after:
every entry printed `exists; preserved` — idempotency confirmed, 0
duplicates. Generated dev-only passwords (14 chars, mixed
letters+digits) are saved in this session's local scratchpad only, never
committed to git, never written to `/opt`.

**Verified in User Management** (`/api/users`, real 71.0.0.26 build):
all 10 accounts (`admin` + 9 new) render with correct Vietnamese role
labels and descriptions matching `rbac_roles` exactly (Quản trị viên /
Quản lý / Quản đốc / Vận hành / Chỉ xem), "Cần đổi mật khẩu — Yêu cầu đổi
ở lần đăng nhập tiếp theo" shown for every new account, "Đang hoạt động"
status, no destructive mutation performed (existing `admin` account
untouched throughout).

## BUTTON NORMALIZATION:

- `.ba-chip`: 33.875px → 32px height (canonical compact-control height),
  radius kept at 999px (correct — genuine filter chips, not tabs/buttons).
- No other button on Business Audit needed a change — "Lọc" and "Chi
  tiết thay đổi" were already canonical (36px/5px and 32px/5px
  respectively), confirmed by direct measurement, not assumption.

## BEFORE/AFTER MEASUREMENTS:

| Metric | BEFORE | AFTER |
|---|---|---|
| Business Audit category chip height | 33.875px | 32px |
| Business Audit chip border radius | 999px | 999px (unchanged — correct) |
| Business Audit "Lọc" button height/radius | 36px / 5px | 36px / 5px (unchanged — already canonical) |
| Business Audit "Chi tiết thay đổi" height/radius | 32px / 5px | 32px / 5px (unchanged — already canonical) |
| Gantt outer PO container: background/border/shadow/padding | white / 1px solid / drop-shadow / 16px | transparent / 0 / none / 0px |
| Gantt outer PO container box vs. page-content edge (1920px) | container inset ~16px inside a taller-than-needed card | container `x:272,right:1896` == page-shell `x:272,right:1896` exactly |
| Gantt outer PO container box vs. page-content edge (1366px) | same double-card pattern | container `x:248,right:1346` == page-shell `x:248,right:1346` exactly |
| Kiosk Online badge size | 48.2 × 22px (fixed in 71.0.0.25) | 48.2 × 22px (re-confirmed holding) |
| Template action-row | merged into filter row (fixed in 71.0.0.25) | re-confirmed holding |
| Session top gap | 0px, refresh in filter row (fixed in 71.0.0.25) | re-confirmed holding |
| Exception summary strip | compact, in tab row (fixed in 71.0.0.25) | re-confirmed holding |
| RBAC sample users | 1 (`admin` only) | 10 (`admin` + 9 role-mapped sample users) |

## 1920x1080:

Captured against the real deployed 71.0.0.26 build for all 7 pages:
`after-business-audit-1920x1080.png`, `after-production-schedule-1920x1080.png`,
`after-templates-1920x1080.png`, `after-session-management-1920x1080.png`,
`after-session-exceptions-1920x1080.png`, `after-kiosk-management-1920x1080.png`,
`after-users-1920x1080.png`, under
`reports/screenshots/remaining-defects-fix/`. All defects listed in the
task confirmed fixed by direct visual inspection, matching the DOM
measurements above.

## 1366x768:

Same 7 pages captured at 1366×768. Business Audit chips stay compact
and wrap cleanly; Gantt's Production Order area is a plain compact
filter bar with no outer white frame, PO card header/timeline fully
visible directly beneath it; Templates/Session/Exception/Kiosk
compositions hold from the prior pass; Users table reflows without
horizontal overflow.

## PAGE ERRORS:

0 in this pass's own functional-smoke run (both viewports). Note: the
pre-existing, out-of-scope `app.js:982` orphaned-`keydown`-listener bug
documented in the prior report (`UI_FINAL_COMPOSITION_FIXES.md`) is
untouched by this diff and was not re-triggered by this pass's specific
click sequence — still present in the code, still out of this task's
explicit scope, not fixed here.

## CONSOLE ERRORS:

0 across all 7 pages, both viewports, real deployed 71.0.0.26 build.

## OVERFLOW:

0px unintended horizontal overflow on Business Audit, Production
Schedule, Templates, Session Management, Exception Center, Kiosk
Management, Users — both 1920×1080 and 1366×768.

## CSS CHECK:

`ui.css` brace balance: 2860 `{` / 2860 `}`, custom comment/string-aware
depth-scanner final depth 0. `git diff --check`: clean (no
trailing-whitespace/conflict-marker issues).

## JS CHECK:

`node --check app/mesflow/web/static/app.js` — OK.

## PYTHON CHECK:

`python3 -m py_compile app/mesflow/cli.py` — OK.

## JINJA CHECK:

All templates under `app/mesflow/web/templates/**/*.html` load cleanly
via Jinja2's `Environment.get_template()` — 0 syntax errors (none of
this pass's changes touched a template, checked as a full-repo
regression guard anyway).

## PYTEST:

`pytest tests/test_v71_ui_foundation.py tests/test_web_ui.py` — 7/7
passed. (The broader `tests/` suite has 9 pre-existing collection
errors unrelated to this change — missing `psycopg` module and
`DATABASE_URL` not set for this shell's Python environment; those tests
only run inside the Docker container's own environment. No test in the
repo covers `seed_default_users()` directly; its behavior was verified
live instead — see RBAC SAMPLE USERS above.)

## FULL UI AUDIT:

39-check composition-regression suite (Production Order, Exception
Center, Production Trace, Business Audit, Production Schedule incl.
`ps-sticky-toolbar-pinned top=68`, Kiosk Management, Guidance) — 39/39
pass against the real deployed 71.0.0.26 build.

## FUNCTIONAL SMOKE:

48/48 checks (24 checks × 2 viewports) against the real deployed
71.0.0.26 build: Business Audit (category filter, category selection,
advanced-filter toggle, Lọc, detail drawer), Production Schedule/Gantt
(no toolbar/PO overlap, panel within page boundary at both widths, PO
filter, refresh, Gantt present, Material Flow present, sticky pinned at
`top:68`, horizontal scroll), Templates (search+actions same row, tools
dropdown), Session Management (no standalone action row, refresh),
Exception Center (no hero banner, canonical tabs, apply), Kiosk
Management (search, refresh), Users (sample users visible, 10 total
accounts). 0 failures.

## LOCAL BUILD:

`scripts/build-release.sh --bump` → `IMAGE RELEASE PASS`. Version
71.0.0.25 → **71.0.0.26**. Image `mesflow-app:71.0.0.26`, digest
`sha256:159daf43dd8326d7d2c06ab2aecf2588d9dae38d8e17692dcccdec0a37227a05`,
schema `0037_v72_audit_operations_separation`, package
`artifacts/releases/71.0.0.26/MESFlow_71.0.0.26.deploy.zip`.

## LOCAL DEPLOY:

Deploy Agent `POST /agent/api/release-manager/deploy-local
{"version":"71.0.0.26"}` → job `success`. Steps: backup
(`source_20260817_043015_c7e3dba7`) → stage → install → restart ("MES
Docker stack started; PostgreSQL data preserved") → health ("Version
71.0.0.26 and health verified") → rollback skipped (not required).
`from_version: 71.0.0.25`.

## LOCAL HEALTH:

`GET /api/system/health` (via Deploy Agent status) → `{"ok": true,
"status": "healthy", "version": "71.0.0.26", "postgres_version":
"17.10", "schema_version": "72.0.0.0"}`. `docker ps` confirms
`mesflow-app:71.0.0.26` (healthy). All 10 users (including the 9 new
sample accounts) confirmed present in PostgreSQL after the deploy —
data survived the cutover.

POSTGRES RESTARTED: NO
PRODUCTION TEST TOUCHED: NO
PRODUCTION TOUCHED: NO
