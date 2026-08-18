# Board Info — esp32-cyd-clock

Self-contained copy of the verified hardware facts this project needs.
The original, more detailed investigation (connector pinout, GM65/PCF8574
research, etc.) lives in the separate `esp-kiosk` project's
`BOARD_INFO.md` — this project does not depend on that file or that
project; only the facts actually used here are restated below.

## Identity (verified via esptool, `dell-Latitude-5511`, 2026-08-17)

| Field | Value |
|---|---|
| Board | ESP32-2432S028, dual-USB (USB-C + micro-USB) variant |
| Chip | ESP32-D0WD-V3 (revision v3.1) — classic ESP32 |
| Cores | 2, 240MHz |
| Flash | 4MB |
| PSRAM | 0 bytes (none) |
| MAC | `8C:94:DF:4D:54:28` |
| USB-serial bridge | CH340 on the **micro-USB** port (`1a86:7523`) |

## TFT — display stack (updated 2026-08-17, physically re-verified)

**The `Adafruit_ILI9341` stack below (reused from
`esp-kiosk/esp/hardware_test_cyd/hardware_test_cyd.ino`) is DEPRECATED
for this board revision.** It was only ever confirmed by "text/graphics
visible, no crashes" — never a full-edge-to-edge physical geometry
test. When actually tested with a full-screen border/quadrant/edge-strip
pattern (`display_test/`, see `DISPLAY_DRIVER_MATRIX.md`), the physical
panel showed a compressed/near-square active region under ILI9341,
consistent with community reports that this dual-USB
ESP32-2432S028 variant carries an **ST7789** controller, not ILI9341.

**Preferred stack, physically verified 2026-08-17** (border/quadrant/
edge-strip pattern reaches all 4 physical edges, no crop/wrap/mirror):

| Field | Value |
|---|---|
| Display controller | **ST7789** |
| Preferred library | **TFT_eSPI** (v2.5.43) |
| Driver | `ST7789_DRIVER` |
| Native resolution | 240×320 (portrait) |
| Landscape resolution | 320×240 |
| Rotation | `tft.setRotation(1)` — physically verified correct (right-side-up, full landscape) |
| SPI | Hardware SPI (ESP32 SPI peripheral, not bitbang), **20 MHz**, verified stable |
| Column/row start offset | none (0/0) — this is a native 240×320 panel, not a 240×240 or other odd-size ST7789 module that would need one |

| Signal | GPIO |
|---|---|
| MOSI | 13 |
| MISO | 12 |
| SCLK | 14 |
| CS | 15 |
| DC | 2 |
| RST | -1 (not wired; uses EN/board reset) |
| Backlight | 21 |

**TFT_eSPI compile configuration**: no pre-made CYD2USB/dual-USB config
exists in the installed TFT_eSPI@2.5.43 (searched, no match) —
configured entirely via `compiler.cpp.extra_flags` (not by editing the
shared library's `User_Setup.h`), which relies on
`User_Setup_Select.h`'s `#ifndef USER_SETUP_LOADED` guard:

```
-DUSER_SETUP_LOADED=1 -DST7789_DRIVER=1 -DTFT_WIDTH=240 -DTFT_HEIGHT=320
-DTFT_MISO=12 -DTFT_MOSI=13 -DTFT_SCLK=14 -DTFT_CS=15 -DTFT_DC=2 -DTFT_RST=-1
-DSPI_FREQUENCY=20000000 -DSPI_READ_FREQUENCY=20000000
-DLOAD_GLCD -DLOAD_FONT2 -DLOAD_FONT4 -DLOAD_FONT6 -DLOAD_FONT7 -DLOAD_FONT8
```

Reference firmware: `display_known_good/` (build via its own
`build_and_flash.sh`) — the exact minimal firmware physically verified
to fill the complete panel. Do not delete it. Full A/B/C driver
comparison evidence: `DISPLAY_DRIVER_MATRIX.md`, `display_test/`.

### Old ILI9341 configuration (deprecated for this board revision, kept for reference)

Controller: ILI9341, 320×240, software SPI (`Adafruit_ILI9341`
constructor with individual pins, not the default hardware-SPI pin set).
Same 6 pins as above. `tft.setRotation(3)`. This was the original
`esp32-cyd-clock`/`hardware_test_cyd.ino` stack; superseded 2026-08-17
per the physical verification above. `esp-kiosk`'s kiosk firmware still
uses this stack and is unaffected by this change (separate project).

## Not used by this project

Touch (XPT2046), microSD, RGB LED, GM65 UART, PCF8574 I2C keypad — none
of these are touched by `esp32-cyd-clock` V0.1. See `esp-kiosk`'s own
`BOARD_INFO.md` if/when a future version of this clock needs them.
