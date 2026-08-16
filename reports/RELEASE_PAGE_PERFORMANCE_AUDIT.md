# Release Page Performance Audit

Project: `deploy-agent/`. Complaint: opening Release & Deploy freezes the
UI for a noticeable period, repeatedly.

## 1. REPRODUCE WITH REAL RUNTIME

Real Chromium (Playwright) against the live local Agent at
`http://127.0.0.1:8090`, real login, real network capture of the first
15s after `GET /agent/releases?tab=deploy`.

| METHOD | URL | START | DURATION | STATUS | SIZE |
|---|---|---|---|---|---|
| GET | `/agent/releases?tab=deploy` | 3.5ms | **15338.8ms** | 200 | 30461 B |
| GET | `/agent/static/css/agent.css?v=...` | 15349.7ms | 0.3ms | 200 | 10767 B |
| GET | `/agent/static/js/core/navigation.js?v=...` | 15350.4ms | 0.1ms | 200 | 446 B |

- **DOMContentLoaded:** 15352.8ms
- **load:** 15353.5ms
- **time until usable** (primary action button present): 15382.2ms
- **page errors:** 0
- **console errors:** 0

The entire freeze is one request: the HTML response itself took 15.3s.
Everything after it (CSS/JS) is effectively instant once the HTML finally
arrives.

## 2. TRACE SLOW REQUEST INTO BACKEND

Instrumented profiling directly against the live container's running
process (`docker exec ... python3 -c "..."`, timing each function the
route actually calls):

```
GET /releases?tab=deploy
  → release_manager_page()
    → _release_deploy_tab_context()
      → mes_status()                    15.233s  <-- entire bottleneck
      → qa_status()                      0.011s
      → _release_summary()               0.190s
      → _qa_release_summary()            0.020s (warm) / 1.164s (cold, one-time SHA hash)
      → _deployment_platform_summary()   0.001s (reuses the above -- no recompute)
```

`mes_status()` → `http_json()` (called 3x: `/api/system/version`,
`/api/system/health`, `/api/system/ready`) → `_mes_url_candidates()`
(`[MES_URL, http://127.0.0.1, https://127.0.0.1, http://localhost,
https://localhost]`) → `_http_json_base()` → `urllib.request.urlopen()`.

**Expensive operation, isolated:** `socket.getaddrinfo('mesflow-app',
8080)` measured **5.0096s** to fail with `[Errno -3] Try again`
(glibc `EAI_AGAIN`). This is *not* bounded by `urlopen`'s `timeout=`
parameter -- DNS resolution happens before the socket-level timeout
logic starts, a known CPython/glibc limitation. `mes_status()` hits this
once per each of its 3 internal `http_json()` calls: **3 × ~5.0s ≈
15.2s**, matching the measured 15.233s almost exactly.

**Root network cause:** `mesflow-deploy-agent` is on Docker network
`mesflow-edge` (172.18.0.0/16); `mesflow-app` is on `mesflow_network`
(172.19.0.0/16) -- two separate networks on this host, so `mesflow-app`'s
hostname genuinely does not resolve from inside this Agent's container,
regardless of whether MESFlow itself is healthy (it is: `mesflow-app` was
`Up ... (healthy)` the whole time). A `curl` from the same container hit
the identical DNS failure, but *instantly* (0.01s) -- `curl`'s resolver
path fails fast; Python's `socket.getaddrinfo` (glibc, `/etc/resolv.conf`
`options timeout`/`attempts` defaults) does not.

## 3. PAGE-LOAD REQUEST FANOUT

| Operation | Classification | Notes |
|---|---|---|
| `_release_summary()` (MESFlow version/build/promotion state) | ESSENTIAL | small, local files only |
| `_qa_release_summary()` | ESSENTIAL | small, local files only |
| `mes_status()` / `qa_status()` (online/healthy) | ESSENTIAL | must be network-bound-safe (this task's fix) |
| `_deployment_platform_summary()` | ESSENTIAL | reuses the 4 above, no new work |
| Deployment history | ON-DEMAND | separate tab, client-fetched (`/api/release-manager/history`), confirmed absent from this page's requests |
| Build/deploy logs | ON-DEMAND | confirmed no `tail()` call anywhere in the Release page's context builders (only inside job workers, persisted once at completion) |
| Job progress polling | JOB-ONLY | `/api/release-manager/live-status`, gated -- see section 4 |
| ESP Firmware / ESP Tutorial / OTA | UNRELATED | already relocated to `/kiosk/*` in the earlier ESP_KIOSK_UI_SEPARATION task; reconfirmed live: **zero** `/api/esp-*` requests during this page's load or its 30s idle window |
| Operations logs / server diagnostics | UNRELATED | not called by any Release page code path |

No unrelated work was found running on Release page load.

## 4. POLLING AUDIT

| Poller | Endpoint | Interval | Starts | Stops |
|---|---|---|---|---|
| `pollReleaseState` (`_deploy_tab.html`) | `/api/release-manager/live-status` (cheap, state-file-only) | 5000ms | **only** if a job was already active at page render (`releaseHadActiveJob`, computed server-side) | one-time `location.reload()` when the polled job transitions to a terminal state; interval itself is never even created on an idle page |
| `pollAgentUpdateState` (`_agent_update_tab.html`) | same endpoint | 5000ms | same gating, for `agent_update_job` | same |

Both were already implemented this way by the earlier
`DEPLOY_AGENT_REFRESH_PERFORMANCE_FIX.md` fix -- **unchanged and
reconfirmed** by this audit, live: a 30-second idle capture on the
Release page produced **zero** `/api/*` requests (no active job).
This task did not need to change polling.

## 5. SERVER BLOCKING CHECK

`GET /agent/health` also calls `mes_status()` (its own `mes` field), so
it independently pays the same cost pre-fix -- not because one request
blocks another, but because both routes do the same expensive work.
Live, **after** the fix, with `/agent/health` sampled every 300ms by a
separate thread *while* a real ~3.6s cold Release page load was in
flight: **6/6 samples returned HTTP 200**, max latency **0.702s** --
`/agent/health` was never stuck behind the slow request. waitress runs
with `threads=8`; DNS/subprocess I/O releases the GIL, so concurrent
requests are not serialized by one slow one. No additional blocking fix
was needed beyond making `mes_status()` itself fast.

## 6. LOG BEHAVIOR

Confirmed via code audit: no `tail()` call exists anywhere in
`_release_deploy_tab_context()`, `mes_status()`, `qa_status()`,
`_release_summary()`, `_qa_release_summary()`, or
`_deployment_platform_summary()`. Every `tail()` call in `agent.py` is
either inside a background job worker (persisting `log_tail` into state
once, at completion -- read from state, not re-read from disk) or behind
an explicit on-demand detail route (`release_manager_history_detail`,
incident/backup/server detail endpoints). Opening Release does not tail,
stream, or poll any log.

## 7. LARGE ARTIFACT HASHING

`sha()` is cached (mtime_ns + size keyed, in-process, from the earlier
performance-fix task) -- confirmed live: first call after a fresh process
start (`_qa_release_summary()`, which hashes the QA release ZIP) took
1.164-1.276s; the identical call immediately after took **0.020s**. The
MESFlow release ZIP behaved the same (`_release_summary()`: 0.346-0.495s
cold, 0.048s warm). Opening Release does re-hash on the very first call
after a process restart (unavoidable -- there is no persisted digest
store this reads from yet) but never again after that for an unchanged
file. This was already correct; unchanged by this task.

## 8. REMOTE PRODUCTION TEST CHECK

Confirmed via code audit: `_release_summary()`/`_qa_release_summary()`
only read `MESFLOW_PRODUCTION_TEST_AGENT_URL` as a **string** (to decide
whether to show "no Production Test Agent configured"); neither they nor
`_deployment_platform_summary()` construct an HTTP request to it. No
`_remote_agent_*` function is called anywhere in the Release page's
render path. TEST_PASS/LOCAL_PASS are read from persisted
`promotion-state.json` only. Already correct; unchanged by this task.

## 9. FIX

**Root cause:** `http_json()` (used by `mes_status()`) re-resolves DNS
for every unreachable candidate URL on every single call, with no
memory of a very recent failure -- 3 calls per `mes_status()` invocation,
each paying the full ~5s glibc DNS-retry cost independently.

**Fix (`agent.py`, `http_json`/`_http_json_base`):** a small in-process
cache (`_MES_BASE_UNREACHABLE`, mirroring the existing `_SHA_CACHE`
pattern) remembering, per base URL, the timestamp of its last
connection-level failure (HTTP status code `0` -- DNS/connect/timeout, as
opposed to a real HTTP response with any status). While that memory is
fresh (`_MES_BASE_UNREACHABLE_TTL = 45s`), `http_json()` skips the real
network attempt for that base entirely. Any real HTTP response (even an
error status) clears the cache for that base immediately, so recovery is
never delayed. This is a projection-layer fix only: `mes_status()`'s
correctness (online/offline determination) is unchanged, only the cost
of computing it.

## ZIP REHASH ON PAGE LOAD: NO
## DOCKER INSPECT ON PAGE LOAD: YES (cheap, ~0.35-0.4s local subprocess calls via `_docker_mes_state()`, not the bottleneck, left unchanged)
## REMOTE CALL ON PAGE LOAD: NO
## LOG READ/POLL ON PAGE LOAD: NO
## ESP REQUEST ON PAGE LOAD: NO

## POLLERS BEFORE
`pollReleaseState` / `pollAgentUpdateState`, gated (only run while a job
is active, stop at terminal state) -- see section 4.

## POLLERS AFTER
Unchanged (already correct; this task did not touch polling).

## 10. API SPLIT

Not needed. The endpoint was already split appropriately
(`/api/release-manager/live-status` for job polling,
`/api/release-manager/history` for on-demand history, per-log/detail
routes for on-demand deep data). The bottleneck was inside the
*lightweight* summary path itself, not a giant endpoint doing unrelated
work -- fixing `mes_status()`'s cost was the correct scope, not
re-architecting the API surface.

## 11. BROWSER REGRESSION (real Chromium, after the fix, live)

- **First load after a container restart** (worst case -- cache cold):
  **3596.1ms** (down from a *guaranteed* 15338.8ms on every single load,
  before). This single remaining cost is the same ~5s glibc DNS retry,
  now paid **once** instead of three times per load.
- **Navigate away (Dashboard) and back to Release, 5 times in a row:**
  923.5ms, 719.8ms, 867.3ms, 685.3ms, 887.6ms -- stable, **not
  increasing**.
- **Idle 30 seconds on the Release page:** **0** `/api/*` requests.
- **`GET /agent/health` sampled concurrently during the slow first
  load:** 6/6 HTTP 200, max 0.702s -- not blocked.
- **Page errors:** 0. **Console errors:** 0.
- No destructive deployment action was started at any point during this
  verification.

## AFTER

**TIME TO UI:** cold ~3.6s (down from guaranteed 15.3s); warm (within the
45s cache window -- i.e. essentially every navigation in a normal
session) ~0.5-0.9s.
**INITIAL REQUEST COUNT:** 3 (unchanged shape: HTML + CSS + JS)
**SLOWEST REQUEST:** main HTML response -- cold 3596ms / warm ~450-930ms
(was a guaranteed 15338.8ms every time)
**AGENT HEALTH DURING LOAD:** PASS -- not blocked, 6/6 200, max 0.702s

## IDLE 30S NETWORK REQUESTS: 0
## DUPLICATE TIMERS: none observed (5x nav-back latency stable, not increasing)
## PAGE ERRORS: 0
## CONSOLE ERRORS: 0

## KNOWN LIMITATION / NOT FIXED

The very first Release (or `/agent/health`) hit after the Agent process
starts, or after 45s of no MESFlow-status traffic, still pays one real
~3.6-5.5s DNS-retry cost -- this task made it happen **once** instead of
**three times per page load, on every single page load**, but did not
eliminate it, because the underlying cause is this local dev
environment's Docker network topology (`mesflow-deploy-agent` and
`mesflow-app` are on two different Docker networks), not application
code. A fully synchronous-request-independent fix (render the page
immediately and fetch `mes`/`qa` status asynchronously) would eliminate
this residual cost unconditionally, but is a materially larger change to
the Release page's render path than this task's proven root cause
required -- flagged here as a candidate follow-up, not implemented.

## FILES CHANGED

- `agent.py` -- `_MES_BASE_UNREACHABLE` cache + `_mes_base_recently_unreachable()`/
  `_mark_mes_base_reachability()`, wired into `http_json()`.
- `tests/test_release_page_performance_audit.py` -- new, 4 tests: the
  cache prevents repeated DNS-cost attempts within a single `mes_status()`
  call, a real response clears the cache immediately, `mes_status()` stays
  bounded under a simulated slow-DNS condition, and the Release Deploy tab
  context builder still calls each expensive function exactly once (no
  duplicate-recompute regression from the earlier fix).

## AUTOMATED TESTS

`tests/test_release_page_performance_audit.py`: 4 passed. Full suite
(fresh isolated `WORKSHOP_AGENT_HOME`): **400-412 passed** (skip count
varies run-to-run for unrelated environment-contingent tests), **0
failed** in either run.

## AGENT REBUILT: YES
`docker compose -f docker/compose.linux.yml -f docker/compose.dev.override.yml -f docker/compose.bootstrap.override.yml up -d --build mesflow-deploy-agent`
from the official workspace, twice in this pass (initial fix, then a TTL
adjustment 20s→45s after live testing showed real navigation gaps could
exceed 20s). `mesflow-app`/`mesflow-postgres`/`mesflow-nginx` were not
restarted at any point (confirmed: their `docker ps` uptimes span this
entire session, unaffected).

## AGENT HEALTH: PASS
`docker ps` → `healthy`, `127.0.0.1:8090->8090/tcp`. `GET /agent/live` →
`ok:true`. `GET /agent/health` → HTTP 200.

## PRODUCTION TOUCHED: NO

## NOTE ON THIS SESSION'S LOGIN

This local container's admin password (set earlier this session via the
already-fixed `/agent/local-reset` flow) did not match when re-verifying
after the first rebuild in this pass; re-applied the same recovery flow
and it is now `KioskVerify_2026b!`. Change it if you'd like a different
one -- the recovery code is unaffected.
