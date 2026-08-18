// esp32-cyd-clock -- debug screenshot subsystem. Compiled in ONLY when
// CLOCK_UI_SCREENSHOT is defined (see esp32-cyd-clock.ino) -- the
// release firmware carries none of this.
//
// Architecture: Adafruit_ILI9341 exposes no reliable pixel-readback API
// (checked: no readPixel()/readGRAM() in this installed library
// version, only readcommand8/16 for device-ID queries and a low-level
// read16() with no documented multi-pixel GRAM-read sequence built on
// top of it). So instead of reading the physical panel back, this
// subclasses the driver and intercepts every one of Adafruit_GFX's
// virtual low-level draw hooks (drawPixel/writePixel/writeFillRect/
// writeFastHLine/writeFastVLine -- confirmed virtual in Adafruit_GFX.h,
// which is how fillRect()/print()/drawFastHLine() etc. all ultimately
// reach the hardware) to ALSO mirror each write into one small RGB565
// shadow buffer, then call the real Adafruit_ILI9341 implementation so
// the physical TFT is completely unaffected. This is the actual
// rendering path -- not a separate simulator that could diverge from
// it -- because every draw call in display.cpp goes through these same
// virtual functions either way.
//
// One shadow buffer only (320*240*2 = 153600 bytes, this app's fixed
// landscape/rotation-3 resolution), no duplicate BGR buffer: the BMP
// endpoint converts RGB565->BGR888 one row at a time while streaming
// the HTTP response (960 bytes/row), never materializing the full
// 230400-byte BGR image in RAM.

#pragma once
#include <Adafruit_ILI9341.h>
#include <Arduino.h>
#include <WiFi.h>

class ScreenshotILI9341 : public Adafruit_ILI9341 {
public:
  ScreenshotILI9341(int8_t cs, int8_t dc, int8_t mosi, int8_t sclk, int8_t rst, int8_t miso)
    : Adafruit_ILI9341(cs, dc, mosi, sclk, rst, miso) {}

  void drawPixel(int16_t x, int16_t y, uint16_t color) override;
  void writePixel(int16_t x, int16_t y, uint16_t color) override;
  void writeFillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) override;
  void writeFastHLine(int16_t x, int16_t y, int16_t w, uint16_t color) override;
  void writeFastVLine(int16_t x, int16_t y, int16_t h, uint16_t color) override;
};

// Round 3 (rotation fix): the shadow buffer used to be a compile-time
// fixed 320x240 (landscape-only). Now that rotation itself is under
// test and may end up portrait-numeric (240x320), a fixed 320x240
// buffer would silently DROP any pixel with y>=240 -- a real
// correctness bug for a portrait framebuffer, not hypothetical. Sized
// at runtime instead, from the TFT's own tft.width()/height() after
// setRotation() -- same total pixel count (76800) and same total heap
// cost (153600 bytes) either way, just reshaped, so this does not add
// a new buffer or grow memory footprint.
extern int16_t g_screenshotW, g_screenshotH;

// Call as EARLY as possible (before WiFi/HTTP/weather), but AFTER
// tft.begin()+setRotation() so w/h are known -- see displayInit(). See
// the comment on the implementation for why allocating this lazily (on
// first draw) failed in practice.
void screenshotPreallocate(int16_t w, int16_t h, int rotation);
bool screenshotFramebufferReady();
// Streams a complete BMP (g_screenshotW x g_screenshotH, 24-bit BGR,
// standard bottom-to-top row order) to the given WiFiClient, converting
// one row of RGB565 to BGR888 at a time -- never allocates a second
// full-image buffer. Returns false if the shadow framebuffer was never
// allocated (nothing drawn yet, or allocation failed at boot).
bool screenshotWriteBmp(WiFiClient &client);

// ---- UI-state snapshot for /debug/ui-state -- set by the app whenever
// it redraws a region, read by the debug HTTP server. ----
void debugSetUiState(const String &screenName, const String &time_, const String &date,
                      const String &weatherCondition, int temperatureC, long rssi, bool wifiConnected);
String debugGetUiStateJson();

// ---- Optional deterministic QA override (task section "Optional
// deterministic screen state"). When active, the app substitutes these
// fixed values for live NTP/weather data so a screenshot always shows
// the same content regardless of real time/weather -- useful for
// comparing iterations. Does not alter any persisted/normal runtime
// data; purely an in-memory display override. ----
struct DebugQaState {
  bool active = false;
  String time_ = "18:88";
  String date = "28/08/2026";
  String dayOfWeek = "THU HAI";
  String location = "Binh Phuoc";
  float tempC = 29;
  String condition = "Giong bao";
  long rssi = -55;
};
extern DebugQaState g_debugQaState;

void debugStartHttpServer();
void debugHttpServerLoop(); // call from loop(), non-blocking
