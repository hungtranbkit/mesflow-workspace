# Screenshot capture -- disabled (Adafruit_ILI9341-era code)

`screenshot.h`/`screenshot.cpp` implemented `/debug/screenshot` +
`/debug/ui-state` by subclassing `Adafruit_ILI9341` and overriding its
Adafruit_GFX virtual draw hooks (`drawPixel`/`writeFillRect`/...) to
mirror every draw call into a shadow RGB565 framebuffer, streamed back
as a BMP over HTTP.

**Disabled since the 2026-08-17 TFT_eSPI/ST7789 migration** (see
`BOARD_INFO.md`, `../display.h`): TFT_eSPI is a different class
hierarchy with no equivalent virtual hook to intercept without a much
larger, riskier change than this migration's scope allowed. Physical
display correctness took priority, per instruction.

Moved out of the sketch root (not just `#ifdef`'d out) so Arduino's
sketch compiler doesn't pick these files up automatically -- Arduino
compiles every `.cpp` directly in the sketch folder regardless of
whether anything includes it. Kept here, unused, as a reference for a
possible future TFT_eSPI-native reimplementation (e.g. wrapping
`tft.pushImage()`/`readRect()` if the panel ever supports readback, or
maintaining a shadow buffer via a thin wrapper around TFT_eSPI's own
draw calls instead of virtual-hook interception).
