#include "alarm.h"
#include "display.h"
#include <time.h>

// Same real-time-validity threshold used elsewhere in this project
// (2023-11-14, comfortably in the past) -- an un-synced ESP32 boots
// near epoch 0, so this alone is enough to reject a not-yet-synced
// clock from ever firing the production alarm early/wrong.
#define ALARM_VALID_EPOCH_THRESHOLD 1700000000L

enum AlarmPhase { ALARM_IDLE, ALARM_BEEP_ON, ALARM_BEEP_OFF };
static AlarmPhase g_phase = ALARM_IDLE;
static unsigned long g_alarmStartMs = 0;
static unsigned long g_phaseStartMs = 0;
static int g_lastAlarmYday = -1;
#if ALARM_TEST_MODE
static bool g_testFired = false;
#endif

void alarmInit() {
  ledcAttach(SPEAKER_PIN, ALARM_TONE_HZ, 8); // 8-bit duty resolution -- plenty for a simple square-wave tone
  ledcWriteTone(SPEAKER_PIN, 0);             // make sure it starts silent, not driven
  Serial.printf("[ALARM] configured %02d:%02d\n", ALARM_HOUR, ALARM_MINUTE);
#if ALARM_TEST_MODE
  Serial.println("[ALARM] TEST MODE ACTIVE -- will fire once ~15s after boot instead of waiting for the real time. MUST be reverted to ALARM_TEST_MODE 0 before production.");
#endif
}

static void logTriggerTimestamp() {
  time_t now = time(nullptr);
  struct tm ti;
  localtime_r(&now, &ti);
  char buf[24];
  strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M", &ti);
  Serial.printf("[ALARM] triggered %s\n", buf);
}

static void startAlarm() {
  logTriggerTimestamp();
  g_phase = ALARM_BEEP_ON;
  g_alarmStartMs = millis();
  g_phaseStartMs = g_alarmStartMs;
  ledcWriteTone(SPEAKER_PIN, ALARM_TONE_HZ);
  displayShowAlarmOverlay(ALARM_HOUR, ALARM_MINUTE);
  Serial.println("[ALARM] beep ON");
}

static void stopAlarm() {
  ledcWriteTone(SPEAKER_PIN, 0);
  g_phase = ALARM_IDLE;
  displayHideAlarmOverlay();
  Serial.println("[ALARM] completed");
}

void alarmTick(int hour, int minute, int yday) {
  if (g_phase == ALARM_IDLE) {
#if ALARM_TEST_MODE
    if (!g_testFired && millis() > ALARM_TEST_TRIGGER_DELAY_MS) {
      g_testFired = true;
      startAlarm();
    }
#else
    time_t nowEpoch = time(nullptr);
    bool timeValid = nowEpoch > ALARM_VALID_EPOCH_THRESHOLD;
    if (timeValid && hour == ALARM_HOUR && minute == ALARM_MINUTE && yday != g_lastAlarmYday) {
      g_lastAlarmYday = yday; // marks today as fired -- prevents retriggering for the rest of this 07:00 minute and the rest of today
      startAlarm();
    }
#endif
    return;
  }

  // ---- Active alarm: non-blocking beep toggle + bounded auto-stop,
  // millis()-based only, never delay(). ----
  unsigned long now = millis();
  if (now - g_alarmStartMs >= ALARM_DURATION_MS) {
    stopAlarm();
    return;
  }

  if (g_phase == ALARM_BEEP_ON && now - g_phaseStartMs >= ALARM_BEEP_ON_MS) {
    ledcWriteTone(SPEAKER_PIN, 0);
    g_phase = ALARM_BEEP_OFF;
    g_phaseStartMs = now;
    Serial.println("[ALARM] beep OFF");
  } else if (g_phase == ALARM_BEEP_OFF && now - g_phaseStartMs >= ALARM_BEEP_OFF_MS) {
    ledcWriteTone(SPEAKER_PIN, ALARM_TONE_HZ);
    g_phase = ALARM_BEEP_ON;
    g_phaseStartMs = now;
    Serial.println("[ALARM] beep ON");
  }
}

bool alarmIsActive() { return g_phase != ALARM_IDLE; }
