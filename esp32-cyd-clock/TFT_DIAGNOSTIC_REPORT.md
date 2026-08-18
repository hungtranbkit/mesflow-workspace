# TFT Diagnostic Report — esp32-cyd-clock

Isolated TFT rendering-path investigation, per the explicit "do not
claim PASS from Serial alone" instruction. This firmware
(`tft_diagnostic/`) is Serial + TFT only — no WiFi/NTP/HTTPS/JSON/
weather/sprites/custom fonts/touch/SD/RGB in its rendering path. It now
**cycles continuously** (not once) so every stage becomes visible again
within about a minute regardless of when the board is checked.

## 1. Exact TFT library
`Adafruit_ILI9341` (on top of `Adafruit_GFX`).

## 2. Exact display driver
ILI9341.

## 3. Exact TFT SPI frequency
**Not applicable / no configurable value exists in this code path.**
The constructor used —
`Adafruit_ILI9341(cs, dc, mosi, sclk, rst, miso)` — is the
**software/bit-banged SPI** variant (individual GPIO pins, not a
`SPIClass*`). It does not go through the ESP32's hardware SPI
peripheral at all, so there is no MHz clock divider to report or tune
the way there would be for a hardware-SPI constructor. This is true in
both the known-good `hardware_test_cyd.ino` and the current clock
firmware — identical in both. (This is why Step 6, SPI-frequency
variation, isn't meaningfully testable as written without first
switching to a hardware-SPI constructor — noted, not done, since no
corruption has been physically confirmed yet to justify that change.)

## 4. TFT pins
CS=15, DC=2, MOSI=13, SCLK=14, MISO=12, RST=-1 (unwired, uses EN),
Backlight=21. Identical in both firmwares.

## 5. Known-good hardware-test display config
See `DISPLAY_INIT_DIFF.md` — full table. Summary: `Adafruit_ILI9341`,
software SPI, pins above, `tft.begin()` with no arguments,
`tft.setRotation(3)`, no color inversion set.

## 6. Current clock display config
Identical to (5) — see `DISPLAY_INIT_DIFF.md`.

## 7. Differences between them
**None.** Confirmed by direct diff of both files' TFT init sections.

## 8. Whether full-screen solid fills work
Serial confirms all 5 stages executed and logged
(`[TEST 1] BLACK` … `[TEST 5] BLUE`), each via a single
`tft.fillScreen()` call, nothing else. **Physical correctness on the
real panel is not claimed here — needs your visual confirmation.**

## 9. Whether rectangle/grid test works
Serial confirms it executed (`[GRID] Coordinate/address-window test
drawn`) — 4 colored 80×60 blocks, 4 corner blocks, 9 horizontal lines,
9 vertical lines, no text, no sprites. **Physical correctness not
claimed — needs your visual confirmation.**

## 10. Results of rotation 0/1/2/3

```
[ROTATION 0] W=240 H=320
[ROTATION 1] W=320 H=240
[ROTATION 2] W=240 H=320
[ROTATION 3] W=320 H=240
```

Standard, textbook ILI9341 rotation behavior — 0/2 portrait, 1/3
landscape, exactly swapping W/H with no odd values. **No anomaly in
the reported dimensions themselves.** Which rotation's border/corner
blocks actually look correct/clean on the physical panel is exactly
what needs your eyes — not decided here from these numbers alone.

## 11. Results at different SPI frequencies
**Not tested.** Step 6 is explicitly conditional on Step 3/4 showing
physical corruption, and per instruction I have not claimed corruption
exists without your confirmation — so this step is correctly deferred,
not skipped by oversight. Also see item 3: the current software-SPI
constructor has no frequency knob to turn without a bigger change
(switching to hardware SPI), which I have not done.

## 12. Why the previous font measurement could produce 364px height
**Root cause found and empirically proven** (not just theorized) via a
direct wrap=0 vs. wrap=1 comparison, same font, same sizes, same string
(`"00:00"`, `FreeSansBold24pt7b`, sizes 2–4):

```
wrap=0 size=2 measured=228x70    wrap=1 size=2 measured=228x70   (identical -- no wrap needed, fits in 320px)
wrap=0 size=3 measured=342x105   wrap=1 size=3 measured=264x273  (wrap=1 diverges hard)
wrap=0 size=4 measured=456x140   wrap=1 size=4 measured=240x364  (wrap=1 diverges hard)
```

With wrap disabled, height scales **perfectly linearly** with size —
70, 105, 140 — exactly 35px × size, matching the font's own glyph
metrics (`'0'` glyph: width=24 height=35 in `FreeSansBold24pt7b.h`'s
own glyph table). With wrap enabled (`Adafruit_GFX`'s **default**,
which the clock code never explicitly overrode), once the single-line
width at a given size would exceed the panel's physical width (320px —
`342` and `456` both exceed it), `getTextBounds()` simulates the same
line-wrapping `print()` would do, splitting the string across multiple
lines and reporting the resulting **multi-line** bounding box — taller
and narrower than the true single-line size. This is standard
`Adafruit_GFX` behavour interacting with a large custom font at a large
scale, **not** a driver bug, not a panel corruption issue, and not a
coordinate/geometry problem. The fix (for whenever adaptive sizing is
reinstated) is one line: `tft.setTextWrap(false)` before measuring or
drawing a single large line of text.

## 13. Whether simple built-in-font text renders correctly
Serial-measured bounds are exactly linear and sane for every sample
and size (no wrap-related ballooning at any size 1–3, as expected since
none of these strings are anywhere near 320px wide even at size 3):

```
"1234567890"  size1=60x8   size2=120x16  size3=180x24
"14:05"       size1=30x8   size2=60x16   size3=90x24
"ABCDEF"      size1=36x8   size2=72x16   size3=108x24
"Binh Phuoc"  size1=60x8   size2=120x16  size3=180x24
```

**Physical rendering correctness on the panel is not claimed here —
needs your visual confirmation**, same as items 8–10.

## What still needs your eyes

Per the explicit instruction: I am not writing "PASS" for any of the
above based on Serial output alone. The board is now running
`tft_diagnostic` **on a continuous cycle** (~50s per full pass:
4×3s rotations, 5×2s solid fills, grid test held 4s, built-in-font
text held 6s, then repeats). Please look at the physical screen and
tell me, for whichever stage(s) you can catch:

- Do the 5 solid-color fills look like clean, uniform full-screen
  color with no static/noise/wraparound/duplicated pixels anywhere,
  including the bottom of the screen?
- In the grid/rectangle test, are all 4 colored blocks, all 4 corner
  blocks, and all 18 grid lines exactly where they should be, with no
  unfilled/corrupted area?
- Across the 4 rotation tests, does any rotation show a border that
  doesn't reach all 4 physical edges of the panel, or corner blocks
  that land in the wrong place?
- Does the built-in-font text look clean (no garbled/missing glyphs)?

Not proceeding to Steps 6 (SPI frequency)/7 (driver re-verification)/
9 (adaptive sizing) or restoring the weather/clock application until
you've confirmed what's actually on the panel.
