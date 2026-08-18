// esp32-cyd-clock -- Open-Meteo weather fetch (no API key required).
// Non-blocking from the caller's point of view: weatherTick() only
// does network I/O when its own millis()-based interval has elapsed,
// and always leaves the last-good reading in place on any failure.

#pragma once
#include <Arduino.h>

struct WeatherState {
  bool haveData = false;      // true once at least one successful fetch has happened
  bool stale = false;         // true if the last successful fetch is older than WEATHER_STALE_MS
  float tempC = 0;
  int humidityPct = 0;
  String condition = "";      // short ASCII label, e.g. "Co may", "Mua", "Troi quang"
  unsigned long lastSuccessMs = 0;
};

// Call from loop() -- returns quickly if it isn't time to refresh yet.
// Never blocks longer than WEATHER_HTTP_TIMEOUT_MS, never throws/crashes
// on a bad response; on any failure the previous WeatherState is left
// untouched except `stale` being recomputed against WEATHER_STALE_MS.
void weatherTick(WeatherState &state);
