// esp32-cyd-clock -- V0.2.0
// Simple 24/7 desk clock for the ESP32-2432S028 (CYD) dual-USB board.
// Independent project -- does not modify or depend on the MESFlow
// kiosk firmware (esp-kiosk/). See README.md and BOARD_INFO.md.
//
// V0.2.0: display layer migrated from Adafruit_ILI9341 to TFT_eSPI/
// ST7789 -- see BOARD_INFO.md and DISPLAY_DRIVER_MATRIX.md. The old
// ILI9341 stack physically compressed the active area on this board's
// real ST7789 panel; TFT_eSPI+ST7789_DRIVER was physically verified
// (full-edge border/quadrant/strip test) to fill the complete 320x240
// landscape panel. Build with build_and_flash.sh, not plain
// `arduino-cli compile` -- see display.h's header comment.
//
// Screenshot/debug capture (/debug/screenshot, /debug/ui-state) is
// RE-ENABLED this round, reimplemented natively for TFT_eSPI --
// screenshot.cpp now reads real GRAM via tft.readRect() instead of the
// old Adafruit_GFX shadow-buffer approach (see screenshot.h). Weather
// runs unconditionally (it was only ever disabled in the old ILI9341
// screenshot build to make room for a shadow framebuffer's memory
// pressure, which doesn't apply to this readRect-based approach at all
// -- no extra RAM buffer involved).

#include <WiFi.h>
#include <time.h>
#include "config.h"
#include "display.h"
#include "weather.h"
#include "alarm.h"
#include "screenshot.h"

static const char *WDAY_VN[7] = {
  "CHU NHAT", "THU HAI", "THU BA", "THU TU", "THU NAM", "THU SAU", "THU BAY"
};

WeatherState weather;

unsigned long lastWifiReconnectAttempt = 0;
const unsigned long WIFI_RECONNECT_INTERVAL_MS = 15000;
bool ntpSynced = false;

unsigned long lastDiagnosticMs = 0;
const unsigned long DIAGNOSTIC_INTERVAL_MS = 60000; // one quiet heartbeat line per minute, not per loop

// Real-time validity check: an epoch below this is definitely NOT a
// real synced clock (threshold is 2023-11-14, comfortably in the past
// -- any genuinely NTP-synced device reads well above it; an un-synced
// ESP32 boots near epoch 0). getLocalTime() already does an internal
// year>=2016 check -- this is a second, explicit check that doubles as
// a clear Serial log line.
#define VALID_EPOCH_THRESHOLD 1700000000L

void connectWiFi() {
  Serial.printf("[WIFI] Connecting to \"%s\"...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void setup() {
  Serial.begin(115200); // USB serial (CH340), UART0 -- kept free for debug, matches hardware_test_cyd/connector_test
  delay(300);
  Serial.println();
  Serial.println("[CLOCK] ESP32 CYD Clock");
  Serial.printf("[CHIP] %s rev%d, %d cores, %dMHz, flash %uMB, psram %u bytes\n",
    ESP.getChipModel(), ESP.getChipRevision(), ESP.getChipCores(), ESP.getCpuFreqMHz(),
    ESP.getFlashChipSize() / 1048576, ESP.getPsramSize());

  // Boot progress is Serial-only, deliberately -- displayInit() paints
  // the screen black once and nothing else touches the TFT until the
  // first real, complete frame is drawn in loop().
  displayInit();
  Serial.println("[TFT] OK");

  alarmInit();

  connectWiFi();
  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 15000) {
    delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WIFI] Connected, IP: %s, RSSI %ld dBm\n", WiFi.localIP().toString().c_str(), (long)WiFi.RSSI());
    debugStartHttpServer();
  } else {
    Serial.println("[WIFI] Not connected yet -- will keep retrying in the background");
  }

  // Standard timezone support via the TZ env var + NTP, not a manual
  // hour offset -- configTzTime() sets TZ and starts SNTP in one call.
  // CLOCK_TZ = "ICT-7" (config.h) -- POSIX TZ sign convention is
  // inverted from what it looks like: "ICT-7" means offset=-7 (the
  // value ADDED to local time to reach UTC), which correctly encodes
  // UTC+7 (Asia/Ho_Chi_Minh, no DST).
  configTzTime(CLOCK_TZ, NTP_SERVER_1, NTP_SERVER_2);
  if (WiFi.status() == WL_CONNECTED) {
    struct tm timeinfo;
    if (getLocalTime(&timeinfo, 10000)) {
      ntpSynced = true;
    } else {
      Serial.println("[NTP] Sync timed out after 10s -- not blocking boot; SNTP keeps retrying in the background, clock stays on system/RTC time meanwhile");
    }
  } else {
    Serial.println("[NTP] Skipped -- no WiFi yet");
  }

  {
    time_t nowEpoch = time(nullptr);
    bool validTime = nowEpoch > VALID_EPOCH_THRESHOLD;
    struct tm ti;
    localtime_r(&nowEpoch, &ti);
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &ti);
    Serial.printf("[TIME] epoch=%ld valid=%s local=%s tz=%s\n",
      (long)nowEpoch, validTime ? "true" : "false", buf, CLOCK_TZ);
  }

  // First weather fetch, best-effort -- failure here must never block
  // reaching READY. No longer gated behind a screenshot-memory
  // tradeoff (that subsystem is disabled in this version).
  weatherTick(weather);
  Serial.println(weather.haveData ? "[WEATHER] OK" : "[WEATHER] Pending");

  Serial.printf("[READY] Free heap: %u bytes\n", ESP.getFreeHeap());
  Serial.println("[READY]");
}

void loop() {
  unsigned long now = millis();

  debugHttpServerLoop(); // non-blocking, services one pending request if any

  // ---- WiFi reconnect, non-blocking ----
  if (WiFi.status() != WL_CONNECTED && now - lastWifiReconnectAttempt > WIFI_RECONNECT_INTERVAL_MS) {
    lastWifiReconnectAttempt = now;
    Serial.println("[WIFI] Reconnecting...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }

  // ---- Weather, self-throttled inside weatherTick() ----
  weatherTick(weather);

  // ---- Clock: read system time (kept ticking by the RTC/millis even
  // if WiFi/NTP is down). Only redraw when the displayed fields
  // actually change -- display.cpp itself also de-duplicates, this is
  // just to avoid needless measurement calls every loop. ----
  struct tm timeinfo;
  static int lastDrawnMinute = -1;
  static int lastDrawnYday = -1;
  static char currentDateBuf[16] = "";
  static const char *currentWday = WDAY_VN[1];
  static unsigned long lastHeaderUpdateMs = 0;
  static bool alarmWasActive = false;
  bool dateChangedThisTick = false;
  bool haveDate = false;

  if (getLocalTime(&timeinfo, 5)) {
    if (!ntpSynced) { ntpSynced = true; Serial.println("[NTP] Time now available"); }

    // Alarm check/state-machine runs every tick regardless of minute
    // change, BEFORE the display calls below, so alarmIsActive()
    // reflects this tick's state for the gating right after it.
    alarmTick(timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_yday);

    // Alarm just ended: displayHideAlarmOverlay() (called from inside
    // alarmTick()) already invalidated display.cpp's own redraw cache,
    // but this .ino's OWN "did the minute/date actually change" gates
    // (lastDrawnMinute/lastHeaderUpdateMs) would otherwise still think
    // nothing changed and skip calling displayUpdateTime()/Header() at
    // all until the next real minute rollover -- leaving the clock
    // band blank. Force both gates open for exactly one tick here.
    bool alarmJustEnded = alarmWasActive && !alarmIsActive();
    if (alarmJustEnded) { lastDrawnMinute = -1; lastHeaderUpdateMs = 0; }
    alarmWasActive = alarmIsActive();

    if (timeinfo.tm_min != lastDrawnMinute) {
      lastDrawnMinute = timeinfo.tm_min;
      if (!alarmIsActive()) displayUpdateTime(timeinfo.tm_hour, timeinfo.tm_min);
    }
    if (timeinfo.tm_yday != lastDrawnYday) {
      lastDrawnYday = timeinfo.tm_yday;
      snprintf(currentDateBuf, sizeof(currentDateBuf), "%02d/%02d/%04d", timeinfo.tm_mday, timeinfo.tm_mon + 1, timeinfo.tm_year + 1900);
      currentWday = WDAY_VN[timeinfo.tm_wday];
      dateChangedThisTick = true;
    }
    haveDate = lastDrawnYday != -1;
  }

  // Display updates are skipped entirely while the alarm overlay is
  // showing -- restored once the alarm ends (see alarmJustEnded above).
  if (!alarmIsActive()) {
    displayUpdateWeather(WEATHER_LOCATION_NAME, weather.tempC, weather.condition, weather.haveData, weather.stale);

    // Header (date + WiFi/RSSI) is rate-limited to once every 8s for the
    // RSSI portion -- display.cpp already ignores sub-5dB wobble, but
    // real-world RSSI can still cross rounding buckets every couple of
    // seconds, which would redraw far more often than useful. A date
    // change (once/day) still redraws immediately regardless of the
    // rate limit.
    if (haveDate && (dateChangedThisTick || now - lastHeaderUpdateMs > 8000)) {
      lastHeaderUpdateMs = now;
      displayUpdateHeader(currentWday, currentDateBuf, (long)WiFi.RSSI(), WiFi.status() == WL_CONNECTED);
    }
  }

  // ---- Keep /debug/ui-state current every tick (cheap -- just a few
  // static String assignments, no drawing) ----
  {
    char timeBuf[6];
    snprintf(timeBuf, sizeof(timeBuf), "%02d:%02d", timeinfo.tm_hour, timeinfo.tm_min);
    debugSetUiState("clock", haveDate ? String(timeBuf) : "", haveDate ? String(currentDateBuf) : "",
                     weather.condition, (int)(weather.tempC + 0.5f), (long)WiFi.RSSI(), WiFi.status() == WL_CONNECTED);
  }

  // ---- Quiet periodic diagnostic (not every loop) ----
  if (now - lastDiagnosticMs > DIAGNOSTIC_INTERVAL_MS) {
    lastDiagnosticMs = now;
    time_t nowEpoch = time(nullptr);
    struct tm ti;
    localtime_r(&nowEpoch, &ti);
    char tbuf[24];
    strftime(tbuf, sizeof(tbuf), "%Y-%m-%d %H:%M:%S", &ti);
    Serial.printf("[DIAG] heap=%u wifi=%s rssi=%ld weather=%s%s epoch=%ld local=%s valid=%s\n",
      ESP.getFreeHeap(),
      WiFi.status() == WL_CONNECTED ? "up" : "down",
      (long)WiFi.RSSI(),
      weather.haveData ? "ok" : "none",
      weather.stale ? " stale" : "",
      (long)nowEpoch, tbuf, nowEpoch > VALID_EPOCH_THRESHOLD ? "true" : "false");
  }

  delay(50); // short, bounded -- never a long/blocking delay
}
