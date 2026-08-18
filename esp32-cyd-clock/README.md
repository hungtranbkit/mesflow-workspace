# esp32-cyd-clock

A simple, always-on desk clock for the ESP32-2432S028 (CYD) dual-USB
board. **Independent project** — does not modify or depend on the
MESFlow kiosk firmware in `esp-kiosk/`.

## Board

ESP32-2432S028, dual-USB variant. Classic ESP32-D0WD-V3, 4MB flash, no
PSRAM. See `BOARD_INFO.md` for the verified pin map (TFT reused
verbatim from `esp-kiosk`'s hardware-test firmware — not re-derived
here).

## Project structure

```
esp32-cyd-clock/
├── README.md
├── BOARD_INFO.md
├── VERSION
├── config.example.h        # template, committed
├── config.h                 # real dev config, gitignored (has a WiFi password)
├── esp32-cyd-clock.ino      # setup()/loop(), the Arduino sketch entry point
├── display.h / display.cpp  # TFT layout + flicker-free partial redraw
└── weather.h / weather.cpp  # Open-Meteo fetch (no API key)
```

Note on structure: the task's suggested tree used a `src/main.cpp`
layout. Arduino CLI (the toolchain already set up and used for the
`esp-kiosk` hardware-test firmware) requires the primary sketch file to
be a `.ino` sitting directly in a folder of the same name, with
sibling `.cpp`/`.h` files in that same folder — the same flat layout
`esp-kiosk/esp/hardware_test_cyd/` already uses. Kept consistent with
that proven, already-working pattern instead of forcing an incompatible
PlatformIO-style tree onto Arduino CLI.

## Build command

Run from this directory:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 --output-dir build_output .
```

## Flash command

```bash
esptool --chip esp32 --port /dev/ttyUSB0 --baud 460800 write-flash -z \
  --flash-mode dio --flash-freq 40m --flash-size 4MB \
  0x1000  build_output/esp32-cyd-clock.ino.bootloader.bin \
  0x8000  build_output/esp32-cyd-clock.ino.partitions.bin \
  0x10000 build_output/esp32-cyd-clock.ino.bin
```

(`esptool` here is the copy bundled with Arduino CLI's esp32 core:
`~/.arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool` on the
machine this was built on.)

## Serial monitor command

```bash
python3 -c "
import serial, time
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
while True:
    data = ser.read(4096)
    if data: print(data.decode('utf-8', errors='replace'), end='')
"
```

## WiFi configuration

Copy `config.example.h` to `config.h` and fill in real values.
**Current `config.h` uses a TEMPORARY DEVELOPMENT WIFI** (`Airport` /
test password) for V0.1 bring-up only — see "Known limitations" below.
Never commit real production WiFi credentials; `config.h` is gitignored.

## Weather source

[Open-Meteo](https://open-meteo.com/) `forecast` endpoint — free, no
API key required. Fetches `temperature_2m`, `relative_humidity_2m`,
`weather_code` (WMO code, mapped to a short ASCII condition label) for
a fixed lat/lon (`config.h`, default: Binh Phuoc / Dong Xoai,
11.536, 106.919). Refreshes every 15 minutes (`WEATHER_REFRESH_MS`);
on any fetch failure the last known reading is kept and shown, with a
"(stale)" note once it's older than 1 hour (`WEATHER_STALE_MS`).

## Timezone

`ICT-7` (POSIX TZ string, fixed UTC+7, Vietnam has no DST) via
`configTzTime()` — standard ESP32 Arduino core timezone support, no
manual hour-offset arithmetic.

## Known limitations (V0.1)

- WiFi credentials are hardcoded in `config.h` (temporary dev AP) — a
  real WiFi-setup UI (captive portal or keypad-based entry, once the
  keypad connector work lands in `esp-kiosk`) replaces this later.
- Vietnamese day-of-week/location labels are plain ASCII (`THU HAI`,
  `BINH PHUOC`-style, no diacritics) — the built-in Adafruit_GFX fonts
  used here don't render Vietnamese Unicode. A proper diacritic-capable
  font is a reasonable V0.2 addition; deliberately skipped for V0.1 to
  keep this first version small, simple, and stable rather than porting
  a new font asset from scratch.
- No touch, no keypad, no GM65, no microSD, no MQTT/Bluetooth/web
  server/OTA/captive portal — see the task's own explicit "not in V0.1"
  list. This is a clock only.
- `WiFiClientSecure::setInsecure()` is used for the HTTPS weather
  request (skips certificate validation) — a deliberate simplification
  for a public, non-sensitive, read-only endpoint; revisit if this
  firmware ever handles anything sensitive.
