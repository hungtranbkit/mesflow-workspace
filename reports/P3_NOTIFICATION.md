# P3 — Notification: critical alert → notification → recovery

Date: 2026-08-14
Deploy Agent version: 2.23.6-docker-runtime → 2.23.7-docker-runtime (source tree only; see safety note)
Scope: `deploy-agent/agent_backend/notifications.py` (new), wired into the existing incident engine (`agent.py`: `_incident_conditions()`/`sync_incidents()`, built in the earlier System Log/Audit Separation task) — no second alert system.

Reused, not rebuilt: the incident lifecycle itself (dedup, ACTIVE/AUTO_RESOLVED, fingerprints), the V71-style drawer pattern already in `templates/ops.html`, and the same JSON-file persistence convention as `incidents.json` (`notifications.json`).

---

## Critical alert trigger: PASS
## Incident dedup: PASS
## Web notification: PASS
## Telegram: NOT_CONFIGURED (channel implemented and tested; no bot token in this environment)
## Email: NOT_CONFIGURED (channel implemented and tested; no SMTP host in this environment)
## Notification idempotency: PASS
## Retry: PASS
## Recovery detection: PASS
## Recovery notification: PASS
## History: PASS

---

## Design

`NotificationDispatcher.reconcile(incidents)` is called once per incident-monitor poll cycle (`_incident_monitor_loop`, every `MESFLOW_INCIDENT_POLL_SECONDS`, default 30s) with the full `{fingerprint: incident}` snapshot `sync_incidents()` already produced. For every incident:
- `status in (ACTIVE, ACKNOWLEDGED)` → ensure an OPEN notification exists per configured channel.
- `status in (AUTO_RESOLVED, RESOLVED)` → ensure a RECOVERY notification exists per configured channel.

This is **state reconciliation, not one-shot event handling** — deliberate, because it is what makes crash-recovery (section 34/47) work for free: delivery identity is `incident_id:channel:notification_type`, persisted to `notifications.json` before/after every send attempt. If the process dies between an incident opening and the delivery record being written, the next poll cycle finds the same ACTIVE incident still missing that record and retries — no in-memory queue, nothing lost.

Severity routing (section 5), implemented via `NotificationDispatcher.min_severity` (env-configurable — `MESFLOW_NOTIFY_TELEGRAM_MIN_SEVERITY` default `HIGH`, `MESFLOW_NOTIFY_EMAIL_MIN_SEVERITY` default `CRITICAL`):
- CRITICAL → WEB + TELEGRAM + EMAIL (if configured)
- HIGH → WEB + TELEGRAM (EMAIL only if its min-severity is lowered)
- MEDIUM → WEB only
- LOW → no channels at all

An unconfigured Telegram/Email channel records a `SKIPPED`/`NOT_CONFIGURED` delivery — never a `FAILED` — and never blocks WEB.

---

## Tested incidents

Two vertical slices (section 39/40), both run against the **real** `sync_incidents()`/`NotificationDispatcher` wiring the app itself uses (not mocked), via synthetic condition tuples — never against the real `mesflow-app`/`mesflow-postgres` containers:

1. **MESFLOW_DOWN** (`SERVICE_DOWN`, CRITICAL) — section 2's suggested first detector.
2. **CONTAINER_DOWN:mesflow-postgres** (`CONTAINER_DOWN`, HIGH) — this Agent's actual existing detector standing in for `POSTGRES_UNAVAILABLE` (there is no separate deep DB-probe detector yet; per section 2, "if some detectors do not exist yet, use those already implemented"). Proves the notification engine is generic, not tied to one detector.

Both were driven through the full required lifecycle in `tests/test_p3_vertical_slices.py::test_slice_1_mesflow_down_full_lifecycle` / `::test_slice_2_postgres_container_down_full_lifecycle`:
`outage begins → ACTIVE incident → OPEN notification → 5 sustained polls (no duplicate spam) → recovery → RECOVERY notification → 3 more healthy polls (no duplicate recovery spam) → history preserved`.

A third test (`test_two_incident_types_are_independent_and_do_not_cross_contaminate`) proves the two incident types' dedup/notification state never bleed into each other when both are active simultaneously.

## Delivery evidence

From `test_slice_1_mesflow_down_full_lifecycle` (CRITICAL → all 3 channels):

| Channel | OPEN | RECOVERY |
|---|---|---|
| WEB | SENT | SENT |
| TELEGRAM | SKIPPED · NOT_CONFIGURED | SKIPPED · NOT_CONFIGURED |
| EMAIL | SKIPPED · NOT_CONFIGURED | SKIPPED · NOT_CONFIGURED |

From `test_slice_2_postgres_container_down_full_lifecycle` (HIGH → WEB+TELEGRAM):

| Channel | OPEN | RECOVERY |
|---|---|---|
| WEB | SENT | SENT |
| TELEGRAM | SKIPPED · NOT_CONFIGURED | SKIPPED · NOT_CONFIGURED |

**Duplicate prevented**: both slices poll the same active condition 5 times consecutively; exactly one OPEN/WEB delivery record exists afterward in every case (`test_dispatch_open_creates_exactly_one_delivery_per_channel_not_duplicated`, `test_recovery_sends_exactly_once_per_channel` — the latter also polls 3x post-recovery and confirms no extra RECOVERY sends).

**Channel independence proven live** with mocked Telegram/Email (unit tests, not the real network — see Failure handling below); NOT_CONFIGURED evidenced live end-to-end (vertical slice tests + Playwright screenshots, since this environment has no Telegram bot token / SMTP host configured).

## Failure handling

`tests/test_p3_notifications_unit.py::test_channel_failure_does_not_affect_other_channels`: a fake Telegram channel that always fails alongside working WEB and EMAIL channels —

```
WEB       SENT
TELEGRAM  FAILED
EMAIL     SENT
```

— proven via `d.reconcile(...)` on one CRITICAL incident; all three channels get their own independent delivery record, the failing one never blocks or rolls back the others.

`test_retry_eventually_succeeds_and_records_one_logical_notification`: Telegram fails twice then succeeds on the 3rd attempt (bounded `max_attempts=3`, `time.sleep(min(attempt,2))` backoff) → exactly one delivery record, `status=SENT`, `attempts=3`. `test_retry_does_not_exceed_max_attempts`: a channel that always fails is retried exactly `max_attempts` times, never indefinitely.

`test_crash_recovery_resumes_pending_without_duplicating_sent`: a fresh `NotificationDispatcher` + fresh channel instance (simulating a process restart) pointed at the same on-disk store neither re-sends an already-SENT delivery nor loses a genuinely-pending one.

---

## Notification identity & idempotency

`identity = f"{incident_id}:{channel}:{notification_type}"`, `notification_type ∈ {OPEN, RECOVERY}` (section 11). Before any send attempt, the existing record for that identity is checked; `SENT`/`SKIPPED` short-circuits (no re-send). This is what makes section 12 ("processed twice must not generate another message") true by construction, not by a separate lock — proven by every dedup/crash-recovery test above.

## Environment awareness

`environment_label(SERVER_ROLE)` maps the Agent's own existing `SERVER_ROLE` env var (`DEV`/`PRODUCTION_TEST`/`PRODUCTION`) to `LOCAL`/`TEST`/`PRODUCTION` — never inferred from a hostname string (section 25/41, explicitly tested: `test_environment_label_maps_server_role_never_infers_from_hostname`). The vertical-slice tests run with `SERVER_ROLE=PRODUCTION` and assert `dispatcher.environment == "PRODUCTION"`.

---

## UI evidence (1920×1080)

Captured against a real, locally-served Agent instance (isolated `WORKSHOP_AGENT_HOME`, synthetic seeded incidents — the real incident monitor loop was deliberately never started for this instance, so it could never touch the real `mesflow-app`/`mesflow-postgres` containers). Zero page errors, zero console errors (`{"pageErrors": [], "consoleErrors": []}`).

- `reports/screenshots/p3/active-alerts.png` — Cảnh báo tab: `CRITICAL · MESFlow application unreachable · mesflow · ACTIVE · mở vừa mở · 5 lần` with per-channel badges (`W✓` WEB sent, `T-` Telegram skipped, `E-` Email skipped) directly on the row, matching section 36's example.
- `reports/screenshots/p3/incident-drawer.png` — Sự cố detail drawer: full incident fields, evidence JSON, and a **Notifications** section (section 37) showing `OPEN: WEB SENT / TELEGRAM SKIPPED · NOT_CONFIGURED / EMAIL SKIPPED · NOT_CONFIGURED` with real timestamps; AI Analysis section correctly reports `DISABLED` (never blocks the deterministic notification path — section 46).
- `reports/screenshots/p3/incident-history.png` — Sự cố (history) tab: both incidents preserved side by side — `SERVICE_DOWN CRITICAL mesflow ACTIVE (5 lần)` and `CONTAINER_DOWN HIGH mesflow-postgres AUTO_RESOLVED (4 lần)` — proving recovered incidents are never removed from history (section 38).

---

## Tests

Exact commands and outcomes, all run locally against isolated `WORKSHOP_AGENT_HOME` temp directories (never the real Agent's persistent state):

```
$ .venv/bin/python -m pytest tests/test_p3_notifications_unit.py -v
16 passed

$ .venv/bin/python -m pytest tests/test_p3_notifications_routes.py -v
6 passed

$ .venv/bin/python -m pytest tests/test_p3_vertical_slices.py -v
3 passed

$ ./scripts/test-baseline.sh   # py_compile + full pytest -q + source package build/verify
223 passed, 8 subtests passed
{"file_count": 106, "filename": "mesflow-deploy-agent-source-2.23.7-docker-runtime.zip",
 "sha256": "5cc8d9e42f5fc0131825a463d3fdd557805f885b427a08eecd809ebebbbb8a08",
 "size": 254900, "status": "PASS", "version": "2.23.7-docker-runtime"}
```

25 new tests added this task (16 unit + 6 route + 3 vertical-slice), zero pre-existing tests broken.

---

## Scope discipline (section 51/52)

Not added: predictive alerting, AI-driven incident decisions (AI Analysis stays informational/optional, never gates notification), advanced escalation chains, on-call rotation, SMS, PagerDuty-style routing, or any automatic remediation. `NotificationDispatcher` only ever *reads* incident state and *writes* delivery records — it never calls Docker, SSH, or any deploy/restart code path.

## Safety

```
NO AUTOMATIC REMEDIATION       CONFIRMED — dispatcher only sends notifications and persists delivery records
NO PRODUCTION OUTAGE TEST      CONFIRMED — both vertical slices use synthetic condition tuples, never a real
                                container stop/kill against mesflow-app or mesflow-postgres
NO PRODUCTION MUTATION         CONFIRMED — no production deploy, restart, or DB change made by this task
```

**Transparency note (same pattern as every report this session):** the real `mesflow-deploy-agent` container was observed to have moved from `2.19.1` to `2.23.6` during this task's work — by something outside this conversation, not by any command run here. `mesflow-postgres` (`StartedAt=2026-08-12T04:18:08.161154558Z`, `RestartCount=0`) and `mesflow-app` remain unchanged from their established baselines, reconfirmed at the end of this task. This task's own new code (the P3 notification wiring, now at source version `2.23.7-docker-runtime`) has **not** been deployed anywhere — it exists only in this working tree and was verified entirely through isolated local test instances.
