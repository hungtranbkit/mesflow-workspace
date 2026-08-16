
# Deploy Agent Frontend Cache Busting

Project: `deploy-agent/`. Goal: users must never need a hard-refresh or
Incognito after an Agent update to see new JS/CSS.

## CACHE POLICY

- HTML/control-plane pages (every response except `/static/*`):
  `Cache-Control: no-cache, must-revalidate` — always revalidated, never
  served stale from a shared/browser cache, so a rebuilt Agent's new HTML
  (referencing the new asset URL) is always the one the browser sees on
  the very next request/reload.
- Versioned static JS/CSS (`/static/*`, always requested with `?v=...`):
  `Cache-Control: public, max-age=31536000, immutable` — safe, because
  the URL itself only ever repeats for byte-identical content.
- Implemented as a single `@app.after_request` hook in `agent.py`
  (`_apply_cache_policy`), branching only on `request.path.startswith('/static/')`.
  No route previously set its own `Cache-Control`, so nothing was
  overridden.

## FRONTEND_BUILD_ID

`FRONTEND_BUILD_ID = AGENT_VERSION + "-" + <10-hex-char SHA256 over every
static file's relative path + content, sorted>` (`_compute_frontend_build_id()`
in `agent.py`, computed once at module load). Deterministic content hash,
not mtime — proven live: after reverting a one-line test change to
`static/css/agent.css` and rebuilding, the id returned to its exact
original value (`...77c5dc7860`), and changing the content produced a
different one (`...bafb00739b`) — an mtime-only signal would have
produced a different id both times, defeating the whole point of
letting versioned assets cache forever.

## ASSET VERSIONING

New `static_url(filename)` helper (registered as a Jinja global,
`app.jinja_env.globals['static_url']`) — **not** a global `url_for`
override, per this task's explicit preference: it only ever wraps
`url_for('static', filename=...)` and appends `?v=<FRONTEND_BUILD_ID>`;
every other `url_for()` call in the codebase (redirects, form actions,
API endpoints, ~40+ other call sites) is untouched. Applied to all 5
template references audited (the complete set — verified by a
regression test that fails if any template ever regresses to a bare
`url_for('static', ...)`):

| Template | Asset |
|---|---|
| `_operations_shell_end.html` (shared shell, included by ops/release/dashboard) | `js/core/navigation.js` |
| `dashboard.html` (main Agent UI / Overview) | `css/agent.css` |
| `ops.html` (Operations Center) | `css/agent.css` |
| `release/index.html` (Release Manager) | `css/agent.css` |
| `kiosk.html` (OTA / ESP Kiosk) | `css/agent.css` |

## HTML CACHE / STATIC CACHE

Verified live against the real rebuilt Agent (`curl`/Playwright):
- `GET /` (dashboard): `Cache-Control: no-cache, must-revalidate`
- `GET /agent/login` (POST response too): `Cache-Control: no-cache, must-revalidate`
- `GET /static/css/agent.css?v=...`: `Cache-Control: public, max-age=31536000, immutable`

## OLD ASSET BEFORE

`/agent/static/css/agent.css?v=2.23.20-docker-runtime-77c5dc7860`

## NEW ASSET AFTER

After a real, live content change + full `docker compose ... up -d --build`
rebuild: `/agent/static/css/agent.css?v=2.23.20-docker-runtime-bafb00739b`
— fetched via a **plain `page.reload()`** in the exact same persistent
browser profile/context used before the rebuild (real cookies, real HTTP
cache carried over, nothing cleared): new URL, new bytes actually served
(the test marker appended to the source file was present in the fetched
response), old CSS not reused from cache. Reverting the source change and
rebuilding again returned the id to `...77c5dc7860` exactly, confirming
determinism in both directions.

## NORMAL RELOAD

**PASS.** `page.reload({ waitUntil: 'domcontentloaded' })` (no
cache-bypass flag — the Playwright equivalent of a plain F5, not
Ctrl+Shift+R) was sufficient in every test: unchanged-content reload
returns the identical asset URL (verified in both a normal context and a
separate incognito-equivalent context); post-rebuild reload returns the
new URL and new bytes.

## HARD RELOAD REQUIRED: NO

Never needed in any test — the `no-cache, must-revalidate` HTML policy
guarantees the browser always re-fetches and re-parses the HTML on a
plain reload, and a changed static URL is, by construction, a cache miss
regardless of the old URL's `immutable` caching.

## INCOGNITO DIFFERENCE: NO

Ran the identical login → asset-URL → cache-header → Docker-page sequence
in a normal `browser.newContext()` and a second, completely separate
`browser.newContext()` (Playwright's per-context storage is isolated the
same way Incognito is — no persisted profile is shared). Every field
(`cssHref`, `htmlCacheControl`, `staticCacheControl`,
`dockerRowsAfterAdvanced`, `dockerListVisibleAfterAdvanced`) was
byte-for-byte identical between the two.

## DOCKER LIST CLICK/ADVANCED: PASS

Re-verified after every rebuild in this pass (initial build, marker
build, final clean build): 18 real rows before and after, list stays
visible, `<details>` opens correctly for exactly the clicked row.
Docker UI code itself was **not modified** in this task — only its
`<link>`/`<script>` asset references gained `static_url()` (same
generated `/static/...` path, plus a query string), which cannot affect
its DOM/event behavior.

## PAGE ERRORS: 0
## CONSOLE ERRORS: 0
(across the normal-window run, the incognito-equivalent run, and the
real pre/post-rebuild persistent-context reload run.)

## METADATA EXPOSURE

`GET /live` and `GET /api/status` both now include `agent_version` and
`frontend_build_id`, verified live:
```json
{"agent_version":"2.23.20-docker-runtime","frontend_build_id":"2.23.20-docker-runtime-77c5dc7860","ok":true,"runtime_mode":"docker-linux"}
```

## FILES CHANGED

- `agent.py` — `_compute_frontend_build_id()`, `FRONTEND_BUILD_ID`,
  `static_url()` + Jinja global registration, `_apply_cache_policy`
  (`@app.after_request`), `frontend_build_id` added to `/live` and
  `/api/status`.
- `templates/_operations_shell_end.html`, `templates/dashboard.html`,
  `templates/ops.html`, `templates/release/index.html`,
  `templates/kiosk.html` — `url_for('static', filename=...)` →
  `static_url(...)`.
- `tests/test_frontend_cache_busting.py` — new, 10 tests (determinism,
  content-sensitivity, no-bare-url_for-static regression guard, header
  values, metadata exposure, cross-process rebuild simulation).

## AUTOMATED TESTS

`tests/test_frontend_cache_busting.py`: 10 passed. Full suite
(`pytest tests/ -q`): **392 passed, 2 skipped, 8 subtests passed, 0 failed**.

## AGENT REBUILT: YES (3 times in this pass — initial fix, marker-content live test, final clean revert)
`docker compose -f docker/compose.linux.yml -f docker/compose.dev.override.yml -f docker/compose.bootstrap.override.yml up -d --build`
from the official workspace. Only `mesflow-deploy-agent` was touched;
`mesflow-postgres`/`mesflow-app`/`mesflow-nginx`/`mesflow-qa-center` were
not restarted at any point.

## AGENT HEALTH: PASS
`docker ps` → `healthy`, port `127.0.0.1:8090->8090/tcp`. `GET /live` →
`ok:true`. `GET /agent/health` → HTTP 200.

## SCOPE NOTES

- Docker UI behavior: unchanged (task instruction). Deployment/recovery
  logic: untouched. This task only touched asset URL generation and
  response cache headers.
- As a side effect of this rebuild cycle, the previously-reported
  `local-reset` 403-over-published-port issue (fixed earlier this
  session, not yet redeployed) is now also live and reconfirmed working:
  `GET /agent/local-reset` from the real host now returns 200.
