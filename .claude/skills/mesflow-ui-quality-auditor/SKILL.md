---
name: mesflow-ui-quality-auditor
description: Use when the user asks to audit, review, polish, clean up, tighten, or fix visual/UI quality in any MESFlow-family app (deploy-agent, mesflow, qa-center, bootstrap, mesflow-web) -- alignment, spacing, spacing consistency, typography, button/input heights, table layout, card boundaries, tab wrapping, drawers/modals, or responsive overflow at 1920x1080/1366x768. Also use for "make this screen look professional/impeccable", finding P0/P1/P2/P3 UI defects, or producing reports/UI_QUALITY_AUDIT.md. Not for new features, backend/business-logic changes, API semantics, or framework rewrites.
---

# MESFlow UI Quality Auditor

Audits and polishes existing MESFlow-family web UIs without changing business logic or unnecessarily redesigning working screens. Covers `deploy-agent/`, `mesflow/`, `qa-center/`, `bootstrap/`, and `mesflow-web/` where applicable.

Read `docs/ui/MESFLOW_UI_STANDARD.md` and the top-level `AGENTS.md` first (Project boundary rule, per-project version/build rules). Those are the authority when this skill's guidance and theirs would otherwise diverge — never contradict them.

## Core principle

**Do not start by editing CSS.** Systemic issues (a shared class missing a property) look like dozens of page-specific defects until you check the shared primitive; fixing each occurrence separately creates duplicate, drifting CSS. Sequence:

1. Discover routes/pages (grep the router/template list; don't guess).
2. Inspect the current design system / shared primitives (tokens, `Button`/`Card`/`Table`/`FormRow`-equivalents).
3. Render pages in a real browser at real size.
4. Classify each defect as systemic (shared component/class) vs page-specific (one screen's markup).
5. Fix shared causes first, then remaining page-specific defects.

A real worked example from this codebase: MESFlow's Session Management filter bar had labels sitting flush against their inputs (`<label>Ngày<input...></label>`, zero separation in the markup). The fix was not a one-off page rule -- `ui.css` already had the correct pattern on three *other* toolbars (`.overview-filters label{display:grid;gap:5px}` + `<span>` for the label text, folded into the existing shared `label>span{font-size:12px;font-weight:650;color:#4a5866}` typography rule). The fix extended that existing shared rule (`.ui-filter-controls label{display:grid;gap:5px}` + wrapped label text in `<span>`) instead of inventing new CSS. That is the standard this skill enforces: find the existing convention before writing anything new.

## Per-project map

Discover-first still applies -- treat this table as a starting point, not ground truth; a project's structure can have moved since this was written.

| Project | Stack | Page source | Shared CSS / tokens | Local dev run | Default port | Git repo |
|---|---|---|---|---|---|---|
| `deploy-agent/` | Flask + Jinja | `templates/*.html`, `templates/release/*.html`, `templates/kiosk/*.html` | `static/css/agent.css` (`--ops-*`, `--space-*`, `--radius-*` tokens); some templates (e.g. `templates/release/index.html`) also carry a large page-scoped inline `<style>` block -- check both | isolated run, see below | 8090 | own repo (`deploy-agent/`) |
| `mesflow/` | Flask + Jinja shell, pages rendered client-side by `static/app.js`/`static/pages/*.js` | `app/mesflow/web/templates/app.html` (shell only) | `app/mesflow/web/static/ui.css` (`--ui-space-1..5` = 4/8/12/16/24px; `label>span` shared typography rule) | `docker compose up` (full stack incl. Postgres) or a bare `flask run` against an already-migrated DB | 8080 | own repo (`mesflow/`) |
| `qa-center/` | Flask + Jinja, single dashboard page | `current/templates/index.html`, `current/templates/kiosk.html` | `current/static/app.css` (CSS variables, own scale) | `python current/agent.py` with `MESFLOW_QA_*` env | 8095 | own repo (`qa-center/`) |
| `bootstrap/` | Flask + Jinja | `templates/*.html` (`base.html` is the shell) | `static/style.css` (`:root` has color tokens only -- no spacing scale defined yet, note this as a P2/P3 opportunity if touched) | `python app.py` (waitress) or the real `mesflow-bootstrap` systemd service | 8098 | outer workspace repo |
| `mesflow-web/` | React 19 + Vite + TS + Tailwind v4 + Radix UI | `src/` (router in `src/app/router.tsx`) | `src/index.css` (`:root` + Tailwind `@theme` tokens) | `npm run dev` | 5173 | outer workspace repo |

Git boundary: `deploy-agent/`, `mesflow/`, `qa-center/` are each their own git repository, independent of the outer workspace repo that `bootstrap/` and `mesflow-web/` live in. Never mix a commit across two of these -- stage and commit only the files that belong to the repo you're actually in, exactly like any other change in this workspace (see `AGENTS.md` "Project boundary rule"). A repo frequently has a large amount of *pre-existing* unrelated uncommitted work sitting in it; `git add` only the files this audit actually touched, never `git add -A`.

## Browser audit

Use a real browser against the real running app, not a mental model of the CSS.

**Primary viewport:** 1920x1080. **Secondary:** 1366x768.

**Tool choice:**
- `mesflow-web/` already has Playwright wired in (`playwright.config.ts`, `tests/`, `npm run test:e2e`). Prefer real Playwright there, and add/extend a spec under `tests/` if the audit is going to be repeated.
- The four Python/Flask apps do not have the `playwright` Python package installed by default in this environment, but Chromium browsers are typically already cached under `~/.cache/ms-playwright` (installing `playwright` and running `playwright install chromium` reuses that cache, no re-download). If Playwright isn't available or isn't worth the setup for a narrow check, a system `google-chrome`/`chromium` binary is a reliable fallback:
  ```bash
  google-chrome --headless --disable-gpu --no-sandbox \
    --window-size=1920,1080 --screenshot=/path/out.png \
    "http://127.0.0.1:<port>/<route>"
  ```
- For a fix that's already narrowed down to one component (markup + CSS, no backend data needed), a full app boot is unnecessary: build a small standalone HTML file that `<link>`s the project's real CSS file via an absolute `file://` path plus the exact HTML fragment (before and after), and screenshot that directly. This is fast, gives an honest side-by-side, and was used successfully in this codebase to prove a filter-bar label-spacing fix before shipping it. Get the "before" HTML/CSS from `git show HEAD:path/to/file.css` (or the pre-edit version) so the comparison is real, not two copies of the already-fixed file.

**Isolated local run for the Python/Flask apps** (never point a throwaway audit run at the real shared Docker daemon's production containers -- a past incident in this workspace had a spawned "throwaway" process mutate real containers):
- `deploy-agent/`: set an isolated `WORKSHOP_AGENT_HOME` (a scratch dir with `config/` and `data/logs/` created), plus `SERVER_ROLE`, `MESFLOW_BUILD_ENABLED`, `MESFLOW_QA_URL=http://127.0.0.1:1`, `WORKSHOP_MES_URL=http://127.0.0.1:1`, and **`MESFLOW_POSTGRES_CONTAINER=<name that provably does not exist>`** (the default container name is the real production Postgres container -- this env var is a hard safety requirement, not optional, for any spawned instance). `deploy-agent/tests/conftest.py`'s `spawn_agent()` is the canonical reference for the full safe env set.
- `qa-center/`: set `MESFLOW_QA_CONFIG_PATH`/`_LOG_DIR`/`_REPORT_DIR`/`_STATE_DIR` to a scratch dir before running `current/agent.py` directly, so it never touches the real deployed instance's `/data`.
- `mesflow/`: prefer auditing against an already-running DEV-role instance (read-only page loads are safe) over spinning up a second Postgres-backed stack just for a UI pass, unless the audit needs to be fully isolated.
- `bootstrap/`: read-only page audits against the real running instance are low-risk (no destructive actions triggered by merely loading pages); avoid actually clicking service-control/install actions during an audit.

**For every important page, check:** horizontal overflow, vertical layout anomalies, alignment, spacing consistency, control heights, card boundaries, table layout, tab wrapping, buttons, forms, dialogs/drawers, empty/error states.

Capture screenshots before and after every change.

## Visual quality checklist

**Alignment** -- common left edges; common baselines; headers aligned; action groups aligned; labels/values aligned.

**Spacing** -- consistent page padding; section spacing; card padding; form gaps; button group gaps.

**Typography** -- page title hierarchy; section title hierarchy; body text; metadata; no random font sizes/weights.

**Controls** -- buttons at a standard height; inputs/selects at the same height; icon/text alignment; disabled states still readable.

**Tables** -- headers aligned; predictable row height; actions don't wrap badly; long text handled safely (`text-overflow`/wrap, never silent clipping of meaningful data); overflow contained inside the table's own scroll region, never the page.

**Cards** -- consistent border/radius; header/body spacing; status cards the same height when shown in one row.

**Tabs/nav** -- no awkward wrapping; active state consistent; no layout shift when a tab is selected.

**Modals/drawers** -- consistent width; header/footer alignment; close actions predictable; long content scrolls internally, never the whole page.

**Responsive** -- no page-wide horizontal overflow; important actions stay reachable; layouts degrade gracefully at 1366x768.

## Design system first

Audit shared CSS/components before touching any individual page. Examples of the shared primitives to look for in this codebase (names vary per project -- discover the real ones, don't assume): Button, Input, Select, Badge, Card, Table, PageHeader, Tabs, Drawer, Modal, FormRow.

If a defect affects multiple pages, **fix the shared primitive** -- a class like `.ui-filter-controls label`, `.ops-badge`, `.rel-card` in `deploy-agent`/`mesflow`, or a shared React component in `mesflow-web`. Never write the same fix N times as page-scoped CSS; that is exactly how a design system rots.

## Measurable consistency

Use the project's existing spacing scale if one exists (`mesflow`'s `ui.css` already defines `--ui-space-1..5` = 4/8/12/16/24px; `deploy-agent`'s `agent.css` defines an equivalent `--space-1..6` = 4/8/12/16/20/24px). When a project has no formal scale yet but an informal one is visible in practice (e.g. `bootstrap`'s `style.css` reuses `5px`/`6px`/`8px`/`12px` literals across its toolbars), match that existing informal convention rather than inventing a third value nearby. Do not introduce arbitrary values like `13px`/`17px`/`23px` unless an existing, intentional design already uses them.

## Do not

- Change backend business logic or API semantics.
- Restructure navigation without a specific, named reason.
- Replace a working UI wholesale when a targeted fix solves the reported problem.
- Introduce a new framework (or migrate a page to a different one, e.g. Classic UI to React) merely for polish -- that migration, if wanted, is its own separate task with its own scope, not something this skill decides to do opportunistically.
- Convert every page to React.
- Change production workflows (deploy/promote/rollback logic, approval gates).
- Hide or remove functionality to make a layout easier to fix.

## Priority classification

- **P0 Broken** -- controls inaccessible, content overlaps, a screen effectively disappears, page overflow blocks normal use.
- **P1 UX** -- badly aligned controls, confusing action hierarchy, a table that's unusable, a broken responsive state.
- **P2 Consistency** -- padding differences, inconsistent control heights, typography variation, inconsistent cards.
- **P3 Polish** -- minor visual refinement.

Fix P0/P1 first. P2/P3 are worth batching into the same pass when the shared-primitive fix already covers them for free, but don't let chasing P3 polish delay shipping a P0/P1 fix.

## Shipping the fix (Build Once applies here too)

A template/CSS/JS edit in `deploy-agent/`, `mesflow/`, or `qa-center/` is not live just because the file changed on disk -- these three follow the workspace's Build Once model. After editing:
1. Commit only the files this audit touched, in the correct repo.
2. Bump that project's own version (`scripts/bump-version.sh` exists in all three now; deploy-agent's Release & Deploy page also has "Nâng version" buttons for MESFlow/QA Center, and the Agent Update tab has one for Deploy Agent itself -- prefer those over hand-editing version files).
3. Build with that project's canonical builder (`scripts/build-release.sh` for `mesflow`/`qa-center`, `scripts/build-agent-release.sh` for `deploy-agent`) -- never hand-build an image another way.
4. Deploy Local (or the equivalent redeploy step for `deploy-agent`'s own container) to actually see the fix running, before calling the audit complete.

`bootstrap/`'s `install.sh` is idempotent and has no separate version/build pipeline -- re-running it refreshes the served code directly. `mesflow-web/`'s build/deploy path (`npm run build`, then however the built assets reach nginx/production) was not established by this skill and should be discovered/asked about before assuming a shipping mechanism.

## Visual regression

After changes, revisit every modified page with the browser and compare before/after screenshots. Verify:
- Page errors = 0
- Console errors = 0
- Page horizontal overflow = 0 (at both 1920x1080 and 1366x768)

Run the project's own typecheck / lint / tests / template-parsing / build steps as applicable (`node --check` for a Jinja app's JS, `python3 -m py_compile` for touched `.py`, the project's real `pytest`/`npm run typecheck`/`npm run lint`/`npm run test:e2e`, etc.) -- these catch a broken edit before a human ever loads the page.

## Report

Produce `reports/UI_QUALITY_AUDIT.md` in the relevant project (or the workspace root `reports/` if the audit spans multiple projects), with this shape:

```
PAGES AUDITED:
SHARED COMPONENTS AUDITED:

P0:
P1:
P2:
P3:

SHARED FIXES:
PAGE-SPECIFIC FIXES:

ALIGNMENT:
SPACING:
TYPOGRAPHY:
BUTTONS:
FORMS:
TABLES:
CARDS:
TABS:
DRAWERS/MODALS:
RESPONSIVE:

1920x1080:
1366x768:

PAGE ERRORS:
CONSOLE ERRORS:
OVERFLOW:

BUSINESS LOGIC CHANGED: NO
```

Every finding line should be concrete (`file:line` or a component/class name plus the page(s) it affects), not a restatement of the checklist category name.
