# Display Init Diff — esp32-cyd-clock vs. known-good hardware_test_cyd

Known-good reference: `esp-kiosk/esp/hardware_test_cyd/hardware_test_cyd.ino`
(physically confirmed on the real board: TFT displayed correctly, text
and graphics visible, orientation later corrected to rotation 3).

## Comparison

| Item | Known-good (`hardware_test_cyd.ino`) | Current (`esp32-cyd-clock/display.cpp`) | Same? |
|---|---|---|---|
| Library | `Adafruit_ILI9341` | `Adafruit_ILI9341` | YES |
| Driver | ILI9341 | ILI9341 | YES |
| TFT_CS | 15 | 15 | YES |
| TFT_DC | 2 | 2 | YES |
| TFT_MOSI | 13 | 13 | YES |
| TFT_SCLK | 14 | 14 | YES |
| TFT_MISO | 12 | 12 | YES |
| TFT_RST | -1 | -1 | YES |
| TFT_BL | 21 | 21 | YES |
| Constructor | `Adafruit_ILI9341(CS,DC,MOSI,SCLK,RST,MISO)` — software SPI, individual pins | identical | YES |
| SPI mode | not set (library default for its software-SPI path) | not set (same) | YES |
| SPI frequency | not set — this constructor uses a **software/bit-banged SPI** implementation, not the hardware SPI peripheral, so there is no configurable MHz clock the way a hardware-SPI constructor would have; toggle speed is whatever `Adafruit_SPITFT`'s software-SPI path does internally | not set (same) | YES |
| `tft.begin()` | called with no arguments (default init sequence) | same | YES |
| Color inversion | not set anywhere | not set anywhere | YES |
| `tft.setRotation()` | `3` | `3` | YES |
| Width/height source | library defaults (240×320 native ILI9341, rotation applied) — never explicitly overridden | same, but now also **read back** via `tft.width()`/`tft.height()` after `setRotation()` (added this round, does not change how they're computed, only reads them) | Effectively YES (added a read, not a different config) |

## Conclusion

**No difference found.** The TFT initialization path in `esp32-cyd-clock`
is byte-for-byte identical to the known-good `hardware_test_cyd.ino` —
same library, same driver, same pins, same constructor variant, same
`begin()` call, same rotation, no inversion set in either. This was
verified again live: the runtime log confirms `rotation=3 width=320
height=240`, matching what `hardware_test_cyd.ino` also produces on
this exact panel.

Given this, the TFT init sequence itself is **not implicated** by this
diff. Any remaining rendering problem is somewhere else — in how content
is drawn (fonts/text bounds/coordinates) after init, not in how the
panel is initialized. This narrows, but does not by itself prove,
where the actual bug is — see `TFT_DIAGNOSTIC_REPORT.md` for the
isolated physical tests.
