#include "screenshot.h"
#include <WiFi.h>
#include <WebServer.h>

// Real bug found by actually fetching /debug/screenshot (503 every
// time), not assumed: a single 153600-byte malloc() FAILED even called
// as early as possible in setup() (before any WiFi/HTTP/weather churn)
// with free heap logged at 270508 bytes at the moment of the call --
// ESP.getFreeHeap() sums free bytes across the ESP32's several
// non-contiguous internal heap regions, it does NOT mean a single
// allocation that large can be satisfied (that's ESP.getMaxAllocHeap(),
// a much smaller number here). One big buffer was never going to work
// reliably on this board. Fixed by storing the shadow framebuffer as
// SCREENSHOT_H separate small per-row allocations (320*2 = 640 bytes
// each) instead of one 153600-byte block -- same total memory, but
// each individual allocation is trivially satisfiable even under heavy
// fragmentation, and it fits this file's existing "stream one row at a
// time" design even better than a monolithic buffer did.
// 320 = the largest dimension this panel can ever report (either axis,
// any rotation) -- just an array of pointers (1.25KB static, not heap),
// sized once for the worst case so both landscape (240 rows) and
// portrait (320 rows) fit without a second array shape.
static uint16_t *g_rows[320] = {nullptr};
static bool g_fbAllocFailed = false;
static bool g_fbAllocAttempted = false;
int16_t g_screenshotW = 0, g_screenshotH = 0;
static int g_rotation = 0;

void screenshotPreallocate(int16_t w, int16_t h, int rotation) {
  if (g_fbAllocAttempted) return;
  g_fbAllocAttempted = true;
  g_screenshotW = w; g_screenshotH = h; g_rotation = rotation;
  size_t rowBytes = (size_t)w * sizeof(uint16_t);
  for (int16_t y = 0; y < h; y++) {
    g_rows[y] = (uint16_t *)malloc(rowBytes);
    if (!g_rows[y]) {
      g_fbAllocFailed = true;
      Serial.printf("[SCREENSHOT] ERROR: framebuffer row %d allocation FAILED (out of memory, free heap=%u, max alloc=%u)\n",
                     y, ESP.getFreeHeap(), ESP.getMaxAllocHeap());
      // free whatever rows did succeed -- an all-or-nothing buffer, no
      // partial-screenshot mode
      for (int16_t k = 0; k < y; k++) { free(g_rows[k]); g_rows[k] = nullptr; }
      return;
    }
    memset(g_rows[y], 0, rowBytes);
  }
  Serial.printf("[SCREENSHOT] Framebuffer allocated: %dx%d (rotation=%d) as %d row buffers of %u bytes each (%u bytes total), free heap=%u\n",
                w, h, rotation, h, (unsigned)rowBytes,
                (unsigned)(rowBytes * h), ESP.getFreeHeap());
}

static inline void ensureFramebuffer() {
  // Do NOT lazily allocate here anymore -- w/h must come from the TFT's
  // real post-rotation geometry (see displayInit()). If this fires
  // before that call ran, something is drawing before init; there is
  // nothing sane to size a lazy buffer to, so just skip mirroring.
}

static inline void setFbPixel(int16_t x, int16_t y, uint16_t color) {
  if (g_fbAllocFailed || !g_fbAllocAttempted) return;
  if (x < 0 || y < 0 || x >= g_screenshotW || y >= g_screenshotH) return;
  if (!g_rows[y]) return;
  g_rows[y][x] = color;
}

void ScreenshotILI9341::drawPixel(int16_t x, int16_t y, uint16_t color) {
  ensureFramebuffer();
  setFbPixel(x, y, color);
  Adafruit_ILI9341::drawPixel(x, y, color);
}

void ScreenshotILI9341::writePixel(int16_t x, int16_t y, uint16_t color) {
  ensureFramebuffer();
  setFbPixel(x, y, color);
  Adafruit_ILI9341::writePixel(x, y, color);
}

void ScreenshotILI9341::writeFillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
  ensureFramebuffer();
  for (int16_t yy = y; yy < y + h; yy++)
    for (int16_t xx = x; xx < x + w; xx++)
      setFbPixel(xx, yy, color);
  Adafruit_ILI9341::writeFillRect(x, y, w, h, color);
}

void ScreenshotILI9341::writeFastHLine(int16_t x, int16_t y, int16_t w, uint16_t color) {
  ensureFramebuffer();
  for (int16_t xx = x; xx < x + w; xx++) setFbPixel(xx, y, color);
  Adafruit_ILI9341::writeFastHLine(x, y, w, color);
}

void ScreenshotILI9341::writeFastVLine(int16_t x, int16_t y, int16_t h, uint16_t color) {
  ensureFramebuffer();
  for (int16_t yy = y; yy < y + h; yy++) setFbPixel(x, yy, color);
  Adafruit_ILI9341::writeFastVLine(x, y, h, color);
}

bool screenshotFramebufferReady() { return g_fbAllocAttempted && !g_fbAllocFailed; }

bool screenshotWriteBmp(WiFiClient &client) {
  if (!screenshotFramebufferReady()) return false;
  const int16_t w = g_screenshotW, h = g_screenshotH;
  const uint32_t rowBytes = w * 3; // e.g. 960 for w=320, always a multiple of 4 for our even widths -- no BMP row padding needed
  const uint32_t imageSize = rowBytes * h;
  const uint32_t fileSize = 54 + imageSize;

  uint8_t header[54] = {0};
  header[0] = 'B'; header[1] = 'M';
  header[2] = fileSize & 0xFF; header[3] = (fileSize >> 8) & 0xFF; header[4] = (fileSize >> 16) & 0xFF; header[5] = (fileSize >> 24) & 0xFF;
  header[10] = 54; // pixel data offset
  header[14] = 40; // DIB header size
  header[18] = w & 0xFF; header[19] = (w >> 8) & 0xFF;
  header[22] = h & 0xFF; header[23] = (h >> 8) & 0xFF; // positive height = bottom-up row order (standard BMP)
  header[26] = 1;  // color planes
  header[28] = 24; // bits per pixel
  header[34] = imageSize & 0xFF; header[35] = (imageSize >> 8) & 0xFF; header[36] = (imageSize >> 16) & 0xFF; header[37] = (imageSize >> 24) & 0xFF;

  client.write(header, 54);

  uint8_t row[320 * 3]; // worst-case width, one row at a time, never the full image
  for (int16_t y = h - 1; y >= 0; y--) { // bottom-to-top, standard BMP order
    for (int16_t x = 0; x < w; x++) {
      uint16_t px = g_rows[y][x];
      uint8_t r5 = (px >> 11) & 0x1F, g6 = (px >> 5) & 0x3F, b5 = px & 0x1F;
      uint8_t r8 = (r5 << 3) | (r5 >> 2);
      uint8_t g8 = (g6 << 2) | (g6 >> 4);
      uint8_t b8 = (b5 << 3) | (b5 >> 2);
      row[x * 3 + 0] = b8; row[x * 3 + 1] = g8; row[x * 3 + 2] = r8; // BGR order
    }
    client.write(row, rowBytes);
  }
  return true;
}

// ---- UI state snapshot ----
static String s_screen = "clock", s_time = "", s_date = "", s_weather = "";
static int s_tempC = 0;
static long s_rssi = 0;
static bool s_wifiConnected = false;

void debugSetUiState(const String &screenName, const String &time_, const String &date,
                      const String &weatherCondition, int temperatureC, long rssi, bool wifiConnected) {
  s_screen = screenName; s_time = time_; s_date = date; s_weather = weatherCondition;
  s_tempC = temperatureC; s_rssi = rssi; s_wifiConnected = wifiConnected;
}

String debugGetUiStateJson() {
  char buf[320];
  // "rotation" used to be hardcoded to 3 here -- a real bug found while
  // testing rotation=1 (this field kept claiming 3 no matter what was
  // actually flashed). Now reports whatever screenshotPreallocate() was
  // actually called with.
  snprintf(buf, sizeof(buf),
    "{\"screen\":\"%s\",\"width\":%d,\"height\":%d,\"rotation\":%d,\"time\":\"%s\",\"date\":\"%s\","
    "\"weather\":\"%s\",\"temperature\":%d,\"wifi_rssi\":%ld,\"wifi_connected\":%s,\"qa_mode\":%s}",
    s_screen.c_str(), g_screenshotW, g_screenshotH, g_rotation, s_time.c_str(), s_date.c_str(),
    s_weather.c_str(), s_tempC, s_rssi, s_wifiConnected ? "true" : "false", g_debugQaState.active ? "true" : "false");
  return String(buf);
}

DebugQaState g_debugQaState;

// ---- Debug HTTP server ----
static WebServer *g_server = nullptr;

static void handleUiState() {
  g_server->send(200, "application/json", debugGetUiStateJson());
}

static void handleScreenshot() {
  if (!screenshotFramebufferReady()) {
    g_server->send(503, "text/plain", "framebuffer not ready -- nothing drawn yet");
    return;
  }
  WiFiClient client = g_server->client();
  const uint32_t imageSize = (uint32_t)g_screenshotW * 3 * g_screenshotH;
  g_server->setContentLength(54 + imageSize);
  g_server->send(200, "image/bmp", "");
  screenshotWriteBmp(client);
}

static void handleShowScreen() {
  String mode = g_server->hasArg("mode") ? g_server->arg("mode") : "qa";
  if (mode == "qa") {
    g_debugQaState.active = true;
    g_server->send(200, "application/json", "{\"ok\":true,\"mode\":\"qa\"}");
  } else if (mode == "live") {
    g_debugQaState.active = false;
    g_server->send(200, "application/json", "{\"ok\":true,\"mode\":\"live\"}");
  } else {
    g_server->send(400, "application/json", "{\"ok\":false,\"error\":\"mode must be qa or live\"}");
  }
}

static void handleScreensList() {
  g_server->send(200, "application/json", "{\"screens\":[\"clock\"],\"modes\":[\"live\",\"qa\"]}");
}

void debugStartHttpServer() {
  g_server = new WebServer(80);
  g_server->on("/debug/ui-state", HTTP_GET, handleUiState);
  g_server->on("/debug/screenshot", HTTP_GET, handleScreenshot);
  g_server->on("/debug/show-screen", HTTP_POST, handleShowScreen);
  g_server->on("/debug/screens", HTTP_GET, handleScreensList);
  g_server->begin();
  Serial.println("[SCREENSHOT] Debug HTTP server started on port 80 (/debug/ui-state, /debug/screenshot, /debug/show-screen, /debug/screens)");
}

void debugHttpServerLoop() {
  if (g_server) g_server->handleClient();
}
