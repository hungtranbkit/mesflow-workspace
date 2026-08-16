# ESP Kiosk UI audit

## Result

The visual harness rendered and checked all 33 debug framebuffer fixtures. The
live device framebuffer was inspected through the ESP debug endpoint and the
contact sheet was reviewed manually. The firmware source also contains a
recovery fix so the error screen can be dismissed by a short tap or by the next
employee-card scan.

## Evidence

| Item | Result |
|---|---|
| Source firmware version | `5.5.0` / build `20260812.3045` |
| Live framebuffer version | `ESP32-KIOSK-5.4.8-KIMEX-OTA-DEFAULT` |
| Resolution / orientation | `240x320`, portrait |
| Screens discovered / tested | `33 / 33` |
| Automated renderer result | `33/33 PASS` |
| Playwright visual tests | `33 passed` |
| Firmware compile | `PASS` |
| Flash | `NO` |

The live capture is intentionally from the currently running ESP. The source
5.5.0 recovery change has not been flashed in this task, so that behavior still
needs a later hardware verification.

## Findings

- P0: none observed in the reviewed contact sheet.
- P1: none observed in the reviewed contact sheet. Long employee/operation
  fixtures fit within the 240-pixel framebuffer; the deliberate duplicate-pixel
  aliases are expected debug fixtures, not missing screens.
- P2: the visual audit now reports same-pixel aliases as warnings instead of
  false failures. The source renderer was also fixed to mirror `fillScreen()`
  into the shadow framebuffer, preventing stale screenshots in the harness.

The automated edge heuristic reported no text overflow/clipping failures. It
reported edge content for one numeric offline fixture; this is expected large
quantity content touching the intended drawing area and remains visible in the
manual contact-sheet review.

## Recovery fix

`esp/mesflow_app.cpp` now:

1. treats the error footer as a normal short-tap target and returns to the
   employee-card scan screen;
2. dismisses `ERROR_STATE` before processing a new input, allowing an employee
   QR scan to continue directly into the normal lookup path; and
3. retains the existing keypad/hold/watchdog recovery paths.

This does not change scanner mapping, keypad mapping, session business rules or
API contracts.

## Generated artifacts

- Screenshots: `artifacts/esp-kiosk/ui-audit/`
- Contact sheet: `artifacts/esp-kiosk/ui-audit/contact-sheet.png`
- Machine report: `artifacts/esp-kiosk/ui-audit/report.json`
- Harness report: `artifacts/esp-kiosk/ui-audit/report.md`
- Playwright screenshots: `artifacts/esp-kiosk/ui-audit/playwright/`

The reusable command is:

```bash
cd /home/dell/workspace/mesflow/esp-kiosk
./scripts/audit-ui.sh
```

It compiles the real sketch, captures the ESP framebuffer, serves the real PNG
captures at `/esp-ui-test?state=<state>`, runs Playwright, and writes the
reports above.

## Remaining verification

Flash is deliberately not performed. After the new binary is approved, flash
only the explicitly selected ESP and inspect its serial boot log/version before
using it for an OTA test.

Production action required: **NO**.
