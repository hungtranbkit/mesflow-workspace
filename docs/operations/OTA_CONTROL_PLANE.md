# ESP OTA — vận hành tối giản

## Release và flash

```bash
cd esp-kiosk
./scripts/build-ota.sh
```

 Kết quả là `dist/esp-kiosk-<version>.ota.zip`. ZIP chứa binary OTA và manifest version/build/hardware. Mở Deploy Agent → **ESP OTA**, chọn ZIP, chọn một hoặc nhiều kiosk đang Online, rồi bấm **FLASH OTA**. Không nhập lại version, SHA256 hoặc hardware.

Agent tự tính size/SHA256, kiểm tra `.bin`, kích thước partition, hardware và không cho chạy hai job trên một kiosk. Theo dõi từng kiosk ngay trên cùng trang: `PENDING`, `DOWNLOADING`, `FLASHING`, `REBOOTING`, `SUCCESS` hoặc `FAILED`.

Không còn các bước Draft, Activate, Publish, Stage, Canary, Health Gate, Maintenance Window hay Approval.

## Troubleshooting

- `DEVICE_OFFLINE`: chọn lại khi kiosk Online.
- `WRONG_HARDWARE`: firmware và kiosk không cùng model.
- `FIRMWARE_TOO_LARGE`: kiểm tra partition/asset trước khi build.
- `SHA_MISMATCH` hoặc `FLASH_FAILED`: giữ kiosk qua USB recovery.
- CA được lấy tự động từ `MESFLOW_OTA_CA_FILE` hoặc `~/.config/mesflow/esp-kiosk/root-ca.pem` khi build; không truyền Arduino flags thủ công.

USB recovery vẫn dùng:

```bash
./scripts/flash.sh /dev/ttyACM0
```
