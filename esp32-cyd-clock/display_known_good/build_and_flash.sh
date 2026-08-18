#!/bin/bash
# Test C build -- TFT_eSPI configured entirely via compiler defines
# (compiler.cpp.extra_flags), not by editing the shared installed
# library's User_Setup.h. See the .ino header comment for why.
#
# Usage: ./build_and_flash.sh [--flash]
set -euo pipefail
cd "$(dirname "$0")"

EXTRA_FLAGS="-DUSER_SETUP_LOADED=1 -DST7789_DRIVER=1 -DTFT_WIDTH=240 -DTFT_HEIGHT=320 \
-DTFT_MISO=12 -DTFT_MOSI=13 -DTFT_SCLK=14 -DTFT_CS=15 -DTFT_DC=2 -DTFT_RST=-1 \
-DSPI_FREQUENCY=20000000 -DSPI_READ_FREQUENCY=20000000"

arduino-cli compile --fqbn esp32:esp32:esp32 --warnings default \
  --build-property "compiler.cpp.extra_flags=${EXTRA_FLAGS}" \
  --output-dir build_output .

if [[ "${1:-}" == "--flash" ]]; then
  ESPTOOL=/home/dell/.arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool
  "$ESPTOOL" --chip esp32 --port /dev/ttyUSB0 --baud 460800 write-flash -z \
    --flash-mode dio --flash-freq 40m --flash-size 4MB \
    0x1000 build_output/display_known_good.ino.bootloader.bin \
    0x8000 build_output/display_known_good.ino.partitions.bin \
    0x10000 build_output/display_known_good.ino.bin
fi
