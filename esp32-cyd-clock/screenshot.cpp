#include "screenshot.h"
#include "display.h"
#include <WebServer.h>

// ---- UI state snapshot for /debug/ui-state ----
static String s_screen = "clock", s_time = "", s_date = "", s_weather = "";
static int s_tempC = 0;
static long s_rssi = 0;
static bool s_wifiConnected = false;

void debugSetUiState(const String &screenName, const String &time_, const String &date,
                      const String &weatherCondition, int temperatureC, long rssi, bool wifiConnected) {
  s_screen = screenName; s_time = time_; s_date = date; s_weather = weatherCondition;
  s_tempC = temperatureC; s_rssi = rssi; s_wifiConnected = wifiConnected;
}

static String uiStateJson() {
  char buf[320];
  snprintf(buf, sizeof(buf),
    "{\"screen\":\"%s\",\"width\":%d,\"height\":%d,\"rotation\":1,\"time\":\"%s\",\"date\":\"%s\","
    "\"weather\":\"%s\",\"temperature\":%d,\"wifi_rssi\":%ld,\"wifi_connected\":%s}",
    s_screen.c_str(), displayWidth(), displayHeight(), s_time.c_str(), s_date.c_str(),
    s_weather.c_str(), s_tempC, s_rssi, s_wifiConnected ? "true" : "false");
  return String(buf);
}

// ---- BMP streaming, one row read from the real panel at a time ----
static bool writeBmp(WiFiClient &client) {
  const int32_t w = displayWidth(), h = displayHeight();
  const uint32_t rowBytes = w * 3;
  const uint32_t imageSize = rowBytes * h;
  const uint32_t fileSize = 54 + imageSize;

  uint8_t header[54] = {0};
  header[0] = 'B'; header[1] = 'M';
  header[2] = fileSize & 0xFF; header[3] = (fileSize >> 8) & 0xFF; header[4] = (fileSize >> 16) & 0xFF; header[5] = (fileSize >> 24) & 0xFF;
  header[10] = 54;
  header[14] = 40;
  header[18] = w & 0xFF; header[19] = (w >> 8) & 0xFF;
  header[22] = h & 0xFF; header[23] = (h >> 8) & 0xFF; // positive height = bottom-up row order (standard BMP)
  header[26] = 1;
  header[28] = 24;
  header[34] = imageSize & 0xFF; header[35] = (imageSize >> 8) & 0xFF; header[36] = (imageSize >> 16) & 0xFF; header[37] = (imageSize >> 24) & 0xFF;
  client.write(header, 54);

  uint16_t rowPixels[320]; // RGB565, one row, worst-case width
  uint8_t rowOut[320 * 3]; // BGR888, one row
  for (int32_t y = h - 1; y >= 0; y--) { // bottom-to-top, standard BMP order
    displayReadRow(y, rowPixels, w);
    for (int32_t x = 0; x < w; x++) {
      uint16_t px = rowPixels[x];
      uint8_t r5 = (px >> 11) & 0x1F, g6 = (px >> 5) & 0x3F, b5 = px & 0x1F;
      uint8_t r8 = (r5 << 3) | (r5 >> 2);
      uint8_t g8 = (g6 << 2) | (g6 >> 4);
      uint8_t b8 = (b5 << 3) | (b5 >> 2);
      rowOut[x * 3 + 0] = b8; rowOut[x * 3 + 1] = g8; rowOut[x * 3 + 2] = r8; // BGR order
    }
    client.write(rowOut, rowBytes);
  }
  return true;
}

static WebServer *g_server = nullptr;

static void handleUiState() {
  g_server->send(200, "application/json", uiStateJson());
}

static void handleScreenshot() {
  const int32_t w = displayWidth(), h = displayHeight();
  WiFiClient client = g_server->client();
  const uint32_t imageSize = (uint32_t)w * 3 * h;
  g_server->setContentLength(54 + imageSize);
  g_server->send(200, "image/bmp", "");
  writeBmp(client);
}

void debugStartHttpServer() {
  g_server = new WebServer(80);
  g_server->on("/debug/ui-state", HTTP_GET, handleUiState);
  g_server->on("/debug/screenshot", HTTP_GET, handleScreenshot);
  g_server->begin();
  Serial.println("[SCREENSHOT] Debug HTTP server started on port 80 (/debug/ui-state, /debug/screenshot) -- reads real GRAM via tft.readRect(), no shadow buffer");
}

void debugHttpServerLoop() {
  if (g_server) g_server->handleClient();
}
