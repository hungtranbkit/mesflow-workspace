# ESP Kiosk Tutorial Pipeline Report

Generated: 2026-08-12 (Asia/Bangkok)

## Result

PASS for the local pipeline. A newly generated standalone tutorial ZIP was uploaded through the local Deploy Agent HTTP form, validated, atomically published into the local MESFlow runtime tree, loaded by the MESFlow API, rendered as seven videos in the dedicated browser tab, and an actual video playback assertion passed. No production deployment, `/opt` write, database mutation, migration, or production restart was performed.

## Versions

- MESFlow: `65.8.44.54`
- Deploy Agent: `2.15.0-docker-runtime`
- ESP firmware: `ESP32-KIOSK-5.1.9-WORKER-QTY-FLOW` (unchanged)
- Kiosk tutorial: `5.1.9.1`
- Firmware source commit recorded by manifest: `a1827e3729db84328c06322309f7a4bab4750695`

## Generator and package

- Generator uses an explicit fresh device framebuffer capture directory and rejects captures whose recorded firmware version differs from the source firmware constant.
- All seven MP4 files were regenerated from `esp-kiosk/test-results/esp-ui-capture-20260812_123901`.
- Audio is disabled at render and concat time (`-an`). `ffprobe` found exactly one video stream and zero audio streams in every MP4.
- Manifest now follows the independent contract: type, tutorial/firmware versions, timestamps, source commit, render method, audio flag, covered cases, and per-video id/filename/title/description/order/cases/duration.
- Package: `artifacts/esp-kiosk/ESP_Kiosk_Tutorial_5.1.9.1.zip` (approximately 521 KiB).
- Package validation: PASS. The reusable package script verified the exact seven names, non-empty files, streams, zero audio, manifest/version agreement, nine root entries, and exactly one `esp-kiosk-tutorial/` root.

## Deploy Agent

- A separate `Video hướng dẫn ESP Kiosk` upload form and endpoint were added. It has a visible file selection state, current tutorial metadata, auto upload, and a manual `Upload & Publish` fallback.
- Validation covers ZIP size, decompressed size, zip-slip/path traversal, symlink/special files, exact root, exact allowed files, JSON/type/version consistency, required per-video metadata, safe basename `.mp4` files, uniqueness, and non-empty payloads.
- Job stages observed from the real local HTTP upload: `uploading -> validating -> staging -> backing_up -> publishing -> verifying -> success`.
- Same version/same bytes is a no-op; same version/different bytes is rejected with an instruction to increase tutorial version.
- Atomic publish and rollback behavior is covered by focused tests. Current content is renamed to a versioned backup, the prepared temporary directory is renamed into place, and verification occurs after the swap. Only one previous backup is retained.
- Focused tutorial publish tests: `2 passed` after the final manifest-contract validation change.
- Local Agent health: `ok=true`, version `2.15.0-docker-runtime`, bound only to `127.0.0.1:18090` for this test.
- Local E2E publish target: `mesflow/runtime/tutorials/esp-kiosk/` through a bind mount. Production contract target is `/opt/mesflow/runtime/tutorials/esp-kiosk/`; it was not written during this task.

## MESFlow

- Added a final navigation item, `Hướng dẫn ESP Kiosk`, after the existing MESFlow tutorial item.
- The page displays friendly titles/descriptions rather than technical filenames, firmware and tutorial versions, and seven responsive native video players with controls, seeking and fullscreen support.
- Manifest is read from runtime on every API request; tutorial updates do not require an application restart.
- Authenticated routes:
  - `GET /api/esp-kiosk-tutorial`
  - `GET /esp-kiosk-tutorial/videos/<allowed-manifest-filename>`
- Video serving is restricted to safe `.mp4` basenames present in the current manifest and supports conditional/range responses for playback and seeking.
- No firmware mismatch warning is guessed because no trustworthy current-device firmware registry was found. The tutorial firmware version is shown directly.

## Test evidence

- Reconciliation ran before edits for MESFlow and Deploy Agent. Deployed trees were older than the corresponding workspace sources, so no `/opt` source was imported and existing workspace-only work was preserved.
- Python compilation, JavaScript syntax, shell syntax, version consistency and package validation: PASS.
- MESFlow focused tests: `9 passed`.
- Deploy Agent focused pipeline tests: `2 passed`; the prior focused Agent/QA set recorded `8 passed`.
- Full MESFlow Playwright regression after changes: `7 passed`.
- Final dedicated browser test against the package uploaded by Agent: `1 passed`.
- Browser evidence: runtime manifest returned seven entries, the dedicated tab showed seven video elements, existing tutorial navigation remained present and ordered before the Kiosk tab, no technical `.mp4` filename was exposed, the video request returned `200/206`, playback advanced `currentTime > 0`, and no browser page errors occurred.
- Runtime publish contains `VERSION.txt`, `manifest.json`, and seven non-empty files under `videos/`; all seven source files were probed as video-only.

## Regression and limitations

- MESFlow release upload/deploy and QA upload code paths were not changed. Existing focused Agent/QA tests passed.
- Existing MESFlow tutorial navigation remains available; full browser regression passed.
- Navigation overflow assertion passed in the browser test.
- A broader legacy Deploy Agent test run had 22 passes and two stale `test_deploy_safety.py` failures because those tests do not mock the newer PostgreSQL health guard. This is a known test-fixture issue outside the tutorial pipeline; no pipeline test failed.
- The local MESFlow health payload visible from the isolated Agent container cannot reach the separate test API URL configured for that container. Browser validation ran directly against the healthy MESFlow test stack and passed.
- Generated/runtime evidence is local-only. Production permissions and the actual `/opt` filesystem swap remain intentionally untested until human-approved deployment.

## Files changed

### ESP Kiosk

- `TUTORIAL_VERSION.txt`
- `tools/generate_tutorial_videos.py`
- `scripts/package-tutorial.sh`
- regenerated `artifacts/esp-kiosk/tutorial/manifest.json` and seven MP4 files
- `artifacts/esp-kiosk/ESP_Kiosk_Tutorial_5.1.9.1.zip`

### Deploy Agent

- `agent.py`
- `templates/index.html`
- `VERSION.txt`
- `docker/Dockerfile`
- `docker/compose.linux.yml`
- `docker/compose.windows.yml`
- `README.md`
- `docs/DEPLOY_DOCKER.md`
- `tests/test_esp_kiosk_tutorial_publish_v2150.py`

### MESFlow

- `VERSION.txt`
- `app/mesflow/__init__.py`
- `release.json`
- `compose.yml`
- `compose.test.yml`
- `app/mesflow/web/app.py`
- `app/mesflow/web/static/app.js`
- `tests/test_v6584454_esp_kiosk_tutorial.py`
- `tests/e2e/mesflow.spec.js`
- prior version expectation tests updated for version consistency

## Migration and production action

- Migration: NO.
- Database changed: NO.
- Production action required: YES, but only after human review/approval. Deploy the new Deploy Agent and MESFlow application releases through the approved production process, then upload `ESP_Kiosk_Tutorial_5.1.9.1.zip` through the new Agent module. No production action was taken here.
