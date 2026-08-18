// tft_diagnostic -- TEMPORARY, isolated TFT rendering-path test.
//
// Purpose: prove or disprove that the physical TFT panel itself renders
// correctly, independent of any application/UI logic. Per the explicit
// instruction this firmware answers to: Serial + TFT ONLY. No WiFi, no
// NTP, no HTTPS, no JSON, no weather, no sprites, no custom/FreeFonts,
// no icons, no touch, no SD, no RGB animation, no adaptive font sizing.
//
// TFT init is BYTE-IDENTICAL to the known-good
// esp-kiosk/esp/hardware_test_cyd/hardware_test_cyd.ino (verified in
// DISPLAY_INIT_DIFF.md -- same library, same driver, same pins, same
// constructor, same tft.begin(), same rotation(3) as the default/first
// test). Not modified here.
//
// Every stage below only reports what actually executed on Serial.
// Whether the TFT actually LOOKS correct at each stage can only be
// confirmed by physically looking at the board -- this firmware does
// not and cannot claim "PASS" for anything visual.

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
// Included ONLY to empirically investigate the earlier "364px height"
// measurement anomaly (see the [FONT_INVESTIGATION] block below) --
// never used to draw/render anything in this diagnostic firmware.
#include <Fonts/FreeSansBold24pt7b.h>

// ---- TFT pins -- identical to hardware_test_cyd.ino, DISPLAY_INIT_DIFF.md confirms no difference ----
#define TFT_CS   15
#define TFT_DC   2
#define TFT_MOSI 13
#define TFT_SCLK 14
#define TFT_MISO 12
#define TFT_RST  -1
#define TFT_BL   21

Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST, TFT_MISO);

// Full sequence runs repeatedly from loop(), not once from setup() --
// the first version of this firmware ran it once and the LAST stage
// (built-in font text) silently overwrote the grid test, so anyone
// checking the board after boot only ever saw the final stage, never
// the earlier ones. Cycling means every stage becomes visible again
// within about a minute, regardless of when you look.
void runDiagnosticSequence() {
  // ==================================================================
  // STEP 5 FIRST (not step order, but logically first): test all 4
  // rotations, since later steps need to pick one. Each rotation:
  // print W/H, fill black, border, 4 corner color blocks, hold 3s.
  // Physical confirmation of which rotation looks correct is up to you
  // -- this only proves what width/height the driver reports for each.
  // ==================================================================
  tft.begin(); // exactly as hardware_test_cyd.ino -- no arguments
  for (uint8_t rot = 0; rot <= 3; rot++) {
    tft.setRotation(rot);
    int w = tft.width(), h = tft.height();
    Serial.printf("[ROTATION %d] W=%d H=%d\n", rot, w, h);
    tft.fillScreen(ILI9341_BLACK);
    tft.drawRect(0, 0, w, h, ILI9341_WHITE);
    tft.drawRect(1, 1, w - 2, h - 2, ILI9341_WHITE);
    int cb = 30; // corner block size
    tft.fillRect(0, 0, cb, cb, ILI9341_RED);           // top-left
    tft.fillRect(w - cb, 0, cb, cb, ILI9341_GREEN);    // top-right
    tft.fillRect(0, h - cb, cb, cb, ILI9341_BLUE);     // bottom-left
    tft.fillRect(w - cb, h - cb, cb, cb, ILI9341_YELLOW); // bottom-right
    delay(3000);
  }

  // Settle back on rotation 3 (the one previously physically confirmed
  // correct for this board's mount) for every remaining test below.
  tft.setRotation(3);
  int W = tft.width(), H = tft.height();
  Serial.printf("[DISPLAY] Using rotation=3 W=%d H=%d for remaining tests\n", W, H);

  // ==================================================================
  // STEP 3: full-screen solid color test. ONLY tft.fillScreen() per
  // test, nothing else drawn.
  // ==================================================================
  struct { const char *name; uint16_t color; } solids[] = {
    {"BLACK", ILI9341_BLACK}, {"WHITE", ILI9341_WHITE}, {"RED", ILI9341_RED},
    {"GREEN", ILI9341_GREEN}, {"BLUE", ILI9341_BLUE}
  };
  for (int i = 0; i < 5; i++) {
    tft.fillScreen(solids[i].color);
    Serial.printf("[TEST %d] %s\n", i + 1, solids[i].name);
    delay(2000);
  }

  // ==================================================================
  // STEP 4: coordinate/address-window test. No text, no sprites.
  // ==================================================================
  Serial.println("[GRID] Starting coordinate/address-window test");
  tft.fillScreen(ILI9341_BLACK);
  tft.fillRect(0,   0, 80, 60, ILI9341_RED);
  tft.fillRect(80,  0, 80, 60, ILI9341_GREEN);
  tft.fillRect(160, 0, 80, 60, ILI9341_BLUE);
  tft.fillRect(240, 0, 80, 60, ILI9341_WHITE);

  int cb2 = 30;
  tft.fillRect(0, 0, cb2, cb2, ILI9341_YELLOW);              // reinforces top-left over the red block, deliberately -- confirms draw order/overwrite works
  tft.fillRect(W - cb2, 0, cb2, cb2, ILI9341_YELLOW);        // top-right
  tft.fillRect(0, H - cb2, cb2, cb2, ILI9341_YELLOW);        // bottom-left
  tft.fillRect(W - cb2, H - cb2, cb2, cb2, ILI9341_YELLOW);  // bottom-right

  int hLines[] = {0, 30, 60, 90, 120, 150, 180, 210, 239};
  for (int y : hLines) tft.drawFastHLine(0, y, W, ILI9341_CYAN);
  int vLines[] = {0, 40, 80, 120, 160, 200, 240, 280, 319};
  for (int x : vLines) tft.drawFastVLine(x, 0, H, ILI9341_MAGENTA);

  Serial.println("[GRID] Coordinate/address-window test drawn (held 4s, then overwritten by the text test below)");

  // ==================================================================
  // STEP 8/9: simplest built-in bitmap font text test -- no FreeFonts,
  // no sprites, no adaptive sizing. Also empirically explains the
  // earlier "14:01 -> height 364px" anomaly (see report) by measuring
  // the SAME custom font's getTextBounds() with text wrap ON vs OFF,
  // without ever drawing it -- explanation only, not used for any
  // rendered content in this diagnostic.
  // ==================================================================
  delay(4000); // hold the grid test a bit longer before moving to text
  tft.fillScreen(ILI9341_BLACK);
  tft.setFont(); // built-in 5x7 font -- the simplest available
  tft.setTextColor(ILI9341_WHITE);
  tft.setTextWrap(false);

  const char *samples[] = {"1234567890", "14:05", "ABCDEF", "Binh Phuoc"};
  int16_t ty = 10;
  for (int s = 0; s < 4; s++) {
    for (uint8_t size = 1; size <= 3; size++) {
      tft.setTextSize(size);
      int16_t bx, by; uint16_t bw, bh;
      tft.getTextBounds(samples[s], 0, 0, &bx, &by, &bw, &bh);
      Serial.printf("[TEXT] font=builtin size=%u text=\"%s\" measured=%ux%u bx=%d by=%d\n",
        size, samples[s], bw, bh, bx, by);
      if (size == 2) { // draw one representative size per sample so the screen shows something
        tft.setCursor(10, ty);
        tft.print(samples[s]);
        ty += bh + 12;
      }
    }
  }
  Serial.println("[TEXT] Built-in font test drawn (stays until this cycle ends, then rotations restart)");

  // ---- Custom-font measurement-only investigation (no drawing) ----
  // Explains the earlier "00:00 at size=4 -> 364px tall" mystery: does
  // it change with setTextWrap(false)? If yes, this confirms the
  // custom-font getTextBounds() height ballooned because Adafruit_GFX's
  // internal wrap logic split the string across multiple lines once its
  // natural single-line width at that size exceeded the panel's
  // physical width (320px) -- not a driver/panel corruption issue.
  tft.setFont(&FreeSansBold24pt7b);
  for (int wrap = 0; wrap <= 1; wrap++) {
    tft.setTextWrap(wrap == 1);
    for (uint8_t size = 2; size <= 4; size++) {
      tft.setTextSize(size);
      int16_t bx, by; uint16_t bw, bh;
      tft.getTextBounds("00:00", 0, 0, &bx, &by, &bw, &bh);
      Serial.printf("[FONT_INVESTIGATION] wrap=%d size=%u \"00:00\" measured=%ux%u\n", wrap, size, bw, bh);
    }
  }
  tft.setFont(); // back to built-in, nothing further uses the custom font

  Serial.println("[TFT_DIAGNOSTIC] Cycle complete. Built-in font sample stays on screen for 6s, then the whole sequence repeats.");
  delay(6000);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("[TFT_DIAGNOSTIC] Starting isolated TFT rendering test (repeats continuously)");
  Serial.printf("[CHIP] %s rev%d\n", ESP.getChipModel(), ESP.getChipRevision());
  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);
}

void loop() {
  runDiagnosticSequence();
}
