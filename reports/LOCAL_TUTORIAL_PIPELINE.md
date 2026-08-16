# Local ESP Kiosk Tutorial Pipeline

Generated: 2026-08-12, Asia/Bangkok

## RESULT

PASS for the complete local-only pipeline:

`local generator -> validation -> ZIP + SHA256 -> local Deploy Agent upload -> failed-package preservation -> atomic publish -> MESFlow manifest reload -> browser playback`

No file under `/opt` was changed. No production deploy/restart, database write, migration, firmware flash, firewall change, or server package installation was performed.

## LOCAL GENERATOR

- Firmware, framebuffer capture, Pillow overlay, FFmpeg encode, FFprobe validation, manifest generation and ZIP packaging run only from `esp-kiosk/` in the local workspace.
- Firmware source of truth: `esp-kiosk/esp/mesflow_app.cpp` and its related firmware source files.
- Capture used: `esp-kiosk/test-results/esp-ui-capture-20260812_123901`.
- Output directory: `artifacts/esp-kiosk/tutorial/`, containing `manifest.json` and `videos/` with seven MP4 files.
- The manifest contains `source_fingerprint` and `generator_fingerprint`. The source fingerprint covers firmware source, generator/package/build scripts, overlays embedded in the generator, and PNG/JSON framebuffer inputs.
- Incremental evidence: the first final run regenerated seven videos; the immediately repeated command detected the identical fingerprint and reused the validated videos. `--force` remains available.
- Tutorial version is read from `esp-kiosk/TUTORIAL_VERSION.txt` and validated independently from firmware version.

## BUILD COMMAND

```bash
cd ~/workspace/mesflow/esp-kiosk
./scripts/build-tutorial-package.sh
```

Optional inputs:

```bash
./scripts/build-tutorial-package.sh --capture-dir <fresh-capture>
./scripts/build-tutorial-package.sh --force
```

## PACKAGE

- ZIP: `artifacts/esp-kiosk/packages/ESP_Kiosk_Tutorial_5_1_9_2.zip`
- Checksum: `artifacts/esp-kiosk/packages/ESP_Kiosk_Tutorial_5_1_9_2.zip.sha256`
- ZIP has one root, `esp-kiosk-tutorial/`.
- Root contains `VERSION.txt`, `manifest.json`, and `videos/` with exactly seven expected MP4 files.
- Package size at validation: approximately 521 KiB.
- SHA256 verification: PASS.

## PACKAGE VERSION

`5.1.9.2`

## FIRMWARE VERSION

`ESP32-KIOSK-5.1.9-WORKER-QTY-FLOW`

Firmware was not modified or flashed.

## VALIDATION

- All seven files exist and are non-empty.
- Manifest filenames exactly match the seven files under `videos/`.
- Duration is greater than zero for every video.
- FFprobe found one valid video stream per file.
- Resolution is `1280x720` for every file.
- Invalid video/package state stops the build before a successful package result.
- Agent validates size, decompressed size, exact root and directory contract, JSON/type/version agreement, required video metadata, safe basename, `.mp4` extension, non-empty files, zip-slip/path traversal, symlinks/special files and unexpected files.

## AUDIO

`audio: false`. FFprobe confirmed zero audio streams in all seven MP4 files.

## AGENT SERVER GENERATION REMOVED/DISABLED

- Deploy Agent does not run FFmpeg, FFprobe, Playwright, TTS, Arduino tooling, firmware build, framebuffer rendering, or MP4 regeneration for ESP tutorial uploads.
- The previous server-side `tutorial/rebuild` and login-check endpoints are disabled and return HTTP `410 SERVER_VIDEO_GENERATION_DISABLED`.
- The old server generation form was replaced by a local-build notice. The independent ESP tutorial card remains upload/publish only.
- Final HTTP evidence: `/agent/tutorial/rebuild` returned `410` with “Video được build trên máy local và upload qua Agent”.

## AGENT UPLOAD

- Deploy Agent version: `2.15.1-docker-runtime`.
- Real multipart upload ran through the authenticated local Agent on `127.0.0.1:18090`.
- Final upload accepted `ESP_Kiosk_Tutorial_5_1_9_2.zip` and reported tutorial `5.1.9.2`, firmware version above, seven videos and job `success`.
- The helper `scripts/upload-kiosk-tutorial.sh` reports the newest package/checksum and directs the operator to the Agent web form. It neither requests nor stores a password.

## ATOMIC PUBLISH

- Observed successful stages: `uploading -> validating -> staging -> backing_up -> publishing -> verifying -> success`.
- Publish prepares a temporary directory, renames the current live directory to a versioned backup, atomically renames the prepared directory into place, and verifies the published manifest/files.
- Focused atomic/duplicate/zip-slip tests: `2 passed`.
- Failure preservation test: the obsolete flat-layout ZIP was rejected (`failed`), while tutorial `5.1.9.1` remained published and readable. The valid package was then published as `5.1.9.2`.
- Production contract path: `/opt/mesflow/runtime/tutorials/esp-kiosk/`.
- Local E2E path: `mesflow/runtime/tutorials/esp-kiosk/` through a test-only bind mount.

## MESFLOW PLAYBACK

- MESFlow version: `65.8.44.55`.
- MESFlow only reads `runtime/tutorials/esp-kiosk/manifest.json` and files under `videos/`; it contains no ESP tutorial generation path.
- Missing manifest returns an empty successful response and the UI displays: “Chưa có video hướng dẫn ESP Kiosk được publish.”
- Runtime manifest is loaded per request, so a tutorial publish does not require MESFlow restart.
- Full Playwright regression against the final Agent-published runtime: `7 passed`.
- The ESP tutorial test saw version `5.1.9.2`, seven cards, no technical filename in UI, no page error, a valid range response, and actual playback advancing `currentTime > 0`.

## CACHE

- Manifest/API response: `Cache-Control: no-cache, max-age=0, must-revalidate`.
- MP4 response: `Cache-Control: public, max-age=31536000, immutable`.
- Every manifest video URL includes `?v=5.1.9.2`. A new tutorial version therefore receives a distinct browser URL while unchanged video assets can be cached long-term.
- Browser assertions verified both the version query and cache headers.

## SERVER DEPENDENCIES NO LONGER NEEDED

For the ESP Kiosk tutorial pipeline, production no longer needs Playwright/browser images, FFmpeg, FFprobe, TTS/eSpeak/edge-tts, Pillow, Arduino CLI, ESP32 core, or firmware libraries. They remain local build dependencies only.

The Deploy Agent source still contains dormant legacy MESFlow web-tutorial builder implementation for compatibility/audit history, but its HTTP entry points are disabled. No package was uninstalled because other local/test functionality may still use Playwright or media tools.

## FILES CHANGED

### ESP Kiosk/local build

- `esp-kiosk/TUTORIAL_VERSION.txt`
- `esp-kiosk/tools/generate_tutorial_videos.py`
- `esp-kiosk/scripts/package-tutorial.sh`
- `esp-kiosk/scripts/build-tutorial-package.sh`
- `scripts/upload-kiosk-tutorial.sh`
- `artifacts/esp-kiosk/tutorial/manifest.json`
- `artifacts/esp-kiosk/tutorial/videos/*.mp4`
- `artifacts/esp-kiosk/packages/ESP_Kiosk_Tutorial_5_1_9_2.zip`
- `artifacts/esp-kiosk/packages/ESP_Kiosk_Tutorial_5_1_9_2.zip.sha256`

### Deploy Agent

- `deploy-agent/agent.py`
- `deploy-agent/templates/index.html`
- `deploy-agent/tests/test_esp_kiosk_tutorial_publish_v2150.py`
- version declarations/docs updated from `2.15.0` to `2.15.1`

### MESFlow

- `mesflow/app/mesflow/web/app.py`
- `mesflow/app/mesflow/web/static/app.js`
- `mesflow/tests/test_v6584454_esp_kiosk_tutorial.py`
- `mesflow/tests/e2e/mesflow.spec.js`
- MESFlow version declarations/tests updated from `65.8.44.54` to `65.8.44.55`

Existing unrelated uncommitted Session Exception changes were preserved.

## TESTS

- Required reconciliation: completed; `/opt` snapshots were older and no deployed source was imported.
- One-command full local generation/package: PASS.
- Immediate incremental rerun: PASS; videos reused.
- ZIP structure and SHA256: PASS.
- FFprobe seven video streams/resolution/zero audio: PASS.
- Deploy Agent focused tests: `2 passed`.
- Bad ZIP preservation: PASS.
- Authenticated Agent upload and atomic publish: PASS.
- Agent health after final image: PASS, `2.15.1-docker-runtime`.
- Server generation disabled endpoint: PASS, HTTP 410.
- MESFlow focused tests: `9 passed`.
- MESFlow full Playwright regression: `7 passed`.
- Python/JavaScript/shell syntax and Git diff whitespace checks: PASS.

## MIGRATION

NO. No database or schema change.

## PRODUCTION ACTION REQUIRED

YES, only after human review/approval:

1. Deploy MESFlow `65.8.44.55` and Deploy Agent `2.15.1-docker-runtime` through the approved release process.
2. Upload `ESP_Kiosk_Tutorial_5_1_9_2.zip` through the Agent’s ESP Kiosk tutorial card.
3. Verify the runtime tab and playback in production without restarting MESFlow.

No production action was performed in this task.
