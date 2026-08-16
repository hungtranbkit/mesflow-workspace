# ESP OTA Incident Report

**Date:** 2026-08-12 (Asia/Ho_Chi_Minh)  
**Environment:** `mesflow-test` only; no production mutation  
**Device:** `055cc508-f8f7-4865-a850-3a5542b81f1f`

## Result

**PASS — real OTA completed end-to-end.**

Evidence from the final clean job:

| Item | Evidence |
|---|---|
| Job | `42b0fea0-60e3-4a73-bb76-a176ecde6d4c` |
| Current before OTA | `ESP32-KIOSK-5.5.0-KIMEX-OTA-DEFAULT` |
| Target | `5.5.1`, build `20260812.3115` |
| Artifact | `ed803d55-be75-4031-ac16-7ee237db57ef` |
| SHA256 | `13f6706c591e6d624e79ab3f02d4a1e63a420cdbd1b5af243903ef5f0bf3494d` |
| Size | `1,374,400` bytes |
| Agent events | `OTA_CHECK → OTA_AVAILABLE → DOWNLOADING → FLASHING → REBOOTING → SUCCESS` |
| Physical ESP after reboot | `ESP32-KIOSK-5.5.1-KIMEX-OTA-DEFAULT`, UI `READY`, HTTP `201` |
| Final Agent state | Job `SUCCESS`, target `SUCCESS`, empty error |

The physical device was rebooted through its authenticated maintenance console to trigger the existing old-firmware polling interval. No USB flash was used.

## Root causes found from runtime evidence

1. **MESFlow readiness was stale in deployed test.** MESFlow `65.8.44.63` returned `ota_ready=false, reason=ACTIVE_SESSION` while the kiosk was `ui_state=READY`, online, healthy and queue `0`. This was the historical OPEN-session blocker. MESFlow `65.8.44.64` was deployed to test and then returned `ota_ready=true, reason=READY`; Sessions 577/580 were not changed.
2. **Agent OTA event schema drift.** Existing `ota_events` had the earlier Phase-2 columns and no `job_id`/`error`; event POSTs raised `sqlite3.OperationalError`, producing HTTP 500 and leaving targets stuck in `DOWNLOADING`.
3. **Download URL used the internal HTTP scheme.** ESP correctly rejected it with `OTA_HTTP_ERROR` because firmware requires HTTPS.
4. **Download URL did not include `kiosk_id`.** Agent’s device resolver requires both kiosk ID and device token; the request reached Agent as `auth_missing`.
5. **Artifact column-name drift.** Existing artifact rows use `size`; the route assumed `file_size`, causing a runtime `KeyError` and HTTP 500.

## Fixes

- MESFlow readiness uses instantaneous device safety (`online`, `ui_state=READY`, health, queue, transaction state) and keeps historical `active_session` diagnostic-only.
- Agent performs in-place additive compatibility migration for `ota_events.job_id` and `ota_events.error`.
- Agent download URL uses configured/public HTTPS origin (or forwarded HTTPS / mesflow.net HTTPS fallback).
- Download URL includes the assigned `kiosk_id` (no secret in URL).
- Agent download route accepts both legacy `file_size` and current `size` artifact schemas.
- Cancel endpoint is exempted from the login-only request guard so the configured Agent admin token can cancel stale jobs.
- Agent version bumped to `2.16.2-docker-runtime` for the incident fix.

## Runtime checks

Final MESFlow readiness response included:

```json
{"active_session":true,"online":true,"ui_state":"READY",
 "health_state":"OK","offline_queue_count":0,"ota_ready":true,
 "reason":"READY"}
```

Final physical health endpoint reported firmware `5.5.1`, Wi-Fi connected, bound kiosk identity, queue `0`, health score `100`, and UI `READY`.

## Tests and evidence

- `python3 -m py_compile deploy-agent/ota_control.py deploy-agent/agent.py` — PASS.
- Deploy Agent focused tests: `6 passed`.
- MESFlow readiness tests: `3 passed` during the readiness fix.
- Test deployment: Agent health/version `2.16.2-docker-runtime`, MESFlow `65.8.44.64` healthy.
- Real device flow: check, firmware assignment, HTTPS download, SHA/size verification, flash, reboot, new heartbeat/version, Agent SUCCESS.

## Files changed

- `mesflow/app/mesflow/core/ota_readiness.py`
- `mesflow/app/mesflow/web/internal_ota.py`
- `mesflow/tests/test_internal_ota_readiness.py`
- `deploy-agent/ota_control.py`
- `deploy-agent/agent.py`
- `deploy-agent/VERSION.txt`
- `reports/ESP_OTA_INCIDENT.md`

## Final state

- `JOB_FINAL_STATE: SUCCESS`
- `POST_REBOOT_VERSION: 5.5.1`
- `SESSION_577_580: unchanged`
- `PRODUCTION_ACTION_REQUIRED: NO`
- `PRODUCTION_MUTATED: NO`

