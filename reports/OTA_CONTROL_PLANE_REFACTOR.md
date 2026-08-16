# OTA tối giản — kết quả refactor

## Flow mới

```text
./scripts/build-ota.sh
Deploy Agent → ESP OTA → Upload .bin → chọn kiosk → FLASH OTA
```

Deploy Agent là control plane duy nhất. MESFlow không còn đăng ký OTA firmware/deployment UI hoặc API mutation; chỉ còn internal kiosk inventory contract để Agent lấy danh sách thiết bị.

## Đã thay đổi

- Thay Agent OTA store bằng ba nhóm dữ liệu nhỏ: `ota_firmware`, `ota_jobs`, `ota_job_devices` và event tối thiểu.
- Upload + tạo job trong một request `POST /api/esp-ota/upload`.
- Thêm `GET /api/esp-ota/devices`, `GET /api/esp-ota/jobs`, `GET /api/esp-ota/status/<job_id>`.
- ESP dùng `/api/esp-ota/check`, `/api/esp-ota/file/<id>`, `/api/esp-ota/event`.
- Xóa Agent lifecycle action Draft/Activate/Disable, deployment strategy, stages, rollout policy và các route tương ứng.
- Xóa MESFlow OTA blueprint, UI page/script, reconciliation hook và test riêng cho staged OTA. Migration 0027–0029 đã từng phát hành nên được giữ nguyên lịch sử schema, nhưng application không còn dùng chúng.
- Xóa các script `publish-ota.sh`, `release-ota.sh`, `ota-doctor.sh`, `setup-ota-env.sh`; chỉ còn `build-ota.sh` và USB `flash.sh`.
- Firmware build mới: `5.3.3`, build `20260812.2000`, binary `esp-kiosk/dist/esp-kiosk-5.3.3.bin`, size `1,373,808`, SHA256 `57343c043379181ed95a88b250593a22e0883e2789018f87a3bd7cf378199fde`.

## Evidence

- Agent module smoke: upload, online-device selection, job creation, check, event `OTA_HEALTHCHECK_OK` → `SUCCESS`: PASS.
- Production Test deployment: Deploy Agent `2.16.0-docker-runtime` and MESFlow `65.8.44.63` deployed through the test Agent; health/version verified.
- ESP OTA contract tests: 5 passed.
- ESP OTA build: PASS; 41% app partition, 22% RAM.
- Merged image rejection remains enforced.
- USB flash script remains explicit-port and compile-before-upload.

## Acceptance

```text
Single OTA page: PASS
Upload + Flash flow: PASS
Draft/Activate removed: YES
Stage/Canary removed: YES
Health Gate removed: YES
Maintenance Window removed: YES
Complex deployment workflow removed: YES
Unused backend code removed: PARTIAL (released MESFlow migrations retained)
Unused frontend code removed: PASS
Unused tests/docs removed: PASS for replaced OTA workflow
Merged binary blocked: PASS
SHA automatic: PASS
Multi-device simple flash: PASS
USB recovery preserved: PASS
MESFlow no longer OTA control plane: PASS
Production mutated: NO
```

The built firmware uses the local test CA in this workspace build. Rebuild with the real Agent CA before Internet OTA; no production device was flashed.
