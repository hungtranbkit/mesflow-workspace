// esp32-cyd-clock -- config template. Copy this file to config.h and
// fill in real values. config.h is gitignored (it holds a WiFi
// password) -- config.example.h is the one that gets committed.

#pragma once

// ---- WiFi ----
// TEMPORARY DEVELOPMENT WIFI -- replace with a real WiFi-setup UI later
// (see README "Known limitations"). Never commit real production WiFi
// credentials here even in config.h.
#define WIFI_SSID "your-ssid"
#define WIFI_PASS "your-password"

// ---- Timezone ----
// POSIX TZ string. Vietnam has no DST, so this is simply a fixed UTC+7
// offset -- the sign is inverted per POSIX convention (offset is
// subtracted from local time to get UTC).
#define CLOCK_TZ "ICT-7"
#define NTP_SERVER_1 "pool.ntp.org"
#define NTP_SERVER_2 "time.google.com"

// ---- Weather (Open-Meteo, no API key required) ----
#define WEATHER_LOCATION_NAME "Binh Phuoc"
#define WEATHER_LAT 11.536f
#define WEATHER_LON 106.919f
#define WEATHER_REFRESH_MS (15UL * 60UL * 1000UL) // 15 minutes
#define WEATHER_STALE_MS   (60UL * 60UL * 1000UL) // consider data stale after 1 hour of failed refreshes
#define WEATHER_HTTP_TIMEOUT_MS 8000
