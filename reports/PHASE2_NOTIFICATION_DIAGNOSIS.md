# MESFlow — Phase 2: Notification + Diagnosis

Built on top of Phase 1's Active Alerts engine (`reports/PHASE1_HEALTH_CENTER.md`).

## RESULT

```
Threshold engine           PASS
Sustained threshold        PARTIAL (see Known gaps -- no time-series duration tracking)
Dedup                      PASS
Recovery detection         PASS
Recovery notification      PASS
Diagnostics                PASS
Logs                       PASS
Web notifications          PASS
Email notifications        NOT_CONFIGURED (implemented + unit tested; no SMTP server in this environment)
Telegram notifications     NOT_CONFIGURED (implemented + unit tested; no bot token in this environment)
Incident history            PASS
```

## Core flow (implemented exactly as specified)

```
Health Signal (Phase 1 provider results)
  -> Threshold evaluation (mesflow.core.config health_* thresholds, unchanged from Phase 1)
    -> Alert fingerprint / dedup (health_alerts, unique-open-fingerprint index)
      -> Alert opened (INSERT ... ON CONFLICT ... RETURNING (xmax=0) -- detects
         the exact "just inserted" edge, not just "still exists")
        -> Notification (NotificationDispatcher: WEB always, EMAIL/TELEGRAM
           per severity routing) -- fires ONLY on that edge, never on every poll
          -> Diagnostics snapshot (DiagnosticService, SUMMARY level, captured
             automatically, linked to the alert's fingerprint)
            -> Recovery detected (UPDATE ... RETURNING catches the exact
               "just resolved" edge)
              -> Recovery notification (event_type=RESOLVED, same dispatcher)
                -> Incident closed / history preserved (component_health_history
                   + health_alerts open+resolve rows, merged in /history)
```

## Alert types implemented

`COMPONENT_DOWN:MESFLOW`, `COMPONENT_DOWN:POSTGRESQL`, `COMPONENT_DOWN:SERVER`
(all CRITICAL), `COMPONENT_DOWN:DEPLOY_AGENT` (HIGH), `QA_LATEST_FAILED`
(MEDIUM), `DISK_USAGE_HIGH` (MEDIUM at warning / HIGH at critical threshold),
`KIOSK_OFFLINE:<device_uuid>` (HIGH, one per device), `JOB_FAILED:<job>` /
`JOB_MISSED:<job>` (MEDIUM). `DOCKER_UNHEALTHY`/`RAM_HIGH`/`CPU_HIGH` are not
yet wired as alert conditions (component-level DEGRADED already reflects
them on the Server/Docker cards; promoting them to named alerts is a small,
mechanical follow-up using the exact same `_alert_conditions()` pattern).

## Threshold configuration (centralized, `mesflow.core.config`)

```
health_cpu_warning_percent=75          health_cpu_critical_percent=90
health_ram_warning_percent=80          health_ram_critical_percent=90
health_disk_warning_percent=80         health_disk_critical_percent=90
health_kiosk_degraded_seconds=120      health_kiosk_offline_seconds=300
health_db_latency_warning_ms=250       health_deploy_agent_stale_seconds=60
notify_email_min_severity=HIGH         notify_telegram_min_severity=HIGH
notification_timeout_seconds=5         notification_retry_attempts=3
```

## Dedup fingerprints

`COMPONENT_DOWN:<component>`, `KIOSK_OFFLINE:<device_uuid>`,
`QA_LATEST_FAILED`, `DISK_USAGE_HIGH`, `JOB_FAILED:<job_name>` /
`JOB_MISSED:<job_name>`. Enforced at the database level via
`CREATE UNIQUE INDEX uq_health_alerts_open_fingerprint ON health_alerts(fingerprint) WHERE resolved_at IS NULL`
-- a second poll with the same condition is a plain `UPDATE last_seen_at`,
never a second row. Notification-level dedup is a second, independent
guard: `NotificationDispatcher.dispatch()` checks
`notification_deliveries` for an existing SENT/SKIPPED row with the same
`(fingerprint, event_type, channel)` before attempting again, so even a
retried/duplicated `sync_alerts()` call cannot double-notify.

## Retry / cooldown behavior

EMAIL/TELEGRAM: up to `notification_retry_attempts` (default 3) with a
short bounded sleep between attempts, stopping early on SENT/SKIPPED --
never indefinite. WEB: a single attempt (a plain, deterministic DB insert;
a genuine failure there means the whole request already failed). Cooldown
for "still active" conditions is implicit: since notifications only fire
on the newly-opened/newly-resolved edge (not on every poll), there is no
repeat notification for an alert that simply continues -- satisfying the
spec's minimum bar ("one notification per newly opened incident, plus
recovery") without a separate reminder/escalation timer in this phase.

## Diagnostic providers

`DiagnosticService`: `MESFLOW` (recent `action_logs` errors + version),
`POSTGRESQL` (connectivity + latency + connection count + migration
revision; DETAIL adds ungranted lock rows), `SERVER`/`DOCKER`/`DEPLOY_AGENT`
(reuses the same Deploy Agent `/health` + `/api/ops/summary` fetch as
Phase 1's providers; DETAIL additionally calls `/api/ops/docker` for the
per-container list), `QA_CENTER` (reachability + latest run), `KIOSK_FLEET`
(recent ERROR/CRITICAL kiosk_events). Every provider is wrapped in a
try/except that returns `{"error":..., "partial":true}` instead of
raising -- a broken diagnostic never fails the incident drawer or changes
health state (section 22/58). SUMMARY is captured automatically the
instant an alert opens; DETAIL is admin-only, on-demand ("Run diagnostics
again"), and recorded with `requested_by_user_id`.

## Allowed log sources

`mesflow` (MESFlow application, `docker logs`), `postgres` (PostgreSQL,
`docker logs`), `qa` (QA Center, `journalctl`), `agent` (Deploy Agent,
`journalctl`) -- a fixed dict on both ends: Deploy Agent's own
pre-existing allowlist (`agent.py::api_ops_logs`, unchanged) and MESFlow's
own re-validation (`LogService.LOG_SOURCES`) before proxying, so a
compromised/buggy frontend still cannot smuggle an arbitrary path through.
Bounded to 20-1000 lines (default 200). Secret redaction
(`sanitize_log_text`) strips the remainder of any line containing
password/token/authorization/cookie/secret/api_key. Admin-only
(`GET /api/system-health/logs`, 403 for non-admin roles).

## Notification channels

- **WEB**: reuses the pre-existing `notifications` table and its
  `UNIQUE(source_type, source_id)` constraint for dedup -- zero new
  storage for this channel. Recovery gets its own `source_id`
  (`<fingerprint>#resolved`) so it never overwrites/erases the original
  detection notification (section 11).
- **EMAIL**: `smtplib`, config via `MESFLOW_SMTP_HOST/PORT/USER/PASSWORD/
  FROM/TO/USE_TLS`. `NOT_CONFIGURED` (not DOWN) when `smtp_host` is unset.
- **TELEGRAM**: Bot API over HTTPS, config via
  `MESFLOW_TELEGRAM_BOT_TOKEN/CHAT_ID`. `NOT_CONFIGURED` when unset.
- Delivery audit: every attempt (including WEB) recorded in
  `notification_deliveries` (channel, status PENDING/SENT/FAILED/SKIPPED,
  attempted_at, delivered_at, error, correlation_id).
- Test send: `POST /api/system-health/notification-channels/<channel>/test`
  (admin-only), a clearly-labelled "MESFlow notification test" message,
  never a fabricated real incident, recorded with `event_type='TEST'`.

## API

```
GET  /api/system-health/alerts/<id>/diagnostics    -- latest snapshot (auto-captures SUMMARY if none exists)
POST /api/system-health/alerts/<id>/diagnostics    -- admin-only, forces a fresh DETAIL snapshot
GET  /api/system-health/alerts/<id>/notifications  -- delivery history for that alert
GET  /api/system-health/logs?source=&lines=        -- admin-only, allowlisted, bounded
GET  /api/system-health/notification-channels      -- WEB/EMAIL/TELEGRAM configured true/false
POST /api/system-health/notification-channels/<channel>/test  -- admin-only
```
(Deliberately smaller than the spec's own suggested list -- section 51's
own guidance -- e.g. no separate `/api/notifications` since that already
exists and is reused as-is.)

## Migration

`0035_v69c_notifications_diagnostics`,
`down_revision=0034_v69b_health_alerts`. Additive only:
`CREATE TABLE notification_deliveries`, `CREATE TABLE
health_diagnostics_snapshots`, plus supporting indexes. No table dropped,
no column changed.

## Testing

Same isolated `-p mesflow-p2` Compose project as Phase 1 (kept separate
from both the shared `compose.test.yml` project another session was
actively using, and from production).

- **8 unit tests** (`test_v69d_phase2_notifications_unit.py`): severity
  routing math, EMAIL/TELEGRAM `configured()` true/false, WEB always
  configured, log-source allowlist rejects unknown/path-traversal input,
  secret redaction, dispatcher's per-severity channel plan.
- **5 integration tests** (`test_v69d_phase2_notifications.py`), the
  required Phase 2 vertical slice (section 61) run against real PostgreSQL
  + real HTTP: a stale kiosk heartbeat crosses the offline threshold ->
  exactly one `health_alerts` row opens -> exactly one WEB notification
  row is created -> exactly one `notification_deliveries` SENT row for
  that transition -> a diagnostic snapshot is captured automatically ->
  a second poll with the same condition creates **zero** additional alert
  rows and **zero** additional WEB deliveries (dedup proven, not assumed)
  -> the alert's diagnostics/notifications are retrievable via their own
  endpoints -> a fresh heartbeat recovers the kiosk -> the alert resolves
  -> a recovery WEB notification fires -> Incident History contains both
  the ALERT_OPENED and ALERT_RESOLVED events. Plus: notification-channels
  status endpoint reports EMAIL/TELEGRAM as unconfigured; the email test
  endpoint returns SKIPPED/NOT_CONFIGURED (not a fabricated SENT); the
  logs endpoint rejects a path-traversal-style source and is forbidden for
  a non-admin (`manager`) role.
- **Three real bugs found and fixed while running these tests** (all in
  code/tests written this session, not pre-existing):
  1. A hardcoded expected-migration-revision string in `PostgreSQLProvider`
     that I forgot to bump after adding this phase's own migration.
  2. `GET /api/system-health/logs` returned **HTTP 500** for an unknown log
     source -- `jsonify(ok=False, **result)` where `result` already
     contained its own `"ok"` key raised a duplicate-keyword `TypeError`.
     Fixed by not re-passing `ok=` when the dict already carries it.
  3. My own test's expectation for the "not configured" test-send response
     shape didn't match the actual (more consistent) `SKIPPED` + `error`
     representation the dispatcher uses; fixed the test, not the code.
- **Deploy Agent regression**: full suite, **133/133 passed** after adding
  the same internal-token gate to `/api/ops/docker` and `/api/ops/logs`.

## Known gaps

- **Sustained-threshold/duration evaluation** (section 3) is not
  implemented -- `SERVER`'s CPU/RAM/Disk read is a single point-in-time
  sample per poll (matching Deploy Agent's own `ops_summary()`), so a
  5-second CPU spike and a 5-minute sustained CPU spike currently produce
  the same DEGRADED signal. The spec explicitly allows documenting this
  limitation rather than building time-series sampling in this phase.
- **Hysteresis** (open at 85%, recover at 80%) is not implemented --
  recovery uses the same warning threshold as opening. A condition
  hovering exactly at the threshold could flap open/closed across polls.
  Worth a small follow-up (a `recovery_percent` offset per threshold).
- **Severity escalation** (DEGRADED->DOWN re-notifying) is not
  implemented -- the alert's fields are updated (`severity=EXCLUDED.severity`
  on the upsert) but no additional notification fires solely because
  severity changed while the alert was already open.
- **Web notification badge/unread-count UI** (section 42) was not built --
  the pre-existing `GET /api/notifications` list page already gives
  read/unread state; a nav-bar badge is a small, separate frontend
  addition, not started this session.
- Email/Telegram were exercised via unit tests and the NOT_CONFIGURED path
  only -- no real SMTP server or Telegram bot token was available in this
  environment to prove an actual SENT delivery end to end.
- The updated Deploy Agent source (`/api/ops/docker`, `/api/ops/logs`
  token gates) is implemented and tested via a throwaway build, same
  caveat as Phase 1: **not yet deployed to the real running Deploy Agent
  container.**

## NO AUTOMATIC REMEDIATION

Confirmed. Every new code path in this phase is read-only: diagnostics
only read (Deploy Agent GET endpoints, PostgreSQL SELECTs, action_logs
SELECTs); notifications only send messages; nothing in this phase issues a
restart, deploy, migration, or any Docker/systemd mutation. No command
textbox or arbitrary-command path was introduced.

## NO PRODUCTION MUTATION

Confirmed. All work built/tested against the same isolated,
disposable `-p mesflow-p2` Compose project as Phase 1, torn down at the
end. `mesflow-postgres`'s `StartedAt` remained byte-for-byte unchanged
throughout. The real `mesflow-deploy-agent` container was not redeployed.
