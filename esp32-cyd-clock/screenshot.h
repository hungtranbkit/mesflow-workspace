// esp32-cyd-clock -- debug screenshot, TFT_eSPI-native reimplementation.
//
// Unlike the old Adafruit_ILI9341-era version (screenshot_disabled_ili9341/,
// which subclassed Adafruit_GFX's virtual draw hooks to mirror every
// draw into a shadow RAM buffer), this reads the REAL pixel data back
// from the panel's own GRAM via tft.readRect() -- TFT_eSPI exposes this
// directly over standard 4-wire SPI since MISO (GPIO12) is wired on
// this board. This is true ground-truth capture (what the panel
// actually has in its own memory, not a mirror of our draw calls) and
// needs no full-frame RAM buffer at all -- one row (320 x uint16_t =
// 640 bytes) at a time, streamed straight into the BMP HTTP response.
#pragma once
#include <Arduino.h>
#include <WiFi.h>

void debugSetUiState(const String &screenName, const String &time_, const String &date,
                      const String &weatherCondition, int temperatureC, long rssi, bool wifiConnected);

void debugStartHttpServer();
void debugHttpServerLoop(); // call from loop(), non-blocking
