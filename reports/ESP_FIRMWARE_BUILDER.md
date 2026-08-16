# ESP Firmware Builder

## RESULT

Implemented in Deploy Agent test runtime. The builder is local/test-only and does not flash USB or create an OTA job.

## Contract

```text
ESP source
  → Deploy Agent: Build firmware
  → esp-kiosk/scripts/build-ota-package.sh
  → Arduino CLI compile
  → artifacts/esp-kiosk/ota/ESP_Kiosk_<version>_OTA.zip
  → Agent registers artifact as READY
```

The source path is configured by `ESP_KIOSK_SOURCE_DIR`, defaulting to the current user's `~/workspace/mesflow/esp-kiosk`. The build command uses the approved `.mesflow-arduino.env`; it does not inspect a USB port or flash a board.

The promotion ZIP contains exactly:

```text
esp-kiosk-firmware/VERSION.txt
esp-kiosk-firmware/firmware.bin
esp-kiosk-firmware/manifest.json
esp-kiosk-firmware/SHA256SUMS
```

## Files changed

- `esp-kiosk/scripts/build-ota-package.sh`
- `deploy-agent/agent.py`
- `deploy-agent/templates/index.html`
- `deploy-agent/VERSION.txt`
- `deploy-agent/tests/test_docker_runtime_contract.py`
- `deploy-agent/tests/test_ota_package_upload.py`
- `docs/operations/OTA_CONTROL_PLANE.md`

## Status and errors

Builder states are `QUEUED`, `CHECKING`, `BUILDING`, `PACKAGING`, `SUCCESS`, and `FAILED`. The job stores a log tail and error code. A second build is rejected while one is running. A missing source is reported as `SOURCE_NOT_FOUND`; compile and package failures are not hidden as a successful artifact.

## Evidence

- Agent test runtime: `2.16.5-docker-runtime`
- Agent health after restart: `ok=true`
- Template parses successfully.
- Focused tests: `8 passed` (isolated test HOME).
- Python compile and shell syntax checks passed.
- The existing local firmware package `esp-kiosk/dist/esp-kiosk-5.5.7.ota.zip` remains available for upload.
- A direct build was intentionally blocked by existing local version policy (`VERSION_REUSE`) after CA was supplied; the script correctly refuses to silently rebuild the same release. Set a new source `FW_VERSION` for the next real builder run.

## Production action required

No production action. The test Agent was updated by a test-container runtime copy only; no production server, device, USB flash or OTA job was changed.
