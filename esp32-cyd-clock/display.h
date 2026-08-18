// esp32-cyd-clock -- display layer.
//
// MIGRATED 2026-08-17 from Adafruit_ILI9341 to TFT_eSPI/ST7789 -- see
// BOARD_INFO.md and DISPLAY_DRIVER_MATRIX.md for why: the old ILI9341
// stack physically showed a compressed/near-square active region on
// this dual-USB board's real ST7789 panel, confirmed by a full-edge
// border/quadrant/strip test (display_test/), not just Serial logs.
// TFT_eSPI + ST7789_DRIVER was physically verified to fill the
// complete 320x240 landscape panel correctly.
//
// Screenshot/debug capture (/debug/screenshot etc.) is DISABLED in
// this migration. The old approach subclassed Adafruit_GFX's virtual
// draw hooks (drawPixel/writeFillRect/...) to mirror every draw call
// into a shadow framebuffer; TFT_eSPI is a different class hierarchy
// with no equivalent hook to intercept without a much larger, riskier
// change. Physical display correctness took priority, per instruction.
// screenshot.h/.cpp are left in the repo, unused, for a possible
// future TFT_eSPI-native reimplementation -- not deleted, not wired in.
//
// Build note: TFT_eSPI is configured entirely via compiler defines
// (compiler.cpp.extra_flags), not the shared library's User_Setup.h --
// see build_and_flash.sh in this project's root and BOARD_INFO.md for
// the exact flags. Building with plain `arduino-cli compile` (no
// --build-property) will use TFT_eSPI's own default User_Setup.h,
// which does NOT match this board -- use build_and_flash.sh.

#pragma once
#include <TFT_eSPI.h>

void displayInit();
void displayUpdateHeader(const String &dayOfWeekVN, const String &dateStr, long rssi, bool wifiConnected);
void displayUpdateTime(int hour24, int minute);
void displayUpdateWeather(const String &locationName, float tempC, const String &condition, bool haveWeather, bool stale);

// ---- Alarm overlay (alarm.cpp) -- shows/hides a full-screen "HH:MM /
// ALARM" overlay without permanently altering the normal clock UI.
// displayHideAlarmOverlay() also invalidates this file's own
// change-tracking so the very next displayUpdate*() calls repaint
// everything fresh (no stale pixels left from the overlay). ----
void displayShowAlarmOverlay(int hour, int minute);
void displayHideAlarmOverlay();

// ---- Accessors for screenshot.cpp (TFT_eSPI-native readRect capture,
// no shadow buffer -- see screenshot.h). ----
int displayWidth();
int displayHeight();
void displayReadRow(int32_t y, uint16_t *outRow, int32_t w); // reads one real row back from the panel via tft.readRect()
