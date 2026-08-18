// Test C -- TFT_eSPI (ST7789_DRIVER, hardware SPI), simplified physical
// geometry test (round 2). No pre-made CYD2USB config exists in the
// installed TFT_eSPI@2.5.43 (confirmed by search, see
// DISPLAY_DRIVER_MATRIX.md) -- config is from-scratch via
// compiler.cpp.extra_flags (build_and_flash.sh), not by editing the
// shared library's User_Setup.h. Minimal: no WiFi/HTTP/screenshot/
// text/custom font.
//
// SPI frequency: 20MHz (conservative -- geometry/controller first, not
// max performance, per instruction). See build_and_flash.sh.

#include <SPI.h>
#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();

static void logAllRotationGeometry() {
  for (uint8_t r = 0; r < 4; r++) {
    tft.setRotation(r);
    Serial.printf("[TEST_C][GEOM] rotation=%d width=%d height=%d\n", r, tft.width(), tft.height());
  }
}

static void pattern1Border(int16_t w, int16_t h) {
  tft.fillScreen(TFT_BLACK);
  for (int t = 0; t < 3; t++) tft.drawRect(t, t, w - 2 * t, h - 2 * t, TFT_WHITE);
  Serial.printf("[TEST_C] Pattern1: 3px border, 0,0,%d,%d\n", w, h);
  delay(3000);
}

static void pattern2Quadrants(int16_t w, int16_t h) {
  int16_t hw = w / 2, hh = h / 2;
  tft.fillRect(0, 0, hw, hh, TFT_RED);
  tft.fillRect(hw, 0, w - hw, hh, TFT_GREEN);
  tft.fillRect(0, hh, hw, h - hh, TFT_BLUE);
  tft.fillRect(hw, hh, w - hw, h - hh, TFT_WHITE);
  Serial.printf("[TEST_C] Pattern2: quadrants (halves %d/%d x %d/%d)\n", hw, w - hw, hh, h - hh);
  delay(4000);
}

static void pattern3EdgeStrips(int16_t w, int16_t h) {
  tft.fillScreen(TFT_BLACK);
  const int16_t t = 10;
  tft.fillRect(0, 0, w, t, TFT_RED);
  tft.fillRect(0, h - t, w, t, TFT_GREEN);
  tft.fillRect(0, 0, t, h, TFT_BLUE);
  tft.fillRect(w - t, 0, t, h, TFT_WHITE);
  Serial.printf("[TEST_C] Pattern3: edge strips, t=%d\n", t);
  delay(4000);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("[TEST_C] TFT_eSPI (ST7789_DRIVER, hardware SPI) -- simplified geometry test");
#ifdef TFT_CS
  Serial.printf("[TEST_C] pins (from build defines): CS=%d DC=%d MOSI=%d SCLK=%d MISO=%d RST=%d\n",
    TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_MISO, TFT_RST);
#endif
#ifdef TFT_WIDTH
  Serial.printf("[TEST_C][GEOM] configured native panel TFT_WIDTH=%d TFT_HEIGHT=%d (NOT 240x240)\n", TFT_WIDTH, TFT_HEIGHT);
#endif
#ifdef SPI_FREQUENCY
  Serial.printf("[TEST_C] SPI_FREQUENCY=%ld\n", (long)SPI_FREQUENCY);
#endif

  pinMode(21, OUTPUT);
  digitalWrite(21, HIGH);

  tft.init();
  Serial.printf("[TEST_C][GEOM] xStart=0 yStart=0 (no offset override passed -- TFT_eSPI ST7789 driver defaults to 0/0 for a 240x320 panel)\n");
  Serial.printf("[TEST_C][GEOM] after init: tft.width()=%d tft.height()=%d (rotation 0)\n", tft.width(), tft.height());

  logAllRotationGeometry();
}

void loop() {
  const uint8_t rotations[] = {1, 3};
  for (uint8_t i = 0; i < 2; i++) {
    uint8_t rot = rotations[i];
    tft.setRotation(rot);
    int16_t w = tft.width(), h = tft.height();
    Serial.printf("\n[TEST_C] ==== rotation=%d width=%d height=%d ====\n", rot, w, h);
    pattern1Border(w, h);
    pattern2Quadrants(w, h);
    pattern3EdgeStrips(w, h);
  }
}
