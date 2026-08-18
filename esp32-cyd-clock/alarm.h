// esp32-cyd-clock -- daily alarm.
//
// Speaker pin: GPIO26. Per esp-kiosk/BOARD_INFO.md's prior hardware
// investigation of this exact board family (ESP32-2432S028 CYD,
// community reference, 2-pin JST "SPEAK" header): GPIO26 "drives the
// onboard amplifier feeding the SPEAK header, DAC/PWM capable" -- there
// IS an amplifier in the path, not a bare piezo/speaker cone directly
// on the pin, so a modest PWM tone (not a continuous DC level) is the
// documented-appropriate drive method. That note was for this board
// FAMILY, not continuity-tested on this exact physical unit -- kept
// conservative here (modest 2kHz tone, 50% duty via LEDC, bounded
// 30s auto-stop, never a raw DC drive) precisely because of that.
#pragma once
#include <Arduino.h>

// ---- Production alarm time -- Vietnam / UTC+7, the same
// getLocalTime()-backed, NTP-synchronized time source the clock
// display itself uses (no separate time source). ----
#define ALARM_HOUR 7
#define ALARM_MINUTE 0

// ---- Test mode -- set to 1 to verify trigger/beep/overlay/auto-stop
// without waiting for a real 07:00. When on, the alarm fires once,
// ALARM_TEST_TRIGGER_DELAY_MS after boot (via millis(), independent of
// NTP/wall-clock state) instead of at the real alarm time. MUST be 0
// for production -- restored before the final build/flash. ----
#define ALARM_TEST_MODE 0
#define ALARM_TEST_TRIGGER_DELAY_MS 15000UL

#define SPEAKER_PIN 26
#define ALARM_TONE_HZ 2000UL
#define ALARM_BEEP_ON_MS 500UL
#define ALARM_BEEP_OFF_MS 500UL
#define ALARM_DURATION_MS 30000UL

void alarmInit();
// Call every loop() with the current local time (from the same
// getLocalTime() call the clock display uses). Non-blocking -- only
// ever uses millis()-based timing internally, never delay().
void alarmTick(int hour, int minute, int yday);
bool alarmIsActive();
