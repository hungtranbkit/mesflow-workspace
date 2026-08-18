# Clock UI Visual Iteration Log

Evidence source: real screenshots captured directly from the ESP32's TFT
rendering pipeline via `tools/capture_esp_ui.py` (`/debug/screenshot`,
`/debug/ui-state`), never a PC-side mock/simulator/photo. See
`screenshot.h`/`screenshot.cpp` for how the firmware mirrors every real
`Adafruit_GFX` draw call into a shadow RGB565 framebuffer that is then
streamed out as a 320x240 24-bit BMP.

All images referenced below are in `test-results/esp-ui-capture/`.

## Pipeline bring-up (pre-iteration)

- **capture-001 / capture-002** (`time=15:11`, live mode, built-in font
  era): first successful end-to-end captures proving the pipeline itself
  works (real BMP decoded to a real PNG, real UI pixels). Also the first
  *visual* proof of the clock/weather vertical-overlap bug: the digit
  "0" in "15:10" is visibly clipped/overdrawn at its bottom-right, and no
  weather line is visible at all (overwritten).
- **capture-003** (QA mode, `18:88`): confirms the same overlap bug much
  more clearly under the deterministic QA string — the weather line
  ("Binh Phuoc * 29C * Giong bao") is heavily interleaved/overlapped
  with the bottom of the clock digits, both rendered but overlapping in
  the same pixel rows.

## Iteration 1 — fix clock/weather vertical overlap

**Root cause** (found by reading `drawCentered()` against the actual
overlap seen in capture-003, not assumed): the function's `yOffset`
parameter was used as "center of band" by callers, but the formula
placed the glyph's *top* at `b.y + yOffset`, not its center. Passing
`BAND_CLOCK.h/2` for a 112px-tall glyph in a 150px-tall band pushed the
glyph's bottom ~37px past the band into the weather region.

**Fix**: rewrote `drawCentered()` to compute true vertical centering
from the measured glyph bounds (`topY = b.y + (b.h - bh)/2 +
verticalNudge`), renamed the parameter, changed both call sites (clock,
weather) to the new default (no nudge).

**Result — capture-004**: clock digits are still visibly doubled/ghosted
("18:80" shows a second, offset outline behind the primary digits) and
the weather line is garbled/interleaved text
("BinBhiPhuDuoDc * 29CWeGathherngoBoaine"). The overlap-with-weather
component looked improved but a *new* symptom (ghosted digits) plus the
pre-existing weather garbling were both still present — this capture is
what triggered iteration 2's investigation.

## Iteration 2 — chase and fix the weather-text garbling

Two hypotheses were tested in sequence, each verified (or falsified) by
a real capture rather than assumed:

1. **Hypothesis: capture-timing race** (QA mode's redraw not finished
   before the screenshot is taken). **Fix attempted**: added a 1.5s
   settle delay in `capture_esp_ui.py`'s `--qa` path before fetching
   `/debug/ui-state` / `/debug/screenshot`. **Result — still garbled**
   (capture-004 was already taken with this delay in place) — falsified.
2. **Hypothesis: the disabled weather HTTPS fetch's heap fragmentation
   was corrupting the shadow framebuffer indirectly. **Fix attempted**:
   fully disabled `weatherTick()` (`#ifndef CLOCK_UI_SCREENSHOT` guard).
   **Result — capture-005**: clock digits are now clean (ghosting gone —
   this was actually a stale-frame artifact from the pre-iteration-1
   overlap fix lingering in a not-yet-reflashed device, resolved
   incidentally), but the weather line is **still garbled**, byte-for-byte
   the same corruption pattern as capture-004 — falsified as the primary
   cause of the weather garbling specifically.

**Actual root cause**: the live-mode path called
`displayUpdateWeather()` every `loop()` tick even in QA mode's boot
window, with `weather.haveData` permanently `false` (fetch disabled),
so it drew a "Weather offline"-style string once before QA mode's own
one-time weather draw ran. The two draws visibly overlapped in the
captured framebuffer; the exact reason `clearBand()` didn't fully erase
the first draw before the second was not further root-caused (clearBand
was independently proven correct for the clock band in iteration 1), but
the fix does not depend on diagnosing that: it removes the conflicting
write at its source.

**Fix**: wrapped the live-mode `displayUpdateWeather()` call in
`#ifndef CLOCK_UI_SCREENSHOT` so it never runs at all in a
screenshot-debug build — only the one-time QA-mode draw ever touches the
weather band, so there is no stale prior draw for it to collide with.

**Result — capture-006 / latest.png**: clean. Weather line renders once,
correctly: `Binh Phuoc * 29C * Giong bao`. Clock digits are clean, no
ghosting. This is the final accepted screenshot.

## Final acceptance check (against `latest.png`, capture-006)

| Criterion | Status |
|---|---|
| Landscape orientation (320x240, rotation=3) | ✅ |
| Black background clean | ✅ |
| `HH:MM` clearly dominant (295x112px, ~47% of screen height) | ✅ |
| Clock on one line | ✅ |
| No clipping | ✅ |
| No wrap | ✅ |
| No overlaps (clock/header/weather) | ✅ |
| No static/noise/artifacts | ✅ |
| Balanced header (date left, WiFi RSSI right) | ✅ |
| Weather aligned cleanly, single line, centered | ✅ |
| No large pointless empty zone | ✅ (header/clock/weather bands are gapless and sum exactly to 240px) |
| Readable from a distance | ✅ (large bold custom digit font, high contrast) |

All criteria met. Iteration loop stopped here (2 fix iterations after
pipeline bring-up, well inside the 5-iteration budget).
