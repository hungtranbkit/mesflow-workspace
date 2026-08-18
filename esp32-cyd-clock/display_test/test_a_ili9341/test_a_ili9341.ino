// Test A -- current driver (Adafruit_ILI9341), simplified physical
// geometry test (round 2 -- fewer/faster patterns per instruction).
// Minimal: no WiFi/HTTP/screenshot/text/custom font.
//
// Board: ESP32-2432S028 dual-USB CYD, classic ESP32-D0WD-V3. FQBN
// esp32:esp32:esp32.
//
// Sequence: log width/height for rotations 0-3 once (cheap, informative
// -- not physically tested at 0/2, only logged), then continuously
// cycle rotation 1 and 3 only (the two landscape orientations), each:
//   Pattern 1: 3px white border, black bg, hold 3s
//   Pattern 2: 4 quadrants RED/GREEN/BLUE/WHITE, hold 4s
//   Pattern 3: 10px edge strips TOP=red BOTTOM=green LEFT=blue RIGHT=white, hold 4s
// ~11s/rotation, repeats forever.

#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>

#define TFT_CS   15
#define TFT_DC   2
#define TFT_MOSI 13
#define TFT_SCLK 14
#define TFT_MISO 12
#define TFT_RST  -1
#define TFT_BL   21

Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST, TFT_MISO);

static void logAllRotationGeometry() {
  for (uint8_t r = 0; r < 4; r++) {
    tft.setRotation(r);
    Serial.printf("[TEST_A][GEOM] rotation=%d width=%d height=%d\n", r, tft.width(), tft.height());
  }
}

static void pattern1Border(int16_t w, int16_t h) {
  tft.fillScreen(ILI9341_BLACK);
  for (int t = 0; t < 3; t++) tft.drawRect(t, t, w - 2 * t, h - 2 * t, ILI9341_WHITE);
  Serial.printf("[TEST_A] Pattern1: 3px border, 0,0,%d,%d\n", w, h);
  delay(3000);
}

static void pattern2Quadrants(int16_t w, int16_t h) {
  int16_t hw = w / 2, hh = h / 2;
  tft.fillRect(0, 0, hw, hh, ILI9341_RED);
  tft.fillRect(hw, 0, w - hw, hh, ILI9341_GREEN);
  tft.fillRect(0, hh, hw, h - hh, ILI9341_BLUE);
  tft.fillRect(hw, hh, w - hw, h - hh, ILI9341_WHITE);
  Serial.printf("[TEST_A] Pattern2: quadrants (halves %d/%d x %d/%d)\n", hw, w - hw, hh, h - hh);
  delay(4000);
}

static void pattern3EdgeStrips(int16_t w, int16_t h) {
  tft.fillScreen(ILI9341_BLACK);
  const int16_t t = 10;
  tft.fillRect(0, 0, w, t, ILI9341_RED);        // TOP
  tft.fillRect(0, h - t, w, t, ILI9341_GREEN);  // BOTTOM
  tft.fillRect(0, 0, t, h, ILI9341_BLUE);       // LEFT
  tft.fillRect(w - t, 0, t, h, ILI9341_WHITE);  // RIGHT
  Serial.printf("[TEST_A] Pattern3: edge strips, t=%d\n", t);
  delay(4000);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("[TEST_A] Adafruit_ILI9341 -- simplified geometry test");
  Serial.printf("[TEST_A] pins: CS=%d DC=%d MOSI=%d SCLK=%d MISO=%d RST=%d BL=%d\n",
    TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_MISO, TFT_RST, TFT_BL);

  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);
  tft.begin();
  logAllRotationGeometry();
}

void loop() {
  const uint8_t rotations[] = {1, 3}; // landscape only, per instruction
  for (uint8_t i = 0; i < 2; i++) {
    uint8_t rot = rotations[i];
    tft.setRotation(rot);
    int16_t w = tft.width(), h = tft.height();
    Serial.printf("\n[TEST_A] ==== rotation=%d width=%d height=%d ====\n", rot, w, h);
    pattern1Border(w, h);
    pattern2Quadrants(w, h);
    pattern3EdgeStrips(w, h);
  }
}
