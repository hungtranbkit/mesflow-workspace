# ESP Kiosk Tutorial Video Report

Generated: 2026-08-12 (Asia/Bangkok)

## Result

**PASS.** All seven tutorials were regenerated from a fresh framebuffer capture taken from the connected ESP running the current workspace firmware. None of the prior MP4 or prior capture PNG files was used as video input.

## Source provenance

- Old video firmware: `ESP32-KIOSK-5.1.9-WORKER-QTY-FLOW`
- Current source firmware: `ESP32-KIOSK-5.1.9-WORKER-QTY-FLOW`
- Source commit: `a1827e3729db84328c06322309f7a4bab4750695`
- Source: `esp-kiosk/esp/esp.ino`, `mesflow_app.cpp`, `mesflow_app.h`, and current generated Vietnamese font header.
- The version number is unchanged, but provenance is verified independently: workspace constant, current Git HEAD, successful compile, and live `/api/device/health` all report the same firmware.
- Live device: ESP32-S3 N16R8 / ES3C28P profile, `192.168.1.115:17892`, health 100, LCD ILI9341 ready, keypad and scanner ready.
- Fresh capture: `esp-kiosk/test-results/esp-ui-capture-20260812_123901/`, captured 2026-08-12 at 12:40 local.
- Old output backup: `artifacts/esp-kiosk/tutorial-backup-20260812_124102/`.

## Current firmware UI review

The rendered production flow is:

1. `BOOT` → `WIFI` → `BINDING` → `READY`.
2. Employee QR enters `LOOKUP_WORKER`; success renders `WORKER_OK` with `* HỦY`.
3. Operation QR enters `LOOKUP_OPERATION` and `OPERATION_OK` with `* QUAY LẠI / # BẮT ĐẦU`.
4. Successful start renders `START_SUCCESS` for 10 seconds, then returns the shared kiosk to `READY` while the MESFlow Session remains open.
5. Scanning an employee with an open Session enters `INPUT_GOOD`, then `INPUT_DEFECT`.
6. If defect is zero, firmware skips repairable input and enters `CONFIRM_QTY`.
7. If defect is nonzero, `ASK_REWORK` offers `1 KHÔNG, XONG` or `2 CÓ, NHẬP SỐ`; option two enters `INPUT_REWORK`.
8. `CONFIRM_QTY` uses `* QUAY LẠI / # XÁC NHẬN`; successful finish renders `FINISH_SUCCESS` and returns to `READY`.
9. Quantity screens idle-timeout after 120 seconds; confirmation/retry after 60 seconds. UI is released without silently finishing the server Session.
10. `ERROR_STATE` supports `* QUAY LẠI`; invalid raw scanner frames are dropped. `OFFLINE`, durable pending transactions, offline-save/storage-warning, reconnect, and maintenance sync are represented by current renderer states.

LCD frames are 240×320 and retain current source text, font, spacing, footer labels and layout. Tutorial overlay is outside the LCD frame and uses a short state-specific instruction.

## Build

- Arduino CLI: available.
- ESP32 core/profile: current configured production profile.
- FQBN: `esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=default_8MB,PSRAM=opi`.
- Multi-file sketch compiled as directory `esp/`; no `.ino` file was extracted.
- Result: **PASS**.
- Program storage: 1,361,367 bytes, 40% of 3,342,336 bytes.
- Globals: 71,148 bytes, 21% of 327,680 bytes; 256,532 bytes remain for locals.

## Flash

Not performed and not required. The connected device already reports the exact current source version and exposes the fresh framebuffer renderer. No partition, pin, flash or runtime configuration was changed.

## Framebuffer regeneration

`capture_esp_ui.py` queried the current device's `/debug/screens`, rendered each state with `/debug/show-screen`, then downloaded `/debug/screenshot` and `/debug/ui-state` anew.

- 33 states advertised by current firmware.
- 26/33 passed the capture tool's strict unique-pixel check.
- One optional `confirm_normal` request timed out; `confirm_qty` captured successfully and is used.
- Six offline variants intentionally rendered pixels identical to their online counterpart while reporting a distinct debug state. These were freshly captured but correctly reported as duplicate-pixel validation failures. Main `offline`, `offline_saved`, `storage_warning`, and `maintenance` screens passed and are used.

## Generator changes

- Requires an explicit fresh `--capture-dir`; it no longer points at the old capture directory.
- Reads `APP_VERSION` from current firmware source.
- Rejects missing screens or capture/source version mismatch.
- Uses metadata state from each fresh capture.
- Uses short, wrapped Vietnamese overlays and state-specific key instructions.
- Removes eSpeak/TTS and all audio generation/muxing.
- Manifest records source commit, capture directory, method, `audio: false`, video list and covered cases.

## Videos regenerated

| File | Duration | Resolution | Video | Audio streams |
|---|---:|---|---:|---:|
| `00_kiosk_overview.mp4` | 17 s | 1280×720 | 1 | 0 |
| `01_kiosk_boot_connect.mp4` | 13 s | 1280×720 | 1 | 0 |
| `02_kiosk_start_session.mp4` | 16 s | 1280×720 | 1 | 0 |
| `03_kiosk_finish_good_qty.mp4` | 17 s | 1280×720 | 1 | 0 |
| `04_kiosk_defect_rework.mp4` | 22 s | 1280×720 | 1 | 0 |
| `05_kiosk_common_errors.mp4` | 16 s | 1280×720 | 1 | 0 |
| `06_kiosk_offline_reconnect.mp4` | 21 s | 1280×720 | 1 | 0 |

Each simple state holds four seconds; detailed states hold five seconds. SHA-256 comparison confirms every regenerated MP4 differs from its backed-up predecessor.

## Validation

- All seven files exist and have positive duration.
- Each has one valid H.264 video stream at 1280×720, 25 fps.
- **Audio streams = 0 for all seven files.**
- Manifest JSON parsed and contains all seven videos and cases A–K.
- A frame was extracted from every final MP4 and reviewed against its fresh capture/current renderer.
- Visual review found and fixed an initial clipped long overlay and generic key labels before final regeneration.
- Final validation frames: `esp-kiosk/test-results/tutorial-video-validation-20260812_124221/`.

## Database and production safety

- Database changed: **NO**.
- Backend demo data created: **NO**.
- MESFlow restarted/deployed: **NO**.
- ESP flashed: **NO**.
- Production action required: **NO**.

## Known limitations

- The debug error fixture uses a representative current firmware business-error message. The overlay explains operation-before-employee and malformed-QR behavior from `handleSerialLine()`/scanner parsing; it is not presented as a literal live reproduction of those exact input payloads.
- Boot is represented by the current connect/offline/ready renderer states; no camera recording of the physical power-on transition was made.
- Offline duplicate-state pixels are a limitation of the current debug renderer and are explicitly reported rather than hidden.
