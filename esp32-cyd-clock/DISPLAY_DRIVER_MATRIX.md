# Display Driver Matrix — ESP32-2432S028 (dual-USB CYD)

Goal: determine empirically whether `Adafruit_ILI9341` is the correct
controller/driver for THIS physical panel, or whether the visible
"compressed/near-square" active area is a driver/init-table mismatch
(e.g. this dual-USB board actually carrying an ST7789 panel instead of
ILI9341, per community reports cited in the task).

No conclusion in this document is based on Serial logs alone — the
acceptance rule is a physical full-screen fill/border/bar test, checked
by eye against all 4 physical edges of the panel.

## Current configuration (as used by esp32-cyd-clock and hardware_test_cyd)

| Field | Value |
|---|---|
| Library | Adafruit ILI9341 (v1.6.3), built on Adafruit GFX Library (v1.12.6) + Adafruit BusIO (v1.17.4) |
| Driver class | `Adafruit_ILI9341` (esp32-cyd-clock's screenshot build wraps it in a `ScreenshotILI9341` subclass that only intercepts draw calls for shadow-buffer mirroring — same underlying init/geometry code, not relevant to this test) |
| Constructor | `Adafruit_ILI9341(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST, TFT_MISO)` — the explicit-pin constructor, confirmed (Adafruit_SPITFT.cpp line 111) to select **software/bitbanged SPI**, not the ESP32 hardware SPI peripheral. This is a real, previously-undocumented characteristic: draw calls are all `digitalWrite()`-driven bit-banging, not clocked through the VSPI/HSPI peripheral. |
| TFT_CS | GPIO 15 |
| TFT_DC | GPIO 2 |
| TFT_RST | -1 (not wired; relies on EN/board reset) |
| TFT_MOSI | GPIO 13 |
| TFT_MISO | GPIO 12 (also the flash-voltage strapping pin — read-only use here) |
| TFT_SCLK | GPIO 14 |
| TFT_BL (backlight) | GPIO 21, driven HIGH in software (not tied to a PWM channel) |
| SPI frequency | `tft.begin()` called with no explicit freq → library default (`SPI_DEFAULT_FREQ`, platform macro, nominally 24-40MHz depending on target — moot for the bitbang path, which does not clock through a hardware SPI peripheral at a literal fixed frequency the way hardware SPI does) |
| MADCTL / rotation table | Adafruit's standard 4-value table: rotation 0 = `MADCTL_MX\|BGR` (portrait 240x320), rotation 1 = `MADCTL_MV\|BGR` (landscape 320x240), rotation 2 = `MADCTL_MY\|BGR` (portrait 240x320, 180° from 0), rotation 3 = `MADCTL_MX\|MADCTL_MY\|MADCTL_MV\|BGR` (landscape 320x240, 180° from 1). Only these 4 MX/MY/MV combinations are reachable via `setRotation()` — 4 of the 8 possible MADCTL axis-flip combinations are not exposed by this library's simple API. |
| Init command table | `Adafruit_ILI9341::begin()`'s hardcoded `initcmd[]` — an ILI9341-specific command sequence. If the physical panel is actually a different controller (e.g. ST7789), several of these commands are either no-ops, undefined, or map to different registers on that silicon — this is the leading hypothesis for a compressed/square-looking active region despite `tft.width()/height()` self-reporting 320x240. |

## Why this is suspect (per the task's cited community reports)

- ESP32-2432S028**R** (single-USB) commonly uses ILI9341.
- ESP32-2432S028 (dual-USB, this board) may use **ST7789** on some
  batches.
- `BOARD_INFO.md`'s existing "confirmed working" claim for ILI9341 on
  this exact board was based on **text/graphics being visible and the
  device not crashing** — never a full-edge-to-edge geometry test. That
  is exactly the kind of weak evidence this task's acceptance rule
  explicitly rejects ("Do not choose based on Serial logs alone").
  Text can render (position/scale wrong) even against a wrong
  controller, since drawChar()/print() just call drawPixel/fillRect
  repeatedly — a geometry test that stresses all 4 physical edges is a
  categorically stronger check than "some text was legible."

## Test matrix

| Test | Driver/Library | Sketch | Status |
|---|---|---|---|
| A | Adafruit_ILI9341 (current) | `display_test/test_a_ili9341/` | **built, flashed, currently running/cycling on the device** — awaiting physical confirmation |
| B | Adafruit_ST7789 (v1.11.0, installed this round) | `display_test/test_b_st7789/` | built, compiles clean — not yet flashed (device only has one board; flash after Test A is checked) |
| C | TFT_eSPI (v2.5.43, installed this round) + ST7789_DRIVER, custom compiler-define config | `display_test/test_c_tft_espi/` | built, compiles clean — not yet flashed |
| D (optional) | bb_spi_lcd (`DISPLAY_CYD_2USB`) | not started — only if A-C stay ambiguous | not started |

### Test B config detail

`Adafruit_ST7789(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST)` — same
bitbang-SPI constructor family as Test A, same 5 pins, so this isolates
the controller/init-table variable only. `tft.init(240, 320)` called
explicitly. Per the installed library source
(`Adafruit_ST7789.cpp::init()`), width=240/height=320 falls into the
generic "centered" branch: `_rowstart=_rowstart2=(320-320)/2=0`,
`_colstart=_colstart2=(240-240)/2=0` — **zero offset**, no manual
override needed for this exact panel size.

### Test C config detail

No pre-made CYD2USB/dual-USB config exists in the installed
TFT_eSPI@2.5.43 (`User_Setups/` searched, whole library tree grepped
for "dual", "2usb", "cyd" — no matches), so this is a from-scratch
config, built via `compiler.cpp.extra_flags` (not by editing the shared
library's `User_Setup.h`):

```
-DUSER_SETUP_LOADED=1 -DST7789_DRIVER=1 -DTFT_WIDTH=240 -DTFT_HEIGHT=320
-DTFT_MISO=12 -DTFT_MOSI=13 -DTFT_SCLK=14 -DTFT_CS=15 -DTFT_DC=2 -DTFT_RST=-1
-DSPI_FREQUENCY=27000000 -DSPI_READ_FREQUENCY=20000000
```

Same 5 physical pins as A/B. Unlike A/B, TFT_eSPI drives these through
the ESP32's real SPI peripheral (its whole design point), not
bitbanged — a second variable beyond just "which controller", noted
here rather than hidden. No column/row start offset override passed
(TFT_eSPI's ST7789 driver defaults to 0/0 for a 240x320 panel, same
reasoning as Test B).

Each test sketch is a separate, minimal `.ino`: no WiFi, no HTTP
server, no screenshot shadow framebuffer, no clock/weather app code, no
text, no custom font. Only solid fills, a 1px border, and full-span
vertical/horizontal bars, per the task's exact geometry spec.
