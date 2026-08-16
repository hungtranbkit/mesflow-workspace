# MESFlow UI Visual Polish — Pass 2

Date: 2026-08-16
Project: `~/workspace/mesflow/mesflow`
Branch: `sync/reconcile-mesflow-65.8.44.51`
Commit: `ddb604c` (parent `d9ef974`)

## Context

Pass 1 (see `reports/UI_QUALITY_AUDIT_FINAL.md`) audited all 16 pages but changed
only two technical CSS defects (an overflow trap and a stray disclosure marker)
and judged most pages "already consistent." This pass was explicitly requested
as a **second, less conservative** visual polish: same application, same
workflows, but noticeably cleaner, more aligned, more consistent, more modern,
and easier to scan. No route, API, business-logic, workflow, permission, or
database change was made anywhere in this pass.

`docs/ui/MESFLOW_UI_STANDARD.md` was read first and used as the reference
vocabulary (Carbon/Ant/Impeccable references, 4/8/12/16/24/32 spacing scale,
industrial density, avoid AI-generic dashboards/excessive color/oversized cards).

## VERSION

| | |
|---|---|
| Version before this pass | 71.0.0.8 (already frozen, per Pass 1) |
| Version after this pass | **71.0.0.9** (71.0.0.6/.7/.8 were all already frozen; bumped via `build-release.sh --bump`) |

## Method

1. Read `ui.css` in full (981 lines, ~2,975 rule blocks across three layered
   `:root` token generations: a legacy base, a "canonical implementation," and
   an "Industrial Soft-3D" elevation/shadow layer, plus a V71 `--ui-*` token
   set at the end) to find what already existed before adding anything new.
2. Cross-referenced every CSS class against actual page-render code in
   `app.js`/`pages/*.js` (not just CSS existence) to tell live components from
   dead CSS — e.g. confirmed the ~120-line `.se-*` Session Exceptions block is
   dead (superseded by `exception-center.js`'s `.ec-*` markup) and left it
   untouched rather than "polishing" unreachable code.
3. Found concrete, verifiable gaps (not invented ones): `.btn.tertiary`/`.ghost`
   used in markup with zero CSS definition; the sidebar's "active page"
   indicator effectively invisible (1px white line on navy) and missing
   entirely on nested sub-items, which is how most pages are actually reached;
   KPI/summary cards with no visual identity in the default (non-flagged)
   state; RUNNING/OPEN sharing the amber tone with actual at-risk states;
   classic `<table>` headers not uppercased like the newer `.ui-data-table`.
4. Implemented as one clearly-commented, additive "UI Visual Polish Pass 2"
   block at the end of `ui.css` (following the file's own established pattern
   of versioned additive sections, e.g. "v65.8.44.30", "V71 UX foundation") —
   never rewrote or restructured the existing 981 lines.
5. Iterated screenshot -> change -> screenshot on live preview (via `docker cp`
   into the running `mesflow-app:71.0.0.8` container, reverted afterward) for
   Overview, Employees, Kiosk Management, Session Management, Production
   Orders, Dashboard, System Logs, Business Audit, Session Exceptions before
   ever building — the KPI-card accent went through two iterations (grey at
   0.6 opacity was too subtle in the actual screenshot review; changed to a
   brand-tinted `--action-primary` at 0.3 opacity) and the nav accent went
   through one iteration (initial rule only covered top-level `.sidebar-item`;
   screenshot showed nested `.sidebar-sub-item` — where most real navigation
   happens — was untouched, so the rule was extended).
6. Built 71.0.0.9, deployed LOCAL via Deploy Agent's official API, then
   re-ran the full 16x2 Playwright audit and a 12-check functional smoke pass
   against the real deployed build (not just the preview).

## PAGE-BY-PAGE VERDICT

| PAGE | Before issues | Changes | Result |
|---|---|---|---|
| Overview | Cards/rows are a custom grid, not `.card`/`table` — already reviewed clean in Pass 1 | Global chrome only (nav active-state, page-title weight) | GOOD AS-IS |
| Dashboard | `.daily-kpi` cards had no visual identity in the normal (non-flagged) state — a row of 4 read as one grey block | KPI top-accent strip added | POLISHED |
| Production Orders | `<table>` header used default case, thin separator, drifted from the newer table style | Table header uppercase + letter-spacing + 2px separator | POLISHED |
| Templates | No table, no KPI card, no ghost button in its own content | Global chrome only | GOOD AS-IS |
| Employees | `<table>` + `.employee-summary` KPI cards, both pre-dated the newer visual language | Table header uppercase; KPI top-accent | POLISHED |
| Session Management | "Xóa bộ lọc" rendered with the exact same weight as every primary button (class existed, no CSS) | Real ghost/tertiary button style | POLISHED |
| Session Exceptions | Already reviewed strong in Pass 1 (banner/tabs/severity-striped `.ec-card`s); no table/KPI-card/ghost-button in its content | Global chrome only | GOOD AS-IS |
| Production Trace | Custom timeline/event component, no table/KPI-card | Global chrome only | GOOD AS-IS |
| Business Audit | `.ba-chip` filter chips a different height than the rest of the toolbar row, uneven baseline | Chips aligned to shared ~32px control height | POLISHED |
| Production Schedule (Gantt & Material Flow) | Material Flow drill-down modal's `<table>` had the same header drift as other classic tables | Table header uppercase (applies when the modal opens) | POLISHED |
| Kiosk Management | `.daily-kpi` summary cards no default identity; 25+ clickable `.kiosk-card` tiles had zero hover feedback in a dense grid | KPI top-accent; added hover lift+border to `.kiosk-card` | POLISHED |
| System Logs | Stat cards (`.card`) no accent; both tables (Action Log, Error Trace) had the classic header drift | KPI top-accent; table header uppercase | POLISHED |
| QR Print | Card grid uses its own `.qr-catalog-card` selection style (checkbox-based, not click-to-open) — already appropriate, no table/KPI-card | Global chrome only | GOOD AS-IS |
| Equipment | `.catalog-summary` KPI cards + `<table>`, both pre-dated the newer language | KPI top-accent; table header uppercase | POLISHED |
| Users | `.system-user-summary` KPI cards + `<table>` (+ RBAC matrix table in the permissions modal) | KPI top-accent; table header uppercase | POLISHED |
| Working Calendar | `<table>` (Danh sách ca làm việc) had the classic header drift | Table header uppercase | POLISHED |

**11 of 16 pages POLISHED, 5 GOOD AS-IS.** The 5 GOOD AS-IS pages were checked
against every shared class touched in this pass (grep-verified against their
actual render functions, not assumed) and genuinely don't contain any of the
touched components — they still benefit from the global nav/header chrome
polish that applies everywhere, but nothing page-specific needed changing.

## SHARED CSS CHANGES

All added as one block at the end of `ui.css`, additive on top of the
existing token system (never redefines an existing token's meaning):

1. **Button hierarchy** — `.btn.tertiary`/`.btn.ghost` had zero CSS rules
   despite being used in markup (`MFUI.filterBar`'s "Xóa bộ lọc"). Added a
   real recessed style: transparent border/background, muted text, no
   button-shadow, subtle hover fill. Primary actions are now unambiguous
   next to secondary ones.
2. **KPI/summary card identity** — `.card`, `.daily-kpi`, `.pc-kpi`,
   `.catalog-summary article`, `.system-user-summary article`,
   `.employee-summary article` all get a 3px top-accent strip, brand-tinted
   at low opacity by default, full-strength semantic color when
   `.critical`/`.warning`. Card-grid gap bumped 12px → 14px so accented
   cards read as distinct units instead of a fused block.
3. **Sidebar navigation active state** — the shipped indicator was a 1px
   white inset line on a dark-navy background (effectively invisible,
   confirmed via screenshot) and only applied to top-level `.sidebar-item`,
   not nested `.sidebar-sub-item` (how most pages are actually reached).
   Replaced with a clearly visible accent bar + distinct hover/active fill,
   applied consistently to items, sub-items, and group triggers.
4. **Status tone system** — added `.ui-status-info` (blue) and remapped
   RUNNING/OPEN to it in `core/ui.js`'s `tone()` (previously shared the
   amber "warning" tone with DEGRADED/BLOCKED/ACKNOWLEDGED).
5. **Classic table header consistency** — `.table-wrap table th` now
   uppercases with letter-spacing and a 2px header/body separator, matching
   the newer `.ui-data-table`'s language so every table in the app scans
   the same way.
6. **Page header micro-polish** — consistent title weight (750) and a
   visible bottom rule across both the classic `.workspace-header` and the
   V71 `.ui-page-header` shell.
7. Extended the `--ui-space-*` scale with `--ui-space-6:32px` (completing
   4/8/12/16/24/32) and added named typography-scale tokens
   (`--ui-fs-page-title/section-title/card-title/body/meta/kpi`) for future
   rules to reference, without rewriting the ~30 already-scattered
   `.panel-head` redeclarations across responsive breakpoints (a much larger,
   separate refactor than this pass's scope — noted under Known Issues).

## PAGE-SPECIFIC CHANGES

- **Kiosk Management**: `.kiosk-card` (25+ clickable tiles/page) had no
  hover feedback; added the lift+border treatment already used elsewhere by
  `.tutorial-card`.
- **Business Audit**: `.ba-chip` filter chips brought to the shared ~32px
  control height so the toolbar row doesn't look fragmented.

## TYPOGRAPHY

Page title weight strengthened to 750 (classic `.workspace-header h1` and
V71 `.ui-page-header h2` both, so every page opens with the same clear
"title / description / actions" band). Named scale tokens added for future
use. Existing size scale (24/21/20/16/15/13/12/11) was already reasonably
consistent and was not rewritten wholesale — see Known Issues.

## SPACING

Completed the 4/8/12/16/24/**32** scale (`--ui-space-6`). Card/KPI grid gap
12px → 14px. Did not do a blanket rewrite of the file's many already-on-scale
hardcoded values (8/10/12/14/16/18/20/22/24 — nearly all already multiples of
2/4) — see Known Issues for the handful of off-scale legacy values left as-is.

## CARDS

Every KPI/summary card across Dashboard, Kiosk Management, Employees,
Equipment, Users, System Logs now carries a top-accent identity strip
(neutral brand tint by default, full semantic color when flagged
critical/warning) and sits with more breathing room (14px grid gap). Kiosk
cards gained hover feedback.

## TABLES

Production Orders, Employees, Equipment, Users, Working Calendar, System
Logs (both tabs), and the Material Flow drill-down modal all now share one
header language: uppercase, letter-spaced, 2px separator — previously only
the newer `.ui-data-table` primitive had this.

## FILTERS

Session Management's filter bar ("Xóa bộ lọc") now visibly reads as a
secondary/tertiary action next to "Thêm bộ lọc" and "Làm mới", instead of
matching their weight exactly.

## BUTTONS

`.btn.tertiary`/`.ghost` now have a real, distinct, lower-weight visual
treatment — the single highest-leverage button-hierarchy fix available,
since it was previously entirely undefined CSS.

## STATUS

Added a fourth semantic tone (`info`, blue) so "in progress" (RUNNING/OPEN)
is visually distinct from "needs attention" (DEGRADED/BLOCKED/ACKNOWLEDGED/
WARNING) wherever `MFUI.statusBadge`/`core/ui.js`'s `tone()` is used.

## NAVIGATION

Active-page indicator changed from an effectively invisible 1px white line
to a clearly visible accent bar + fill, and — critically — extended to
nested sub-items and group triggers, which is how the large majority of
pages are actually reached (confirmed via screenshot: "Nhân viên" nested
under "Danh mục" now clearly reads as the current page; before, it did not).

## FILES CHANGED

- `app/mesflow/web/static/ui.css` — +108 lines (one additive block)
- `app/mesflow/web/static/core/ui.js` — `tone()` gains an `info` branch
- `VERSION.txt`, `app/mesflow/__init__.py`, `compose.yml`, `release.json` —
  version bump 71.0.0.8 → 71.0.0.9 (via `build-release.sh --bump`)

No JS page-renderer, template, Python, migration, or test file was modified.
The large pre-existing V66–V74 feature pile was left completely untouched
and unstaged, same as Pass 1.

## SCREENSHOTS

- Before (= Pass 1's final state, unchanged since): `reports/screenshots/mesflow-ui-audit-after/` (32 files, 1920×1080 + 1366×768 × 16 pages)
- After, deployed 71.0.0.9: `reports/screenshots/mesflow-ui-polish-pass2-deployed/` (32 files, same matrix)
- Intermediate live-preview iterations (not part of any build, `docker cp` into 71.0.0.8 and reverted): `reports/screenshots/mesflow-ui-polish-pass2-after/`

1920×1080 and 1366×768 were both captured for every page; no new overflow was
introduced at either viewport (see Playwright results below).

## LOCAL BUILD

```
build-release.sh --bump
IMAGE RELEASE PASS
Version: 71.0.0.9
Image: mesflow-app:71.0.0.9
Digest: sha256:9c687b94e5924f79daa5a4ab9aab8f19e3e90bc5cb897c1c2e9d5a1282c9640f
Schema: 0037_v72_audit_operations_separation
```

## LOCAL DEPLOY

Deployed via Deploy Agent's official `POST /agent/api/release-manager/deploy-local`
(the same action the Deploy Agent UI's "Deploy Local" button performs) against
the local DEV agent (`http://127.0.0.1:8090`), version `71.0.0.9`.

Job progression: `deploying` → `"CUTOVER: stopping application only; gateway
and PostgreSQL remain running"` → `"Installed staged Docker release files for
71.0.0.9"` → `verifying` → **`success — "Deployment verified: 71.0.0.9"`**.

Health after deploy:
```json
{"status":"healthy","ok":true,"version":"71.0.0.9","schema_version":"72.0.0.0",
 "database_backend":"postgresql","postgres_version":"17.10"}
```
`mesflow-postgres` uptime unaffected (25h, never restarted).

## PLAYWRIGHT (against the real deployed 71.0.0.9)

| Metric | Result |
|---|---|
| Pages × viewports captured | 32 (16 pages × 1920×1080 + 1366×768) |
| Page errors | 0 |
| Console errors | 0 |
| Failed requests | 0 |
| Horizontal overflow | 0 |

## FUNCTIONAL SMOKE (12 checks, against the real deployed 71.0.0.9)

Login; Production Orders → open PO detail; back navigation; Session
Management → "Thêm bộ lọc" disclosure toggle; Session Exceptions → tab
switch, card → drawer open, drawer close; Templates → "Công cụ" disclosure
toggle; zero console errors; zero failed requests during the full run.

**12/12 passed.** No destructive actions were executed.

## STATIC CHECKS

| Check | Result |
|---|---|
| CSS brace balance (`ui.css`) | balanced (2,975 open / 2,975 close after the addition) |
| `git diff --check` | clean |
| JS syntax (`node --check core/ui.js`) | OK |
| Python compile sanity (`web/app.py`) | OK |
| Jinja parse (`app.html`, unchanged) | OK |
| `tests/test_v71_ui_foundation.py`, `tests/test_web_ui.py` | 7 passed, 0 failed |

## KNOWN ISSUES / NOT DONE (honest scope notes)

- `.panel-head` is redeclared ~30 times across the file (mostly responsive/
  page-specific stacking overrides accumulated over many prior changes).
  Consolidating that into one canonical rule is a real, separate refactor —
  larger and riskier than a "polish pass," and was intentionally left alone
  rather than risk breaking a page-specific mobile layout no screenshot in
  this pass happened to cover.
- Numeric table-column right-alignment (explicitly listed in the task's
  table checklist) was not implemented: no current table marks its numeric
  cells with a class the CSS could target, and adding `nth-child` heuristics
  is fragile against future column reordering. Doing this properly needs a
  small JS markup change per table (adding a data attribute/class to numeric
  `<td>`s) rather than a CSS-only fix — flagged here rather than done with a
  fragile shortcut.
- `.se-*` (Session Exceptions' original master/detail CSS, ~120 lines) is
  confirmed dead code (superseded by `exception-center.js`'s `.ec-*`
  markup) and was left untouched — polishing unreachable CSS has no visible
  effect and removing it is a cleanup task, not a visual-polish task.
- Category badge colors on Business Audit (`.ba-action-badge`, 8 distinct
  hues) are more colors than the standard's "avoid excessive colors"
  guidance prefers, but they carry real category meaning users rely on;
  changing that is a deliberate design decision, not a polish-pass call, so
  it was left as-is.

**PRODUCTION TEST TOUCHED: NO**
**PRODUCTION TOUCHED: NO**
