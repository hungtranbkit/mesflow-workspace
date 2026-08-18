// Test B -- Adafruit_ST7789, simplified physical geometry test (round
// 2). Same physical SPI pins/bitbang-SPI family as Test A -- isolates
// the controller/init-table variable only. Minimal: no WiFi/HTTP/
// screenshot/text/custom font.
//
// Explicit geometry check per instruction: this must be configured as
// a native 240x320 panel, NOT 240x240 (a common ST7789 module size that
// would require a nonzero offset and could itself look "square" if
// wrongly assumed). See init(240,320) below and the Serial log it
// produces.

#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

#define TFT_CS   15
#define TFT_DC   2
#define TFT_MOSI 13
#define TFT_SCLK 14
#define TFT_RST  -1
#define TFT_BL   21

Adafruit_ST7789 tft(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST);

static void logAllRotationGeometry() {
  for (uint8_t r = 0; r < 4; r++) {
    tft.setRotation(r);
    Serial.printf("[TEST_B][GEOM] rotation=%d width=%d height=%d\n", r, tft.width(), tft.height());
  }
}

static void pattern1Border(int16_t w, int16_t h) {
  tft.fillScreen(ST77XX_BLACK);
  for (int t = 0; t < 3; t++) tft.drawRect(t, t, w - 2 * t, h - 2 * t, ST77XX_WHITE);
  Serial.printf("[TEST_B] Pattern1: 3px border, 0,0,%d,%d\n", w, h);
  delay(3000);
}

static void pattern2Quadrants(int16_t w, int16_t h) {
  int16_t hw = w / 2, hh = h / 2;
  tft.fillRect(0, 0, hw, hh, ST77XX_RED);
  tft.fillRect(hw, 0, w - hw, hh, ST77XX_GREEN);
  tft.fillRect(0, hh, hw, h - hh, ST77XX_BLUE);
  tft.fillRect(hw, hh, w - hw, h - hh, ST77XX_WHITE);
  Serial.printf("[TEST_B] Pattern2: quadrants (halves %d/%d x %d/%d)\n", hw, w - hw, hh, h - hh);
  delay(4000);
}

static void pattern3EdgeStrips(int16_t w, int16_t h) {
  tft.fillScreen(ST77XX_BLACK);
  const int16_t t = 10;
  tft.fillRect(0, 0, w, t, ST77XX_RED);
  tft.fillRect(0, h - t, w, t, ST77XX_GREEN);
  tft.fillRect(0, 0, t, h, ST77XX_BLUE);
  tft.fillRect(w - t, 0, t, h, ST77XX_WHITE);
  Serial.printf("[TEST_B] Pattern3: edge strips, t=%d\n", t);
  delay(4000);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("[TEST_B] Adafruit_ST7789 -- simplified geometry test");
  Serial.printf("[TEST_B] pins: CS=%d DC=%d MOSI=%d SCLK=%d RST=%d BL=%d (MISO unused by this ctor)\n",
    TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST, TFT_BL);

  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);

  Serial.println("[TEST_B] Configuring as native 240x320 (NOT 240x240) -- init(240,320)");
  tft.init(240, 320);
  // Adafruit_ST7789.cpp::init(): for width==240 && height==320, this
  // falls into the generic "centered" branch --
  // _colstart=_colstart2=(240-240)/2=0, _rowstart=_rowstart2=(320-320)/2=0.
  // (colstart/rowstart are protected, no public getter -- this is the
  // exact value computed by the installed library's own source for
  // this exact size, not assumed.)
  Serial.println("[TEST_B][GEOM] panel_native=240x320 xStart=0 yStart=0 (computed from library source for this exact size, see comment)");
  Serial.printf("[TEST_B][GEOM] after init: tft.width()=%d tft.height()=%d (rotation 0)\n", tft.width(), tft.height());

  logAllRotationGeometry();
}

void loop() {
  const uint8_t rotations[] = {1, 3};
  for (uint8_t i = 0; i < 2; i++) {
    uint8_t rot = rotations[i];
    tft.setRotation(rot);
    int16_t w = tft.width(), h = tft.height();
    Serial.printf("\n[TEST_B] ==== rotation=%d width=%d height=%d ====\n", rot, w, h);
    pattern1Border(w, h);
    pattern2Quadrants(w, h);
    pattern3EdgeStrips(w, h);
  }
}
