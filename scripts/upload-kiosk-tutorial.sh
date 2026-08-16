#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE="${1:-$(find "$ROOT/artifacts/esp-kiosk/packages" -maxdepth 1 -type f -name 'ESP_Kiosk_Tutorial_*.zip' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d ' ' -f2-)}"
[[ -n "$PACKAGE" && -f "$PACKAGE" ]] || { echo "Không tìm thấy tutorial ZIP. Hãy chạy esp-kiosk/scripts/build-tutorial-package.sh" >&2; exit 2; }
echo "Package sẵn sàng: $PACKAGE"
echo "SHA256: $PACKAGE.sha256"
echo "Hãy đăng nhập Deploy Agent và chọn 'Video hướng dẫn ESP Kiosk' → 'Upload & Publish'."
echo "Script không lưu hoặc yêu cầu mật khẩu Agent."
