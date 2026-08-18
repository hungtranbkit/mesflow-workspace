#include "weather.h"
#include "config.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Open-Meteo requires HTTPS; setInsecure() skips certificate validation
// (deliberate simplification -- this is a public, read-only, non-
// sensitive weather endpoint with no credentials involved, and pinning
// a CA cert here would add real maintenance risk -- cert rotation --
// for a "keep V0.1 simple and stable" clock. Revisit if this firmware
// ever fetches anything sensitive.)

static unsigned long lastAttemptMs = 0;

static String wmoToCondition(int code) {
  if (code == 0) return "Troi quang";
  if (code == 1 || code == 2 || code == 3) return "Co may";
  if (code == 45 || code == 48) return "Suong mu";
  if (code >= 51 && code <= 57) return "Mua phun";
  if (code >= 61 && code <= 67) return "Mua";
  if (code >= 71 && code <= 77) return "Tuyet";
  if (code >= 80 && code <= 82) return "Mua rao";
  if (code == 85 || code == 86) return "Mua tuyet";
  if (code >= 95 && code <= 99) return "Giong bao";
  return "Khong ro";
}

static bool fetchOnce(WeatherState &state) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WEATHER] Skipped -- WiFi not connected");
    return false;
  }

  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(WEATHER_HTTP_TIMEOUT_MS / 1000);

  HTTPClient http;
  http.setConnectTimeout(WEATHER_HTTP_TIMEOUT_MS);
  http.setTimeout(WEATHER_HTTP_TIMEOUT_MS);

  char url[256];
  snprintf(url, sizeof(url),
    "https://api.open-meteo.com/v1/forecast?latitude=%.3f&longitude=%.3f&current=temperature_2m,relative_humidity_2m,weather_code&timezone=auto",
    WEATHER_LAT, WEATHER_LON);

  if (!http.begin(client, url)) {
    Serial.println("[WEATHER] http.begin() failed");
    return false;
  }

  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    Serial.printf("[WEATHER] HTTP error: %d\n", code);
    http.end();
    return false;
  }

  String body = http.getString();
  http.end();

  JsonDocument doc; // ArduinoJson 7 -- auto-sized, no manual capacity math needed
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    Serial.printf("[WEATHER] JSON parse error: %s\n", err.c_str());
    return false;
  }

  if (!doc["current"].is<JsonObject>()) {
    Serial.println("[WEATHER] Unexpected response shape (no \"current\")");
    return false;
  }

  state.tempC = doc["current"]["temperature_2m"] | 0.0f;
  state.humidityPct = doc["current"]["relative_humidity_2m"] | 0;
  int wcode = doc["current"]["weather_code"] | -1;
  state.condition = wmoToCondition(wcode);
  state.haveData = true;
  state.stale = false;
  state.lastSuccessMs = millis();

  Serial.printf("[WEATHER] %.1fC, %d%% humidity, code=%d (%s)\n", state.tempC, state.humidityPct, wcode, state.condition.c_str());
  return true;
}

void weatherTick(WeatherState &state) {
  unsigned long now = millis();

  // Recompute staleness every tick regardless of whether we attempt a
  // fetch this time, so the display reflects reality even between
  // refresh attempts.
  if (state.haveData) {
    state.stale = (now - state.lastSuccessMs) > WEATHER_STALE_MS;
  }

  bool dueForRefresh = (lastAttemptMs == 0) || (now - lastAttemptMs >= WEATHER_REFRESH_MS);
  if (!dueForRefresh) return;
  lastAttemptMs = now;

  Serial.println("[WEATHER] Refreshing...");
  bool ok = fetchOnce(state);
  if (!ok) {
    Serial.println("[WEATHER] Fetch failed, keeping last known data" + String(state.haveData ? "" : " (none yet)"));
  }
}
