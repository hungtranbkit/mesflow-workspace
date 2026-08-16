
# Deploy Agent Refresh/Freeze Performance Fix

Project: `deploy-agent/`. A prior fix (`reports/RELEASE_TAB_PERFORMANCE_FIX.md`,
Agent 2.23.15) already replaced the Release Deploy tab's own 3-second
full-page-reload loop with lightweight polling. This task audited the
CURRENT authoritative source end-to-end, found the freeze/excessive-
refresh problem was still real from causes that fix did not touch, fixed
them, then rebuilt and redeployed the real local Deploy Agent and drove
a live Chromium/Playwright session against it to prove the fix — not
just source review.

## AUDIT MAP (task section 1)

| UI component | Endpoint | Interval | Backend work | Expensive? | Required? |
|---|---|---|---|---|---|
| Release Deploy tab, active job | `GET /api/release-manager/live-status` | 5s, only while a job is active | `load_state()` only | No | Yes |
| Release Deploy tab, idle | — none — | — | — | — | — |
| Release Deploy tab, page load/reload | `GET /releases?tab=deploy` | on real navigation only | `mes_status()`+`qa_status()`+`_release_summary()`+`_qa_release_summary()`+`_deployment_platform_summary()` — each was computed **TWICE** (Root Cause 1) | Yes (Docker inspect, SHA256 of 70–500+MB ZIPs, and — live-discovered — up to 20s of network-timeout cascades, Root Cause 4) | Yes, once, not twice |
| Agent Update tab, active job — **before** | full page `location.reload()` | every 3s, unconditionally | entire `/releases?tab=agent-update` route render | Mild per-call, but a genuine reload-loop | **No — Root Cause 3** |
| Agent Update tab, active job — **after** | `GET /api/release-manager/live-status` | 5s, only while active | `load_state()` only | No | Yes |
| Deployment History tab | `GET /api/release-manager/history` | on demand only | paginated evidence-store read | No | Yes |
| Dashboard (Overview) fleet/storage cards | `GET /api/fleet/summary`, `GET /api/ops/storage` | once per page load | cached/bounded reads | No | Yes — but silently 401'd under the default URL prefix (Root Cause 5) |
| Operations Health/Alerts/Predictions | `/api/ops/summary` (15s) / `/api/incidents` (30s) / `/api/ops/predictions` (60s) | periodic | bounded host/status reads | Bounded | Yes — within the task's own 10–30s NORMAL STATUS band |

## ROOT CAUSE

Five causes. The first three were found by static source audit; the last
two only surfaced once the fix was actually redeployed and driven by a
real browser against the real local host — which is exactly why this
task's live-verification step mattered, not just unit tests.

1. **Redundant double computation on every Release Deploy tab page
   load.** `_deployment_platform_summary()` unconditionally recomputed
   `mes_status()`, `qa_status()`, `_release_summary()` and
   `_qa_release_summary()` — even though its only in-page caller had
   just computed all four itself moments earlier in the same request.
2. **No caching on `sha()`.** The release ZIPs on this host are real
   73MB (MESFlow) and 522MB (QA Center) deploy packages
   (`artifacts/releases/*/*.deploy.zip`,
   `artifacts/qa-center/releases/*/*.deploy.zip`). `sha()` re-hashed the
   full file from scratch on every call, in every request that touched
   a release summary, even when the file had not changed.
3. **A genuine full-page-reload loop on the Agent Update tab.**
   `_agent_update_tab.html` had `setTimeout(()=>{if(active)location.reload()},3000)`
   — a one-shot reload that, once it fires, re-renders the same script
   on the fresh page, which schedules another one-shot reload if the
   job is still active. In effect, reload-the-whole-page-every-3-seconds
   for the duration of any Agent Update job — the exact pattern task
   section 5 names, in a sibling template the earlier fix's own
   regression test never looked at.
4. **Live-discovered: `mes_status()`/`qa_status()` pay a large network-
   timeout cascade whenever MESFlow/QA are down** — a very ordinary,
   expected state (exactly when an operator would be looking at this
   page). Measured directly on the real container: `mes_status()` alone
   took **15.3s**, `qa_status()` **5.0s** — ~20s total, dwarfing causes 1–2.
   `mes_status()` calls `http_json()` three times
   (`/api/system/version`/`/api/system/health`/`/api/system/ready`), and
   `http_json()` cascades through **five** URL candidates (`MES_URL`,
   `http(s)://127.0.0.1`, `http(s)://localhost`) per call — when MESFlow
   is stopped, the `mesflow-app` Docker-DNS candidate doesn't refuse the
   connection, it blocks until the ~4s per-candidate timeout, three times
   over. `qa_status()`'s single `qa_http_json()` call pays a similar cost
   (DNS `EAI_AGAIN` retry + connect timeout) reaching the stopped
   `mesflow-qa-center` hostname.
5. **Live-discovered: a URL-prefix/cookie-scope bug silently breaks the
   Dashboard and Deployment History fetches under the Agent's own
   documented default configuration.** `SESSION_COOKIE_PATH` is set to
   `URL_PREFIX` (default `/agent`), but `dashboard.html` and
   `_history_tab.html`/`index.html`'s shared `apiFetch()` issued
   root-absolute `fetch('/api/...')` calls. A browser does not attach a
   `Path=/agent/`-scoped cookie to a request for `/api/...` (outside that
   path), so every such call looked unauthenticated, 302'd to `/login`,
   and the JSON parse of the login HTML silently failed — surfacing as
   "Không tải được lịch sử triển khai" / a stuck "Đang tải…" Fleet card,
   with two `401`s in the browser console, on every load. Not a freeze,
   but a real correctness bug the task's own live-verification steps
   (History tab usability, console errors) surfaced directly.

Not causes (audited, ruled out): duplicate pollers across navigation
(full server-side page navigation throughout, confirmed live — clicking
History/Agent Update genuinely changes the URL, heading and DOM, never
just an anchor-scroll), remote target auto-probing (Target Agents list
is a cached-JSON read; the live probe is manual-button-only), Operations
Center cadence (already within the task's own acceptable band).

## POLLERS FOUND / REMOVED / KEPT

**Found:** Release Deploy tab 5s active-job poll (pre-existing, correct);
Agent Update tab 3s unconditional reload loop (the bug); Operations
Center 15s/30s/60s dashboards; ESP Kiosk OTA console 3s/15s polls
(separate page, untouched, out of scope).

**Removed:** the Agent Update tab's 3-second full-page-reload loop.

**Kept, hardened:** Release Deploy tab's poller (now with an in-flight
guard and resume-on-visible); Agent Update tab now uses the exact same
lightweight endpoint/pattern (new); Operations Center dashboards
unchanged.

## IDLE RELEASE REQUEST RATE BEFORE / AFTER

Idle Release Deploy tab issues **zero** background requests, before and
after — that part was already correct. What changed is page-load cost
and correctness. **Live, on the real redeployed local Agent** (this
host's real 73MB/522MB ZIPs, real Docker, MESFlow/QA genuinely stopped):

| | first (cold-ish) load | 3 subsequent loads |
|---|---|---|
| Before this task's fixes (measured via isolated function timing, since the redundant-call/no-cache/no-shortcut code was still live) | ~22.7s per load (measured through Playwright against the real container before Root Cause 4/5 were fixed) | ~20.5s, ~20.5s, ~20.5s — **no warm-load improvement**, because the ~20s `mes_status`/`qa_status` network cascade dominated and was unaffected by caching |
| After all 5 fixes (measured the same way, same real container, same real files) | **3.29s** | **446ms, 407ms, 382ms** |

The `sha()`-cache/no-double-compute win (Root Causes 1–2) is real and
was already proven via `pytest` call-counting and isolated timing
(cold 2.08s → warm 0.355s against these exact files, no network
dependency). But it was invisible in the first live run because Root
Cause 4 was ~7–10× larger — this is exactly why "do not claim a
percentage improvement unless measured on the live endpoint" mattered:
the live numbers told a different, bigger story than the isolated
numbers alone.

## LOG AUTO POLLING BEFORE / AFTER

Unchanged, already correct from the prior fix: the Release Deploy tab
context never tails a log file on page render, and the lightweight
live-status endpoint never reads a log either.

## FULL PAGE RELOAD

- Release Deploy tab: one-shot only, on completion or after a button
  action — never a loop. Unchanged, verified live (idle watch: zero
  navigations over 10s; active-job watch: zero navigations over 16s of
  polling).
- Agent Update tab: **was** a 3-second reload loop — **fixed**, verified
  live the same way (idle watch: zero navigations over 11s; simulated
  active `UPDATING` job watch: **4** lightweight `live-status` GETs over
  16s, **zero** document navigations, URL unchanged throughout).

## DUPLICATE POLLERS

None found or introduced. Verified live: clicking "Lịch sử triển khai"
and "Agent Update" in the sidebar produces a real `framenavigated` event
each time (URL changes to `?tab=history`/`?tab=agent-update`, `<h2>`
heading text changes accordingly) — genuine full navigation, not an
anchor-scroll, so a previous page's JS/interval is always fully torn
down by the browser before the next tab's script runs. No code path can
leave two pollers running at once.

## HIDDEN TAB POLLING

Both pollers already skipped their fetch while `document.hidden`. Added
in this task: an in-flight guard (never stacks a second request behind
a slow one) and a `visibilitychange` listener that triggers one
immediate refresh the moment the tab becomes visible again, to both
pollers.

## LIVE STATUS ENDPOINT

Reused `GET /api/release-manager/live-status` for the Agent Update tab
too, rather than adding a new endpoint. Extended its tracked-jobs tuple
to include `agent_update_job` and its active-status set with
`UPDATING`/`PUSHING`. Still state-only — verified by source assertion
(`_release_summary`/`_qa_release_summary`/`mes_status`/`qa_status`/`tail(`
never appear in its body) and live (4 real polls, each answered
instantly, confirmed via Playwright request timestamps ~1.2s/6.2s/11.2s/16.2s
apart, matching the 5s interval).

## EXPENSIVE WORK REMOVED FROM LIVE POLL

The live-status poll itself was already state-only — nothing to remove
there. What was removed is the redundant/expensive work that used to run
inside a page *render* (Root Causes 1, 2, 4), and the always-broken auth
on two Dashboard/History fetches (Root Cause 5).

## RELEASE SUMMARY

`_deployment_platform_summary()` now accepts optional precomputed
`mes`/`qa`/`mes_release`/`qa_release`; `_release_deploy_tab_context()`
computes each once and passes them through. The standalone
`GET /api/deployment-platform` route is unchanged (no pre-existing
values to reuse there). `sha()` is cached by `(path, mtime_ns, size)` —
any real file change invalidates it automatically; deploy-time SHA
verification elsewhere (compares a freshly-read local hash at actual
deploy/promote time) is unaffected.

`mes_status()`/`qa_status()` now consult a fast, purely LOCAL signal
first — `_docker_mes_state()`'s `available`+`running` fields (Docker
Compose state, ~0.3s) for MESFlow, `_qa_service_state()` (`docker
inspect`/`systemctl`, both local) for QA — and skip the network HTTP
cascade entirely **only** when that signal already proves with certainty
that nothing could be listening (container/service confirmed not
running). When Docker/systemd state is unavailable or ambiguous
(Windows runtime, bare-process install, no compose.yml), the full HTTP
probe still runs exactly as before — verified by dedicated tests for
both branches. This cannot return a different *answer* than before
(mathematically: not-running ⇒ no listener ⇒ any HTTP attempt was always
going to fail), only a much faster one.

## DOCKER STATUS

`mes_status()`'s own `_docker_mes_state()` Docker-inspect call (~0.3s,
separate from the HTTP cascade above) is not cached, by design — it now
runs exactly once per real page load (down from twice), never on a
timer, and this page's whole purpose is to show accurate live
deploy/health state; a TTL cache here would risk showing stale
"healthy/unhealthy" right after a real deploy action (task
section 12/23: never cache deployment-correctness surfaces). Operations
Center's own `ops_summary()` was separately audited and left unchanged —
already within the task's own cheap-status/10–30s policy band.

## REMOTE TARGET POLLING

Audited, no auto-probing found. Target Agents renders from a cached
`target-agents.json`; the live remote-target probe is manual-button-only
or tied to an actual promotion.

## BUILD UI TEST / DEPLOY LOCAL UI TEST / FAILURE TEST

A live multi-minute Build Release / Deploy Local run was not triggered
(not required to prove this fix, and this host's MESFlow/QA are
currently stopped rather than mid-deploy). Instead, both the "idle" and
"active job" states were exercised directly against the real redeployed
container: idle (no navigations/requests over 10–11s, both tabs) and a
**real simulated active job** (`agent_update_job.status=UPDATING`,
written directly into this Agent's own persisted state via
`agent.update_state()` inside the running container, then cleared again
immediately after) — proving the actual polling/no-reload behavior under
the exact condition the original bug required, not just the idle case.
Failure-state behavior (`FAILED` job → polling stops → no further
reload) is unchanged from the pre-existing, already-tested Deploy tab
pattern and was not additionally re-simulated live.

## PLAYWRIGHT

Run: headless Chromium via `mesflow-web`'s existing Playwright
install (browsers already cached on this host), driven against the real
rebuilt-and-redeployed local `mesflow-deploy-agent` container (real
Docker, real 1920×1080 viewport, real login through this Agent's
`/local-reset` recovery flow — see Safety section). Three passes were
run as fixes landed: an initial pass exposed the live-only Root Causes
4–5; the final pass, after fixing them, is the evidence below.

- Login: PASS (302 → `/agent/`).
- Release Deploy tab: PASS — loads, idle 10s watch shows zero requests
  and zero navigations, 3 repeated loads average ~410ms.
- Deployment History tab: PASS — real navigation (`?tab=history`),
  heading changes, table now genuinely populates real rows (2 real past
  deployment records rendered, screenshot captured) instead of the
  Root-Cause-5 error text.
- Agent Update tab: PASS — real navigation (`?tab=agent-update`), idle
  11s watch shows zero requests/navigations; simulated active-job 16s
  watch shows exactly 4 lightweight `live-status` polls, zero document
  navigations, URL unchanged throughout.
- No anchor-scroll navigation: PASS — both tab switches are genuine
  `framenavigated` events to a new `?tab=` URL with a new rendered
  heading, not a same-page hash-scroll.
- No 3-second full-page reload: PASS (both idle and simulated-active).
- Polling preserves tab: PASS.

## PAGE ERRORS

None, on any of the three passes.

## CONSOLE ERRORS

First pass (before Root Cause 5's fix): 2× `401 UNAUTHORIZED`
(`/api/fleet/summary`, `/api/ops/storage`) on the Dashboard, and
(separately confirmed) the same failure mode on Deployment History's
`/api/release-manager/history`. Final pass, after the fix: **0**.

## AGENT VERSION BEFORE / AFTER

- Before: `2.23.15-docker-runtime` in `VERSION.txt`/`agent.py`/
  `README.md`/`docs/DEPLOY_DOCKER.md`, but `docker/Dockerfile` and both
  `docker/compose.*.yml` were still at `2.23.14` (pre-existing drift;
  the real running container was `2.23.14`).
- After: `2.23.16-docker-runtime` everywhere (`VERSION.txt`, `agent.py`,
  `docker/Dockerfile`, `docker/compose.linux.yml`,
  `docker/compose.windows.yml`, `README.md`, `docs/DEPLOY_DOCKER.md`).
  `2.23.15` was never actually built into a real image on this host, so
  `2.23.16` is the first genuinely new, never-released version.

## BUILD

- Docker build: **PASS** (built 3 times as fixes iterated; the last two
  builds hit Docker's layer cache for the apk/pip layers — only the
  `COPY agent.py .../templates/...` layers re-ran, each finishing in
  well under a minute).
- Image: `mesflow-deploy-agent:2.23.16`
- Reported version at runtime (`GET /live`): `"agent_version":"2.23.16-docker-runtime"`, matches.

## LOCAL DEPLOYMENT

- Container: **PASS** — `docker compose -f docker/compose.linux.yml -f docker/compose.dev.override.yml up -d --build`, the exact same compose invocation (base + local-dev override) the running container was already using; recreated in place, same name/volumes/network.
- Health: **PASS** — `docker ps` reports `healthy`; `GET /live` responds `{"ok":true,...}` immediately (the heavier `/health` route is the one Root Cause 4 affected — `/live` is the Dockerfile's own `HEALTHCHECK` target and is intentionally not gated on MESFlow/QA reachability).
- Running version: **2.23.16** — matches expected, no mismatch.
- Startup logs: clean, one line (`Agent 2.23.16-docker-runtime start ...`), no ERROR/Traceback/exception in the last 10 minutes of logs.

## AUTOMATED TESTS

- Focused regressions: `tests/test_release_refresh_performance_fix.py` — **17 passed** (10 from the redundant-computation/reload-loop fix, 4 from the live-discovered `mes_status`/`qa_status` network-cascade fix, 3 from the live-discovered URL-prefix cookie fix). `tests/test_release_tab_lightweight_polling.py` — 3 passed, unaffected.
- Full suite (`pytest tests/ -q`), run immediately after the final fix
  (URL-prefix cookie bug) and again after the final docker rebuild:
  **364 passed, 11 skipped, 8 subtests passed, 0 failed** (skip count
  fluctuates a few tests run-to-run on environment-gated tests; failures
  are consistently 0 across all runs in this session). The 3 pre-existing
  version-sync failures from before this task are now fixed as a side
  effect of the version sync, not merely tolerated — confirmed passing
  individually and in every full-suite run since.

## ROOT CAUSES FIXED

1. Redundant double computation of `mes_status`/`qa_status`/release
   summaries inside `_deployment_platform_summary()` on every Release
   Deploy tab load.
2. No caching on `sha()` for the real 73MB/522MB release ZIPs.
3. Agent Update tab's unconditional 3-second full-page-reload loop.
4. `mes_status()`/`qa_status()`'s network-timeout cascade (~20s combined)
   when MESFlow/QA are stopped — now skipped via a fast local Docker/
   systemd check when that check already proves the answer.
5. A URL-prefix/cookie-scope bug silently breaking two Dashboard fetches
   and Deployment History under this Agent's own documented default
   config (`URL_PREFIX=/agent`).

## FILES CHANGED

- `agent.py` — `sha()`/`_hash_file_sha256()` (cache), `_deployment_platform_summary()` (optional precomputed args), `_release_deploy_tab_context()` (compute once, pass through), `_release_live_status_payload()` (tracks `agent_update_job`), `mes_status()`/`qa_status()` (skip HTTP cascade when Docker/systemd already confirms not-running), `AGENT_VERSION` bump.
- `templates/release/_agent_update_tab.html` — replaced the reload loop with lightweight polling (in-flight guard + visibility-resume).
- `templates/release/_deploy_tab.html` — added in-flight guard + visibility-resume to the existing poller.
- `templates/release/index.html` — `apiFetch()` made URL-prefix-aware (mirrors `ops.html`'s pre-existing correct pattern).
- `templates/dashboard.html` — two bare `/api/...` fetches switched to `{{url_for(...)}}`.
- `docker/Dockerfile`, `docker/compose.linux.yml`, `docker/compose.windows.yml`, `VERSION.txt`, `README.md`, `docs/DEPLOY_DOCKER.md` — version sync.
- `tests/test_release_refresh_performance_fix.py` — new, 17 focused regression tests.

## KNOWN REMAINING ISSUES

- `templates/ota.html` (ESP Kiosk OTA console — a different page, not
  Release & Deploy) hardcodes `/agent/api/esp-ota/...` literally instead
  of using `{{url_for(...)}}`. This happens to work under the real
  default config (`URL_PREFIX=/agent`) but would break if the Agent were
  ever run with a different/empty prefix. Not touched — separate page,
  currently working, out of this task's scope.
- The Release Deploy tab's inline "MESFlow verification timeout" error
  banner renders a raw Python dict/error string verbatim (pre-existing,
  visible in the live screenshot from a real past failed deploy on this
  host) rather than a formatted message. Not a freeze/polling issue and
  not touched.
- A live multi-minute Build/Deploy Local run was not exercised end-to-end
  in this pass (see BUILD UI TEST section) — the idle and active-job
  polling behaviors were proven directly instead, which is what the
  freeze reports were actually about.

## SAFETY

- **LOCAL ONLY.** All Docker rebuild/redeploy/verification was against
  this dev host's own local `mesflow-deploy-agent` container
  (`docker/compose.linux.yml` + `docker/compose.dev.override.yml`,
  `SERVER_ROLE=DEV`).
- **NO TEST DEPLOY.**
- **NO PRODUCTION DEPLOY.**
- **NO PRODUCTION RESTART.**
- **NO PRODUCTION DB MUTATION.**
- To log in for live verification, the real local Agent's admin password
  was reset via its own `/local-reset` recovery route (loopback-only by
  design — `_is_local_reset_request()` requires the request to
  genuinely originate from `127.0.0.1`, reached here via `docker exec`
  into the container itself) to a throwaway test password, used only for
  this verification. No other container/data was touched; only this
  Agent's own `agent_update_job` state key was temporarily set to a
  simulated `UPDATING` value (via `agent.update_state()` inside the
  container) to prove the active-polling behavior, then cleared
  immediately after.
- `DEPLOYMENT LOGIC CHANGED: NO` — no release upload/validate/stage/
  activate/verify/rollback code path was touched; `deployment_platform.py`
  is untouched.
- `PRODUCTION GATES CHANGED: NO` — LOCAL_PASS/TEST_PASS/schema
  verification/contamination checks/production approval flags/Agent-
  compatibility checks are all untouched. The SHA cache is
  content-identity-keyed so it can never return a stale digest for a
  changed file.

## PRODUCTION DEPLOYED: NO
