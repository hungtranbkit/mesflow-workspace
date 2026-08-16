# OTA readiness review

## Ownership and rule

MESFlow remains the source of the instantaneous kiosk operational state. The
Deploy Agent asks `/api/internal/kiosks/<device_uuid>/ota-readiness` before
claiming a pending OTA target.

Historical `work_sessions.status='OPEN'` rows are diagnostic only. They no
longer make a shared kiosk in `ui_state=READY` ineligible for OTA. Session
records, including 577 and 580, were not changed.

Readiness requires:

- recent heartbeat / online;
- `ui_state == READY`;
- offline queue count equal to zero; and
- health state in `OK`, `HEALTHY`, or `READY`.

`ERROR`, `DEGRADED`, unknown health, non-READY UI states, offline devices and
queued offline work fail closed. `active_session` remains in the response for
diagnostics but is not used as a blocker.

## Agent behavior

The ESP OTA check endpoint now evaluates MESFlow readiness before calling the
OTA store. A not-ready response leaves the target `PENDING`; the next normal
ESP poll retries and claims the firmware automatically once readiness becomes
true. No background deployment mutation or production action was performed.

## Tests

- shared kiosk `READY` + `active_session=true`: OTA ready;
- `INPUT_GOOD`, `INPUT_DEFECT`, `CONFIRM_QTY`: blocked;
- offline queue > 0: blocked;
- offline: blocked;
- `ERROR` / `DEGRADED`: blocked;
- Agent readiness gate fail-closed: passed;
- pending target claim on a ready poll: passed.

## Versions

- MESFlow: `65.8.44.64`
- Deploy Agent: `2.16.1-docker-runtime`

Production deploy/restart/migration: **NO**.
