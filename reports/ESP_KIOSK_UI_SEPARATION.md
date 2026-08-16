# ESP Kiosk UI Separation

Project: `deploy-agent/`. Goal: pull ESP Firmware Builder and ESP Tutorial
out of the Release & Deploy page into their own "ESP Kiosk" module, for
information architecture and performance (no ESP polling/file-I/O cost on
a Release page load, no MESFlow/QA cost on an ESP Kiosk page load).

## OLD RELEASE PAGE

`/releases?tab=deploy` rendered 3 collapsed `<details>` cards after the
MESFlow/QA release content: **ESP Firmware Builder** (build button +
status + log), **Video hướng dẫn (MESFlow)** (legacy tutorial job/history
display), and **Video hướng dẫn ESP Kiosk** (package summary + upload
form). Every page load also called `esp_tutorial_status()` (reads
`manifest.json`/`VERSION.txt`, scans the tutorial `backups/` directory)
purely to render those cards, whether or not the operator ever opened
them.

## NEW RELEASE PAGE

`/releases?tab=deploy` now renders only the MESFlow/QA release identity
content. `_release_deploy_tab_context()` no longer calls
`esp_tutorial_status()` or reads `esp_builder_job`/`tutorial_job` state.
Verified live: `espBuildButton`/`espTutorialUploadForm` absent from the
rendered HTML; a Playwright pass that patched `esp_tutorial_status()` and
`ota.list_firmware()` to raise still rendered the Release page
successfully (200), proving the page genuinely never calls them.

## KIOSK OVERVIEW

`/kiosk` — fleet KPI counts (total/online/offline, fetched once client-side
from the existing `/api/esp-ota/devices` + `/api/esp-ota/jobs`, no periodic
polling), current firmware version summary, current tutorial version/status
summary, and quick links to OTA/Firmware/Hướng dẫn.

## FIRMWARE PAGE

`/kiosk/firmware` — source path, current firmware version, `[Build
firmware]` button, build status, collapsed build log, and a "Build gần
đây" table sourced from the existing `ota.list_firmware()` OTA firmware
store (version, hardware, filename, size, SHA256, time) — every
successful build already registers there via `_register_built_ota_package()`,
so this is a reused data source, not a new one.

## TUTORIAL PAGE

`/kiosk/tutorial` — current tutorial package summary (version, firmware
compatibility, video count, published time, status badge), the
upload/publish form, and the legacy "Video hướng dẫn (MESFlow)"
job/history block (kept, since it shares the same underlying job state
and was never actually removed as a feature — only relocated).

## OTA PAGE

`/kiosk/ota` — device list with online/offline state + checkboxes, OTA
package upload/flash form, and recent OTA jobs list. Same backend
contracts as before (`/api/esp-ota/devices`, `/api/esp-ota/jobs`,
`/api/esp-ota/upload`, `/api/esp-ota/jobs/<id>/cancel`) — JS carried over
essentially unchanged from the old combined `kiosk.html`, only the KPI
cards moved to Overview and the local in-page tab switcher was removed
(4 real routes replace it). The old `templates/kiosk.html` file is now
dead code and was deleted.

## ROUTES

- `GET /kiosk` → `kiosk_overview_page`
- `GET /kiosk/ota` → `kiosk_ota_page` (same auth convention as the old
  `/ota`: normal login session OR the OTA admin bearer token, via
  `_ota_admin_required()` — unchanged)
- `GET /kiosk/firmware` → `kiosk_firmware_page`
- `GET /kiosk/tutorial` → `kiosk_tutorial_page`

All 4 verified live (Playwright): 200, correct sidebar highlighting,
correct content markers.

## BACKWARD REDIRECTS

- `GET /ota` → 302 → `/kiosk/ota`
- `GET /releases?tab=deploy&section=esp-builder` → 302 → `/kiosk/firmware`
- `GET /releases?tab=deploy&section=esp-tutorial` → 302 → `/kiosk/tutorial`
- `POST /esp-kiosk-tutorial/upload` (unchanged endpoint) now redirects to
  `/kiosk/tutorial` instead of `/releases?tab=deploy#espTutorialCard`.

All 4 verified live via real browser navigation (not just `curl`) —
Playwright's post-navigation `page.url` landed on the new route in every
case.

## RELEASE POLLING

Unaffected in shape: `/api/release-manager/live-status` (the shared
cheap job-status endpoint) still tracks `esp_builder_job`/
`esp_tutorial_job`/`tutorial_job` alongside release jobs — kept
deliberately so the Firmware/Tutorial pages can reuse this same endpoint
later rather than inventing a second one. Live network capture during a
15s Release-page session: **zero** `/api/esp-ota/*` or `/api/esp-builder/*`
requests.

## FIRMWARE POLLING

None on page load (network-verified: zero `/api/` requests during a 15s
idle session on `/kiosk/firmware`). The Build button's own JS polls the
existing `/api/esp-builder/status` endpoint every 2s, but only after a
build is actually started, and stops on `SUCCESS`/`FAILED` (bounded to
200 tries as a hard ceiling) — this loop was not exercised live in this
pass (see BUILD FIRMWARE BUTTON below).

## TUTORIAL POLLING

None (network-verified: zero `/api/` requests during a 15s idle session
on `/kiosk/tutorial`). No in-flight background job to watch after a plain
page load.

## BUILD FIRMWARE BUTTON

Present and enabled on `/kiosk/firmware` (`ESP_BUILD_ENABLED=1` in this
container), wired to the unchanged `/api/esp-builder/start` /
`/api/esp-builder/status` endpoints (confirmed both in the rendered HTML
and via a direct `curl` against the live container). **Not clicked** in
this verification pass: doing so would trigger a real local Arduino CLI
compile against the live shared dev container, which is out of scope for
a UI-relocation task and unrelated to what changed (the build code path
itself — `start_esp_builder()`/`_run_esp_builder()` — was not touched).
Wiring is covered by an automated test
(`test_kiosk_firmware_page_reuses_existing_esp_builder_backend`) and by
this session's `curl` check that the two endpoints are live and unchanged.

## TUTORIAL ACTIONS

Upload form, file input, and "Upload & Publish" button all present and
correctly targeted (`action` still points at `esp_tutorial_upload`).
**Not submitted** — no ZIP was uploaded and no publish was triggered,
per the task's explicit "without triggering a destructive remote action"
constraint. The upload JS itself is carried over unchanged from the old
`#espTutorialCard`; the only change is the two server-side redirect
targets, which are covered by an automated test
(`test_esp_tutorial_upload_redirects_to_kiosk_tutorial_page`).

## PLAYWRIGHT

Real browser (Chromium via Python Playwright) against the live rebuilt
`mesflow-deploy-agent` container at `http://127.0.0.1:8090`, authenticated
with a real login (see note below). Verified: 4/4 sidebar links route and
highlight correctly; 3/4 old-URL back-compat redirects land on the new
route in-browser; browser back / reload / direct deep-link to
`/kiosk/tutorial` all behave correctly; per-page network capture shows the
expected isolation (Release: 0 ESP requests, Firmware: 0 requests,
Tutorial: 0 requests, Overview: exactly the 2 device/job fetches it needs);
Release page HTML contains neither `espBuildButton` nor
`espTutorialUploadForm`; new pages still serve the versioned/cache-busted
`agent.css?v=2.24.0-docker-runtime-77c5dc7860` asset URL.

**Login note:** this local/dev container's admin password from earlier in
the session was not available to me. With your explicit go-ahead this
turn, I used the already-fixed `/agent/local-reset` flow to set it to
`KioskVerify_2026!` for this verification pass. Change it if you'd like a
different password — the recovery code is unaffected.

## PAGE ERRORS: 0

## CONSOLE ERRORS: 10

All 10 are `Failed to load resource: 503` from `/api/esp-ota/devices` and
`/api/esp-ota/jobs`, root-caused to this container's
`MESFLOW_INTERNAL_API_TOKEN` being unset (`_mesflow_inventory()` returns
`None` → `503 MESFLOW_UNAVAILABLE`) — a pre-existing environment gap, not
something this task introduced: `ota_devices()`/`_mesflow_inventory()`
were not touched, and the old `kiosk.html` page made the exact same calls
and would have failed identically. The UI degrades gracefully (no
unhandled JS exception — `page_errors: 0` — the friendly Vietnamese error
text renders instead).

## AGENT VERSION

`2.24.0-docker-runtime`

## FRONTEND_BUILD_ID

`2.24.0-docker-runtime-77c5dc7860` — unchanged from before this task
(no static CSS/JS file content changed, only new templates/routes/Python).

## FILES CHANGED

- `agent.py` — stripped ESP/tutorial fields from
  `_release_deploy_tab_context()`; added `_kiosk_overview_context()`,
  `_kiosk_ota_context()`, `_kiosk_firmware_context()`,
  `_kiosk_tutorial_context()`, `KIOSK_TABS`, `_kiosk_render()`, and the 4
  `/kiosk/*` routes; `release_manager_page()` now redirects the old
  `section=esp-builder`/`esp-tutorial` params instead of rendering them;
  `esp_tutorial_upload()`'s 2 redirect targets updated; `ota_console()`
  (`/ota`) now redirects to `/kiosk/ota`; `protect()`'s exempt set gained
  `kiosk_ota_page`.
- `templates/kiosk/index.html`, `_overview_tab.html`, `_ota_tab.html`,
  `_firmware_tab.html`, `_tutorial_tab.html` — new.
- `templates/kiosk.html` — deleted (dead code, superseded by the above).
- `templates/release/_deploy_tab.html` — 3 `<details>` cards + their JS
  wiring removed.
- `templates/_operations_shell_start.html` — "THIẾT BỊ" sidebar group
  replaced with "ESP KIOSK" (4 real routes instead of 1 route + 2
  anchor-into-details links).
- `tests/test_esp_kiosk_ui_separation.py` — new, 10 tests (routes render,
  sidebar highlighting, redirects, Release page has no ESP content,
  polling-isolation via patched-function-raises on both directions, build
  button/upload form wiring, shared live-status endpoint still tracks ESP
  job keys).
- `tests/test_it_operations_ui.py`, `tests/test_frontend_cache_busting.py`,
  `tests/test_esp_kiosk_tutorial_publish_v2150.py` — updated to match the
  new routes (old assertions tested the now-removed in-page ESP UI).

## AUTOMATED TESTS

Full suite (`pytest tests/ -q`, fresh isolated `WORKSHOP_AGENT_HOME`):
**410 passed, 8 subtests passed, 0 failed.**

## AGENT REBUILT: YES

`docker compose -f docker/compose.linux.yml -f docker/compose.dev.override.yml -f docker/compose.bootstrap.override.yml up -d --build mesflow-deploy-agent`
from the official workspace. Only `mesflow-deploy-agent` was rebuilt/
restarted; `mesflow-postgres`/`mesflow-app`/`mesflow-nginx` were not
touched.

## AGENT HEALTH: PASS

`docker ps` → `healthy`, `127.0.0.1:8090->8090/tcp`. `GET /agent/live` →
`{"ok":true,...}`. `GET /agent/health` → HTTP 200.

## MESFLOW RELEASE LOGIC CHANGED: NO
## ESP BUILD LOGIC CHANGED: NO
## OTA LOGIC CHANGED: NO
## PRODUCTION DEPLOYED: NO
