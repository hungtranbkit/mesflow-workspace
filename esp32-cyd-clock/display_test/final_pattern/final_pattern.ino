// Final continuous display -- left running after the A/B/C driver
// matrix, per instruction: "leave the most promising ST7789 test
// running continuously... prefer Test C if it boots correctly."
// Test C (TFT_eSPI + ST7789_DRIVER, hardware SPI) booted clean, correct
// geometry every rotation, no crashes, no SPI/init warnings across 3
// full pattern cycles -- so this is that same stack, same pins, same
// 20MHz SPI, landscape rotation=1, alternating every 3s so a human has
// plenty of time to inspect without catching a boot window:
//   1. full RED (3s)
//   2. full GREEN (3s)
//   3. full BLUE (3s)
//   4. four quadrants RED/GREEN/BLUE/WHITE (3s)
//   5. edge strips TOP=red BOTTOM=green LEFT=blue RIGHT=white (3s)
//   -> repeat

#include <SPI.h>
#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("[FINAL] TFT_eSPI (ST7789_DRIVER) -- continuous inspection pattern, rotation=1");
  pinMode(21, OUTPUT);
  digitalWrite(21, HIGH);
  tft.init();
  tft.setRotation(1);
  Serial.printf("[FINAL] width=%d height=%d\n", tft.width(), tft.height());
}

void loop() {
  int16_t w = tft.width(), h = tft.height();

  tft.fillScreen(TFT_RED);   Serial.println("[FINAL] full RED");   delay(3000);
  tft.fillScreen(TFT_GREEN); Serial.println("[FINAL] full GREEN"); delay(3000);
  tft.fillScreen(TFT_BLUE);  Serial.println("[FINAL] full BLUE");  delay(3000);

  int16_t hw = w / 2, hh = h / 2;
  tft.fillRect(0, 0, hw, hh, TFT_RED);
  tft.fillRect(hw, 0, w - hw, hh, TFT_GREEN);
  tft.fillRect(0, hh, hw, h - hh, TFT_BLUE);
  tft.fillRect(hw, hh, w - hw, h - hh, TFT_WHITE);
  Serial.println("[FINAL] quadrants");
  delay(3000);

  tft.fillScreen(TFT_BLACK);
  const int16_t t = 10;
  tft.fillRect(0, 0, w, t, TFT_RED);
  tft.fillRect(0, h - t, w, t, TFT_GREEN);
  tft.fillRect(0, 0, t, h, TFT_BLUE);
  tft.fillRect(w - t, 0, t, h, TFT_WHITE);
  Serial.println("[FINAL] edge strips");
  delay(3000);
}
