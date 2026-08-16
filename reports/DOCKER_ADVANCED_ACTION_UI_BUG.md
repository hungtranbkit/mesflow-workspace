
# Docker Advanced Action UI Bug — Investigation & Hardening

Project: `deploy-agent/`. Reported bug: on Operations → Docker
(`/ops?view=docker`), clicking "Thao tác nâng cao" on a container row
makes the entire Docker list disappear; a browser reload restores it.

## REPRODUCTION

Per the task's explicit "reproduce first" mandate, this was tested live
against the real running local Deploy Agent (confirmed byte-identical
source to the workspace — `diff` between the container's
`/app/templates/ops.html` and the workspace file showed no differences)
using headless Chromium via Playwright, real login, and this host's real
18-container `docker ps -a` output. Tested:

- Every one of the 18 real rows individually (click → assert row count/
  DOM/console/page errors → next row).
- Wide (1920×1080) and narrow (820×900) viewports.
- With the container-name filter populated first, then toggling.
- After an idle wait crossing the 15s Operations health-poll interval.
- Opening 5 rows in sequence (state-accumulation check).
- Direct DOM-integrity assertions before/after each click: table count,
  tbody count, row count, `<details>` count, section `display`/class,
  `tablewrap` scroll metrics.
- The same `<details>`-based pattern on the newer "Dịch vụ" (Operations →
  Dịch vụ) page, in case of page confusion.

**Result: the described symptom did not reproduce in any variant.**
Every check stayed correct: 1 `<table>`, 1 `<tbody>`, row count unchanged
(18 before, 18 after, on every row), the Docker list and its
`.tablewrap` container stayed visible throughout, `<details open>`
toggled correctly for exactly the clicked row, no other row's
visibility changed, no document navigation, and zero console/page
errors across every single run.

Every specific failure mode the task itself lists was checked directly
against the source and ruled out: no wrong/overly-broad selector (the
render only ever touches `dockerRows.innerHTML`, exactly the Docker
`<tbody>`), no `hidden` toggling on a parent container (native
`<details>` only affects its own subtree), no duplicate DOM ids (checked
statically across the whole template — none), no click-handler bubbling
to a parent (no parent click listeners exist for this section), no
`<form>` wraps the Docker table anywhere in `ops.html` or the shared
shell partials (the only `<form>` on the page is the unrelated,
self-contained logout button in the header), no accordion/details markup
closing/replacing the wrong node (verified via DOM structure dump before
and after), no shared global state mutation on toggle (`dockers`/
`renderDocker()` are only touched by `loadDocker()`/the filter input,
neither of which a `<summary>` click triggers), no CSS rule hides the
table (read the entire `agent.css`, nothing matches), and the route/URL
never changed during the click.

Given the discrepancy between a clearly detailed bug report and an
extensively negative live-reproduction result, this was raised with the
requester before any code change; the direction taken was to apply the
defensive hardening the task itself names as good practice, since two
real (if currently latent, not currently triggered) fragilities were
found on inspection even though neither could be shown to actually cause
the reported symptom on this host/browser.

## ROOT CAUSE

**Not conclusively established as the cause of the reported symptom** —
extensive live reproduction did not trigger it. Two real, latent code
fragilities were found and fixed defensively:

1. Each row's Restart/Stop/Start buttons were wired via a per-row inline
   `onclick` attribute with the container name string-interpolated
   directly into a single-quoted JS argument
   (`onclick="dockerAction('<name>','restart')"`). `esc()` HTML-entity-
   encodes the name before interpolation, but that encoding lives
   **inside an HTML attribute value** — the browser decodes HTML entities
   back to raw characters before parsing the attribute as JavaScript. A
   container name containing a single quote (not something Docker's own
   naming rules currently allow, but not something this code defended
   against either) would have broken the inline JS and thrown a syntax
   error on click.
2. Those same buttons had no explicit `type` attribute, defaulting to
   `type="submit"` per the HTML spec. No `<form>` currently wraps the
   table (verified), so this had no live effect today, but it was one
   structural change away from silently becoming a real "click Stop and
   the page submits/reloads" bug.

## FILES CHANGED

- `templates/ops.html` — `renderDocker()`/`dockerAction()` wiring only.
- `tests/test_docker_advanced_action_ui.py` — new, real-browser
  regression test (Playwright).

## BUG REPRODUCED: NO (see REPRODUCTION above — extensive live testing, symptom never observed)
## DOCKER LIST DISAPPEARED BEFORE: NO (not observed in any tested variant)

## FIX

Per-row buttons now carry `type="button"` and `data-docker-name`/
`data-docker-action` attributes instead of an inline `onclick` with a
string-interpolated argument. A single delegated `click` listener is
attached once to the stable `#dockerRows` `<tbody>` element (not
re-attached per render), reads the clicked button via
`e.target.closest('button[data-docker-action]')`, and calls the exact
same `dockerAction(name, action)` function as before — same confirm
dialog, same POST endpoint, same alert/refresh behavior; zero change to
Docker lifecycle semantics or backend business logic. The delegated
listener survives every `loadDocker()`/filter re-render automatically,
since it's bound to the `<tbody>` element itself, not to the
regenerated `<tr>` content.

### SELECTOR/DOM ISSUE
None found live. Hardened anyway: dynamic per-row identity now flows
through `data-*` attributes read via `closest()`, per the task's own
suggested pattern, instead of a fragile interpolated-string selector.

### BUTTON FORM ISSUE
No `<form>` wraps the table (confirmed — the only `<form>` on the page
is the unrelated header logout button). Buttons now carry explicit
`type="button"` regardless, closing the latent risk.

### CSS ISSUE
None found. Read `static/css/agent.css` in full — no rule hides
`#dockerRows`/`.tablewrap`/`table` on any state change, no
`content-visibility`/animation/transition touches table rows.

### JS ERROR
None observed in any live run (0 console errors, 0 page errors across
~30 individual toggle interactions in reproduction testing).

## DOCKER ROWS VISIBLE AFTER TOGGLE: YES (all rows, every test)
## ADVANCED ACTION VISIBLE: YES (Restart/Stop/Start render correctly under the toggled row only)
## OTHER ROWS PRESERVED: YES (every other row's visibility/content confirmed unchanged on every toggle)

## PLAYWRIGHT

New test: `tests/test_docker_advanced_action_ui.py`
(`test_docker_advanced_action_toggle_never_hides_the_list`). Spawns a
real second `agent.py` process (same convention as
`tests/test_p5_fleet_routes.py`), drives it with a real headless
Chromium session against this host's real `docker ps -a` output:
loads the Docker page, asserts row count > 0, opens then closes the
first row's advanced toggle (asserting row count unchanged, list
visible, advanced area open/closed correctly, every other row still
visible), repeats for the second row, and asserts zero page navigations,
zero page errors, zero console errors throughout. Never clicks
Restart/Stop/Start (task section 10 — read-only toggle wiring only, no
destructive mutation risk). Guarded with `pytest.importorskip` so
environments without Playwright installed skip cleanly rather than
failing (Playwright is present in this dev `.venv` but intentionally not
added to `requirements.txt` — that file also builds the production
Docker image, which has no use for a browser-automation dependency).

## PAGE ERRORS: 0
## CONSOLE ERRORS: 0

## AGENT REBUILT: YES
`docker compose -f docker/compose.linux.yml -f docker/compose.dev.override.yml up -d --build`
(the exact compose invocation the local Deploy Agent was already running
under — same image name `mesflow-deploy-agent:2.23.16`, same
name/volumes/network, recreated in place). Only this Agent's own
container was touched — `mesflow-postgres`, `mesflow-app`,
`mesflow-nginx`, `mesflow-qa-center` were not restarted.

## AGENT HEALTH: PASS
`docker ps` reports `healthy`; `GET /live` responds
`{"ok":true,"agent_version":"2.23.16-docker-runtime",...}`; `GET /agent/health`
responds normally. The real-browser test in the PLAYWRIGHT section above
was re-run against this rebuilt container directly (all 19 real rows on
the freshly rebuilt host, plus a full before/after DOM-integrity check)
with the same result: list intact, 0 console errors, 0 page errors.

## AUTOMATED TESTS
Focused: `tests/test_docker_advanced_action_ui.py` — 1 passed (real
Playwright browser test). Full suite (`pytest tests/ -q`): **361 passed,
15 skipped, 8 subtests passed, 0 failed** — no regressions from this
change.

## DOCKER BUSINESS LOGIC CHANGED: NO
No change to `/api/ops/docker`, `/api/ops/docker-action`, container
start/stop/restart semantics, permissions, or host-ops policy.
`dockerAction()`'s own body (confirm dialog, POST body, response
handling) is byte-identical to before.

## PRODUCTION TOUCHED: NO
All rebuild/redeploy/verification was against this host's own local
`mesflow-deploy-agent` container only (`docker/compose.linux.yml` +
`docker/compose.dev.override.yml`). `mesflow-postgres`, `mesflow-app`,
`mesflow-nginx`, `mesflow-qa-center` were not restarted, and no
Restart/Stop/Start button was ever actually clicked against any real
container during testing — only the read-only advanced-action toggle.
