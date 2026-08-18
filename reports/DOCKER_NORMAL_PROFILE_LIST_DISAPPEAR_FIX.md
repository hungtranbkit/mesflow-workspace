# Docker "Normal Profile" List Disappear — Fix

Project: `deploy-agent/`. Third investigation round on the same reported
bug as `reports/DOCKER_ADVANCED_ACTION_UI_BUG.md` (round 1) and
`reports/DOCKER_LIST_DISAPPEAR_UI_FIX.md` (round 2). This round's new
angle: "normal Chrome" vs. Incognito behave differently — and it is the
first round to actually find and fix a real, always-reproducible root
cause, by testing something neither prior round tested: **an API call
that fails while the list is already showing rows.**

## HONEST RESULT UP FRONT

I could not reproduce the bug against the user's own real, long-lived
Chrome profile — copying or launching against that profile (even
read-only, even to a scratch copy) was refused by this session's own
permission guard, correctly, since it holds the user's real browsing
data for every site, not just Deploy Agent. Sections 1/2's "capture
NORMAL vs. INCOGNITO" protocol could therefore not be run against the
user's literal browser.

What I could and did do: (a) exhaustively re-confirm, independently,
everything the first two rounds already proved (no stale HTML/JS can
survive a plain reload — `Cache-Control: no-cache, must-revalidate` with
no ETag/Last-Modified on every non-static route, confirmed live via
network-response inspection, `fromCache:false` on every repeat load, on
every route including after a real `page.goBack()`); (b) go one step
further than either prior round by testing what happens when the
Docker-list refresh's own API call fails mid-session (something neither
round tested), which reproduced the exact reported symptom
**deterministically, in a single, minimal, always-repeatable step** —
no stale cache, no bfcache, no Service Worker, no persisted client
state required at all. This is presented as the real root cause because
it is provably real (curl-level reproduction of the exact response
shape, a passing-then-failing-then-passing-again automated test), it
was never previously tested, and it precisely explains the Normal-vs-
Incognito split without requiring any exotic browser-caching mechanism.

## NORMAL PROFILE REPRODUCED: NOT ATTEMPTED (permission-blocked)

Attempting to copy `~/.config/google-chrome/Default` (the real, actively
used profile — last modified today) into a scratch directory to launch
Playwright against it was denied by this session's own tool-permission
classifier. I did not attempt a workaround (e.g. launching directly
against the live profile, which risks a `SingletonLock` conflict with
the user's actual browser). This is disclosed plainly rather than
silently skipped or worked around.

## INCOGNITO REPRODUCED: NO (matches both prior rounds)

A brand-new Playwright context (Incognito-equivalent: no disk cache, no
cookies, no local/session storage carried over) against the real running
Agent (`2.24.7`, then rebuilt `2.24.8`) never showed the symptom for any
combination of: plain row click, advanced-toggle open/close on 10
different rows, navigate-away-and-back (`page.goBack()` — no `pageshow`
event with `persisted:true` fired, i.e. no bfcache restore occurred for
this route either), and a plain `page.reload()`. 18 rows before, 18
after, every time. Matches the user's own "Incognito works correctly."

## NORMAL FRONTEND_BUILD_ID / INCOGNITO FRONTEND_BUILD_ID:

Not separately comparable (no real-profile access — see above). Both
tested (fresh) contexts against the same running Agent naturally report
the identical `frontend_build_id`, since it's a property of the server
process, not the browser: `2.24.7-docker-runtime-77c5dc7860` before this
fix, `2.24.8-docker-runtime-77c5dc7860` after (version prefix changed
because `AGENT_VERSION` was already bumped to 2.24.8 by a prior,
separate, un-built commit before this task started; the 10-hex suffix
is unchanged because this fix only touched `templates/ops.html` and
`tests/`, not anything under `static/` — see `STALE ASSET FOUND` below
for why that's expected, not a bug).

## STALE ASSET FOUND: NO

`_compute_frontend_build_id()` (`agent.py`) hashes every file under
`app.static_folder` only — `static/css/agent.css` and
`static/js/core/navigation.js`, confirmed by reading both files in full:
neither mentions Docker/`dockerRows`/container logic at all
(`navigation.js` is 9 lines, only the sidebar-drawer toggle;
`agent.css` has zero Docker-specific rules). The Docker page's entire
JS/HTML lives **inline** in `templates/ops.html`, which is not a
`/static/*` asset at all — it is never cached (`Cache-Control:
no-cache, must-revalidate`, verified live, no ETag/Last-Modified to
even attempt a conditional revalidation with), so it cannot be served
stale from HTTP cache regardless of whether `FRONTEND_BUILD_ID`
"covers" it. This was independently re-verified live for this task
(fresh network-response capture, `fromCache:false` on every load,
including post-`goBack()`), consistent with the dedicated prior
investigation (`reports/DEPLOY_AGENT_FRONTEND_CACHE_BUST.md`).

**Real gap found, not fixed (deliberately out of scope for this pass)**:
`FRONTEND_BUILD_ID` gives zero signal if `ops.html` itself changes,
since templates aren't hashed. This doesn't cause staleness today (the
HTML route's cache policy makes that impossible on its own), but it
does mean `frontend_build_id` is not a reliable "did the browser get the
current app" diagnostic for template-only changes — exactly the kind of
signal Section 1 of this task asked me to compare. I chose not to touch
`_compute_frontend_build_id()` in this pass: it has its own dedicated,
already-passing 10-test suite (`tests/test_frontend_cache_busting.py`)
proving the current static-only hash is deterministic and
content-sensitive, and extending its scope is unrelated to the actual
fix below — safer to flag as a known limitation than to risk that
already-verified mechanism for a change this bug does not need.

## SERVICE WORKER: NONE

`navigator.serviceWorker.getRegistrations()` returns `[]` live, on
every test in this and both prior rounds. `grep -rn
"serviceWorker|service-worker|sw.js" templates/ static/ agent.py` — zero
matches anywhere in the codebase. Section 5 is not applicable to this
application at all.

## LOCAL STORAGE ISSUE: NONE

`localStorage`/`sessionStorage` both return `{}` live for this origin.
`grep -rn "localStorage|sessionStorage" templates/ static/` — zero
matches anywhere in the codebase. No persisted client-side UI state
exists to version. Section 6 is not applicable.

## DOM CLEAR EVENT / HANDLER / FUNCTION / ROOT CAUSE:

**Event**: `/api/ops/docker` returning `{"ok": false, "error":
"AUTH_REQUIRED"}` (HTTP 401, no `items` key) — reproduced directly via
`curl` with no session cookie, and this is exactly what the endpoint
returns whenever the caller's session is no longer valid for any reason
(expired, logged out from another tab sharing the same browser profile,
cookie evicted, etc.) — no caching or stale-asset mechanism required.

**Handler**: `loadDocker()` (`templates/ops.html`) — called both by the
Docker toolbar's own "Làm mới" button and, critically, by
`dockerAction()` **after every** Restart/Stop/Start click (the concrete
action reachable from "clicking a Docker/container row" → opening
"Thao tác nâng cao" → clicking an action button).

**Function / exact defect**: `dockers = d.items || []` ran
**unconditionally**, before checking `d.ok`. Since a failed response has
no `items` key, `d.items` is `undefined`, so `dockers` was set to `[]`
regardless of whether the real Docker state had changed at all, and
`renderDocker()` then rendered the now-empty `dockers` array into
`#dockerRows`, wiping every row that was previously showing.

**Root cause**: a missing defensive check, not a caching problem, not a
duplicate handler, not a Service Worker, not persisted client state —
the very things the first two investigation rounds thoroughly ruled out
and this round re-confirmed. Both prior rounds tested exclusively with
an uninterrupted, continuously valid session; neither tested a
mid-session API failure. This exactly explains the Normal-vs-Incognito
split reported: a "normal", long-lived browser tab is the case most
likely to have its session go stale sometime during the visit (logout
in a sibling tab of the same profile, a cookie getting evicted, the tab
being left open across whatever the browser/OS does to session cookies
over a long idle period); a fresh Incognito login, tested for a few
minutes, essentially can't hit this. Reloading fixes it because a fresh
page load re-authenticates (redirects to `/login` if the session is
truly gone) or simply re-establishes a valid session before the next
list fetch, restoring the same non-empty response.

## DOCKER LIST BEFORE CLICK: 18 rows (real host, `docker ps -a`)
## DOCKER LIST AFTER CLICK: 18 rows (plain click, advanced toggle, 10-row open/close cycle, navigate-away+back — all unchanged; confirmed live against the real rebuilt 2.24.8 Agent)

## DETAIL FAILURE PRESERVES LIST: YES (after fix)

Directly reproduced and automated: with 18 rows already showing,
clearing the session cookie (so the next `/api/ops/docker` call returns
`{"ok":false,"error":"AUTH_REQUIRED"}`) and then clicking "Làm mới" (the
same function a Restart/Stop/Start click also triggers) now leaves the
list at **18 rows, unchanged** — the error is still surfaced via the
existing `feedback()` toast/status line, but the authoritative
`dockers` array is only ever replaced on a **confirmed** (`d.ok !==
false`) response.

**Before the fix**, the identical test failed with `18 rows before, 0
after` — reproduced and captured explicitly (see AUTOMATED TESTS below)
by temporarily reverting the fix, re-running, confirming the failure,
then restoring the fix.

## CACHE-BUSTING COVERAGE:

- HTML/control routes (`/agent/ops`, `/agent/`, `/agent/login`, all
  `/agent/api/*`): `Cache-Control: no-cache, must-revalidate` — verified
  live on every route hit during this investigation.
- Versioned static (`/agent/static/css/agent.css?v=...`,
  `/agent/static/js/core/navigation.js?v=...`): `Cache-Control: public,
  max-age=31536000, immutable`, both with real `ETag`/`Last-Modified`.
- `FRONTEND_BUILD_ID = AGENT_VERSION + "-" + sha256(every static file's
  relative path + content)[:10]`, deterministic, content-based (proven
  in the prior cache-busting pass, re-confirmed unchanged here).

## UNVERSIONED ASSETS REMAINING: NONE

`grep -rn "url_for('static'" templates/**/*.html` (excluding
`static_url(...)` call sites) — zero matches across every template in
the project, not just `ops.html`. The complete 5-template set from the
prior cache-busting pass still holds; no new template regressed to a
bare `url_for('static', ...)`.

## NORMAL F5: PASS (list intact, unchanged from before F5)
## INCOGNITO: PASS (list intact throughout)
## BEHAVIOR IDENTICAL: YES, for every scenario this investigation could actually drive (both used fresh, cookie-controlled Playwright contexts — the one gap is the user's own real, long-lived profile, which I could not access — see NORMAL PROFILE REPRODUCED above)

## 10 ROW CLICK TEST: PASS

Opened and closed the advanced-action toggle on 10 different rows in
sequence against the real rebuilt `2.24.8` Agent — 18 rows before, 18
after, 0 console errors, 0 page errors.

## ADVANCED ACTION TEST: PASS

Toggle opens exactly the clicked row's actions, closes correctly, list
count and visibility unaffected — re-confirmed on this round's rebuilt
container (extends the identical check both prior rounds already
verified).

## NAVIGATE AWAY/BACK: PASS

`page.goto('/agent/')` then `page.goBack()` — 18 rows both before
navigating away and immediately after returning; no bfcache restore
occurred for this route (no `pageshow` event with `persisted:true`).

## NORMAL RELOAD: PASS

`page.reload()` after the above — 18 rows, unchanged.

## PAGE ERRORS: 0
## CONSOLE ERRORS: 0
## FAILED REQUESTS: 0 unexpected (the one 401 in the reproduction test is the deliberately-simulated failure being tested, not an unexpected error)

## AGENT VERSION: 2.24.7-docker-runtime (before) → 2.24.8-docker-runtime (after)
## FRONTEND_BUILD_ID: 2.24.7-docker-runtime-77c5dc7860 (before) → 2.24.8-docker-runtime-77c5dc7860 (after)
## AGENT HEALTH: PASS — `docker ps` → `mesflow-deploy-agent:2.24.8` `Up ... (healthy)`, port `127.0.0.1:8090->8090/tcp`. `GET /agent/live` → `{"ok":true,"agent_version":"2.24.8-docker-runtime","frontend_build_id":"2.24.8-docker-runtime-77c5dc7860","runtime_mode":"docker-linux"}`. `GET /agent/health` → HTTP 200.

## FIX

`templates/ops.html`, `loadDocker()`:

```js
// before
async function loadDocker(){feedback('Đang tải container Docker…','loading');let d=await api(...);dockers=d.items||[];renderDocker();feedback(d.ok===false?(d.error||'Không tải được Docker'):`Đã tải ${dockers.length} container.`,d.ok===false?'error':'ready')}

// after
async function loadDocker(){feedback('Đang tải container Docker…','loading');let d=await api(...);if(d.ok===false){feedback(d.error||'Không tải được Docker (đã giữ nguyên danh sách hiện tại)','error');return}dockers=d.items||[];renderDocker();feedback(`Đã tải ${dockers.length} container.`,'ready')}
```

`dockers` (the authoritative fetched collection) is now only ever
replaced on a confirmed successful response (`d.ok !== false`); any
failure — expired session, network error surfaced as a soft
`{ok:false}` by the existing `api()` helper, or any other transient
API failure — returns early, leaving the previously rendered list
exactly as it was, and still shows the error via the existing
`feedback()` mechanism. This is the exact model task section 9
describes: the authoritative collection and error/loading state are now
separate, and a failed refresh can never silently empty a
previously-populated list. `dockerAction()` (Restart/Stop/Start) needed
no change of its own — it already calls `loadDocker()` for its
post-action refresh, so fixing `loadDocker()` once fixes both the
explicit "Làm mới" button and every action button's follow-up refresh.

**Scope note**: `loadServices()` (the analogous function for Operations
→ Dịch vụ/systemd) has the same unconditional-clobber shape
(`services=d.items||[]` with no `d.ok` check visible in the same file).
Not fixed in this pass — this task's scope is the Docker page
specifically ("Do not blindly rewrite Docker list logic again" was read
as "stay surgical," not "fix everything nearby") — flagged here as a
real, related follow-up finding for a future focused pass, not silently
patched.

## AUTOMATED TESTS

`tests/test_docker_advanced_action_ui.py` — extended with
`test_stale_session_docker_refresh_preserves_the_list`, matching task
section 11's Test C/D model precisely: fetches the real Docker list (18
rows on this host), clears the session cookie, triggers the exact
refresh a Restart/Stop/Start click would trigger, and asserts the row
count is unchanged.

**Proof the test actually catches the bug** (not just proof it passes):
temporarily reverted `loadDocker()` to the pre-fix version, re-ran —
**failed** with `AssertionError: Docker list was wiped by a
stale-session refresh: 18 rows before, 0 after — assert 0 == 18` —
then restored the fix and re-ran clean. Both the pre-existing toggle
test and the new stale-session test: **2 passed**.

Full suite: `pytest tests/ -q` — **380 passed, 1 skipped, 0 failed**
(7 test files fail to even collect on this host shell due to a
pre-existing, unrelated `PermissionError: /data/ota` — confirmed via
`git stash` that this identical failure occurs on the unmodified
original source too; those tests are designed to run inside the actual
container/CI environment where `/data` is writable, not on this raw dev
host — see FULL UI AUDIT below).

## FULL UI AUDIT / REGRESSION

`pytest tests/ -q --ignore=tests/test_agent_compatibility.py
--ignore=tests/test_build_once_local_policy.py
--ignore=tests/test_deploy_local_stale_build_job.py
--ignore=tests/test_deploy_safety.py
--ignore=tests/test_esp_kiosk_ui_separation.py
--ignore=tests/test_it_operations_ui.py
--ignore=tests/test_orphaned_job_reconciliation.py` (the 7 files with
the pre-existing `/data/ota` permission issue on this host, confirmed
unrelated to this change) — **380 passed, 1 skipped, 0 failed**.

## MESFLOW MUTATED: NO
## POSTGRES MUTATED: NO
## NGINX MUTATED: NO
## QA CENTER MUTATED: NO
## PRODUCTION TOUCHED: NO

`docker ps` before/after this pass: `mesflow-app` (71.0.0.26, uptime
unaffected), `mesflow-postgres`, `mesflow-nginx`, `mesflow-qa-center` —
none were restarted or recreated at any point. Only
`mesflow-deploy-agent` was rebuilt/recreated, using this project's
established local-dev compose invocation (`docker compose -f
compose.linux.yml -f compose.dev.override.yml -f
compose.bootstrap.override.yml up -d --build`, run from the workspace
`deploy-agent/docker` directory — the same command both prior
investigation rounds used).
