# OTA ZIP workflow

## Result

The operator flow is now:

```text
cd esp-kiosk
./scripts/build-ota.sh
Deploy Agent → ESP OTA → choose .ota.zip → select online kiosk(s) → FLASH OTA
```

`build-ota.sh` creates `dist/esp-kiosk-<version>.ota.zip`. The ZIP contains exactly:

- `esp-kiosk-<version>.bin`
- `esp-kiosk-<version>.manifest.json`

The manifest carries version, build, hardware model, size and the local SHA256. The Agent reads version/build/hardware from the manifest; the operator does not enter them again. The Agent calculates SHA256 and size from the binary server-side.

## Safety retained

The workflow is simpler, but the checks that protect a kiosk remain: ZIP structure, non-empty binary, merged-image rejection, OTA-size limit, server-side SHA256, hardware compatibility, online-device requirement and one active OTA per kiosk. These are safety checks, not lifecycle steps such as draft/activate/stage/approval.

The old `.bin` API form remains only as a backward-compatible API path; the Deploy Agent UI accepts ZIP packages and does not expose version or hardware inputs.

## Evidence

- Local firmware package: `esp-kiosk/dist/esp-kiosk-5.5.7.ota.zip`
- Package contents: one `.bin` plus one `.manifest.json`
- Agent test runtime: `2.16.4-docker-runtime`
- Test Agent page accepts `.zip` and has no version/hardware form fields
- Tests: `8 passed`; Python compilation passed
- No production system was mutated.
