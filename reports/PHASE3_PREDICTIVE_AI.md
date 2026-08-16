# MESFlow — Phase 3: Predictive / AI

Built on top of Phase 1 (Health Center) and Phase 2 (Notification +
Diagnosis). Both required vertical slices (section 83/84) were
implemented and tested: **Disk Capacity Risk** and **KIOSK recurring
offline**.

## RESULT

```
Disk forecast                 PASS
DB growth                     PASS
Recurring failure detection   PASS
Anomaly detection             PASS
AI incident summary           PASS (structured pipeline) / DISABLED (no live provider in this environment)
Suggested remediation         PASS (structured, advisory-only) / DISABLED (depends on AI being enabled)
```

`DISABLED` here means exactly what section 25/29 intends: AI is fully
optional and off by default (`MESFLOW_AI_ENABLED=0`, no API key
configured in this environment). The pipeline around it — provider
abstraction, structured-output validation, sanitization, bounded context,
caching, safety — is implemented and tested with a mocked provider
(section 80); it was never exercised against a real external LLM in this
session because no API key/network access to one was available/authorized
here.

## Data

**Metrics collected** (`health_metric_samples`, one lean table per
section 46, not a per-metric table): `DISK_USAGE_PERCENT`,
`DISK_USED_BYTES`, `CPU_PERCENT`, `RAM_PERCENT` (all from Deploy Agent's
existing `/api/ops/summary`, reused via Phase 1's `DeployAgentFetch` — no
second privileged probe), `DB_SIZE_BYTES` + `DB_LATENCY_MS` +
`DB_TOP_TABLES` (top-5 by `pg_total_relation_size`, a single cheap catalog
query, sampled at the same slow interval, never on drawer open).

**Sampling interval**: one collection pass per invocation of the new
`mesflow.cli run-predictive` command (section 4's own "use configurable
intervals" — interval is whatever the external cron/scheduler that invokes
this CLI command is configured to run at; `scheduled_job_health.
expected_interval_seconds=900` for `predictive_metrics_collection`
documents the intended 15-minute cadence, matching the spec's own
5-15 min suggestion for disk).

**Retention**: `MetricsCollector.cleanup()` deletes samples older than
`MESFLOW_METRIC_SAMPLE_RETENTION_DAYS` (default 14 days), run as part of
the same `run-predictive` job. **Hourly/daily aggregation tiers (section
47) are not implemented** — see Known gaps.

**Baseline requirements** (section 54): forecasts require
`predictive_forecast_min_samples=6` and a span of
`predictive_forecast_min_span_hours=24`; anomaly detection requires
`predictive_anomaly_min_samples=20`; recurrence requires
`predictive_recurrence_min_count=3` incidents in
`predictive_recurrence_window_days=7`. Below these bars, the service
returns `available=False`/`confidence=INSUFFICIENT_DATA` — proven by test
(`test_disk_forecast_insufficient_data_when_no_samples`), not just
documented.

## Prediction (deterministic — no ML libraries)

**Forecast algorithm**: ordinary least-squares linear regression, pure
Python (`mesflow.domain.predictive.linear_regression`, no numpy/pandas/
sklearn dependency added). `growth_per_day` = slope; `days_to_warning`/
`days_to_critical` = `(threshold - current) / slope` when slope > 0.
**Confidence rule**: HIGH if R²≥0.7 and ≥20 samples; MEDIUM if R²≥0.4;
else LOW; INSUFFICIENT_DATA below the sample/span floor. **Risk banding**
(section 71, configurable): `<7 days`→HIGH, `<14`→MEDIUM, `<30`→LOW, else
INFO (`MESFLOW_PREDICTIVE_RISK_*_DAYS`).

**Anomaly algorithm**: robust baseline via Median Absolute Deviation
(falls back to stdev when MAD=0), z-score-style deviation against that
baseline, flagged when `|deviation| >= MESFLOW_PREDICTIVE_ANOMALY_ZSCORE_
THRESHOLD` (default 3). A separate rate-based check
(`AnomalyService.db_growth_anomaly`) compares recent-window DB growth
against the typical daily rate scaled to that window (section 12's own
example), not a point z-score — a sudden 2-hour burst would be smeared out
by a whole-history z-score but is caught by this dedicated check.

**Recurrence scoring**: deterministic fingerprint grouping over
`health_alerts` (reusing Phase 2's exact fingerprints — no semantic AI
grouping, section 15). `risk`: HIGH if ≥10 incidents or (increasing trend
and ≥2× the minimum count); MEDIUM if ≥5; else LOW. `trend`: compares
first-half vs second-half incident counts within the window
(increasing/stable/decreasing). `time_pattern`: dominant hour-of-day when
it covers ≥50% of incidents (section 17's "every night around 02:00"
example, computed, not guessed).

**Lifecycle**: `predictive_insights` mirrors Phase 2's `health_alerts`
exactly — one ACTIVE row per fingerprint (partial unique index), condition
no longer present → `status=CLEARED, cleared_at=now()` — proven by test
(`test_predictive_insight_lifecycle_active_then_cleared`), not just
implemented.

## AI

**Provider abstraction**: `AIProvider` (ABC-like) → `DisabledAIProvider`
(default, `available()` always False) → `AnthropicAIProvider` (single
bounded `urllib` POST to the Anthropic Messages API, no SDK dependency,
gated by `MESFLOW_AI_ENABLED=1` + `MESFLOW_AI_PROVIDER=anthropic` +
`MESFLOW_AI_API_KEY`). Tests inject a third, `_FakeProvider` (section 80)
so the whole pipeline (validation/caching/persistence) is exercised
without ever calling a real network endpoint.

**Model/config**: `MESFLOW_AI_MODEL` (default `claude-haiku-4-5`),
`MESFLOW_AI_TIMEOUT_SECONDS=15`, `MESFLOW_AI_MAX_CONTEXT_CHARS=8000`.

**Sanitization**: `build_context()` reuses Phase 2's own
`sanitize_log_text` (password/token/authorization/cookie/secret/api_key
redaction) and truncates to `ai_max_context_chars` — proven by test
(secrets injected into a fake diagnostic snapshot do not appear in the
built context).

**Context limits**: alert metadata + latest diagnostic snapshot (JSON,
capped at 3000 chars) + up to 10 similar past incidents' timestamps —
never raw multi-GB logs, never full stack traces.

**Structured response schema** (enforced, section 25/59):
```json
{"summary":"string","evidence":["..."],"likely_causes":["..."],
 "uncertainties":["..."],"suggested_checks":[
   {"action":"...","risk":"SAFE_CHECK|LOW_RISK_ACTION|HIGH_RISK_ACTION","reason":"..."}]}
```
Missing fields, malformed JSON, or a wrong field type → `INVALID_OUTPUT`
(never rendered as trusted text). An unrecognized/invented `risk` label is
silently clamped to `SAFE_CHECK` server-side — proven by test
(`test_validate_structured_clamps_unknown_risk_label_to_safe_check`).
Statuses: `SUCCESS | FAILED | INVALID_OUTPUT | TIMEOUT | DISABLED`.

**Cache behavior**: keyed on `(alert_fingerprint, incident_stage,
context_hash)` — `ai_incident_analyses` table. Re-opening the same
incident with unchanged evidence returns the cached row (zero extra
provider calls); an explicit `POST .../regenerate` (admin-only, records
`requested_by_user_id`) bypasses the cache — proven by test
(`test_ai_analysis_cache_avoids_regenerating_for_same_context`, asserting
the mocked provider was called exactly once, then twice after `force`).

## Safety

```
AI HAS NO DIRECT INFRASTRUCTURE EXECUTION PATH  -- confirmed
NO AUTOMATIC RESTART                             -- confirmed
NO AUTOMATIC DEPLOY                              -- confirmed
NO AUTOMATIC DATABASE ACTION                     -- confirmed
NO AUTOMATIC DOCKER CLEANUP                      -- confirmed
NO AUTOMATIC REBOOT                              -- confirmed
```

`mesflow.services.ai_incident_service` contains no `subprocess`,
`os.system`, `eval`/`exec`, and no import of anything that calls Deploy
Agent's mutation endpoints — asserted structurally by test
(`test_ai_service_never_executes_anything_from_ai_output`), not just
claimed. The AI response is used exclusively to populate JSON fields
rendered as text in the Incident Drawer; `suggested_checks[].risk` is a
label only, never wired to a button that executes anything — the frontend
only ever calls the existing safe `[View Logs]`/`[Open Kiosk]`-style
navigation (section 64), and no new command-execution UI was added.
Diagnostics remain 100% read-only (unchanged from Phase 2). Core Health
Center (current status, Active Alerts, notifications, recovery) has zero
dependency on AI or on any Phase 3 service being reachable — proven by
`summary()` wrapping the predictive read in try/except, defaulting to an
empty list on any failure.

## Files changed

- New: `app/migrations/versions/0036_v69f_predictive.py`
- New: `app/mesflow/domain/predictive.py`, `app/mesflow/services/{metrics,forecast,anomaly,recurrence,predictive,ai_incident}_service.py`
- Modified: `app/mesflow/core/config.py` (Phase 3 thresholds/AI config),
  `app/mesflow/services/system_health_service.py` (predictions in
  `summary()`; fixed the recurring hardcoded-migration-revision bug by
  deriving it dynamically from the migrations directory instead — see
  Known gaps in the Phase 1 report, now resolved), `app/mesflow/cli.py`
  (`run-predictive` command), `app/mesflow/web/system_health.py` (6 new
  routes), `app/mesflow/web/static/pages/system-health.js` (Predictive
  Insights section, prediction drawer, AI Analysis panel in the alert
  drawer), `app/mesflow/web/static/ui.css`
- Modified: `deploy-agent/agent.py` (raw `used_bytes`/`total_bytes`/
  `free_bytes` added alongside the existing human-formatted disk/RAM
  fields in `/api/ops/summary` — Phase 3 forecast math needs real numbers,
  not "3.2 GB")
- Tests: `tests/test_v69g_phase3_predictive_unit.py`,
  `tests/integration/test_v69g_phase3_predictive.py`, plus small fixes to
  the pre-existing `tests/test_v69_system_health_unit.py` /
  `tests/integration/test_v69_system_health.py` (migration-revision
  assertion updated to compare against itself instead of a literal)

## API

```
GET  /api/system-health/predictions              -- top active insights (also embedded in the main summary)
GET  /api/system-health/recurring-incidents       -- full recurrence list
GET  /api/system-health/metrics/<metric>/trend    -- admin-only, raw samples for a drawer chart
GET  /api/system-health/alerts/<id>/ai-analysis           -- cached-or-fresh AI summary
POST /api/system-health/alerts/<id>/ai-analysis/regenerate -- admin-only, forces re-analysis
```
(Anomalies are not a separate endpoint -- they surface through
`/predictions` as `category=ANOMALY`, per section 56's own "do not create
unnecessary APIs" guidance.)

## Migration

`0036_v69f_predictive`, `down_revision=0035_v69c_notifications_diagnostics`.
Additive only: `health_metric_samples`, `predictive_insights`,
`ai_incident_analyses`, plus a seed row in the pre-existing
`scheduled_job_health` table. No table dropped, no column changed.

## Tests actually executed

Isolated `-p mesflow-p3` Compose project (separate from both production
and any other session), torn down at the end.

- **13 unit tests** (`test_v69g_phase3_predictive_unit.py`): linear
  regression correctness (perfect line, flat line, <2 points), MAD
  robustness to an outlier, risk-band thresholds, AI structured-output
  validation (well-formed / missing fields / garbage / unknown risk label
  clamped / fenced-JSON-block tolerance), context sanitization/bounding,
  and the "no execution path" structural safety test.
- **14 integration tests** (`test_v69g_phase3_predictive.py`, real
  PostgreSQL + real HTTP): disk forecast insufficient-data / linear-growth
  / outlier-does-not-crash; DB growth forecast; anomaly detection
  (baseline noise → not detected, injected spike → detected); recurrence
  (1 incident → not recurring, 5 → recurring with correct count);
  predictive-insight ACTIVE→CLEARED lifecycle; `/predictions` and
  `/recurring-incidents` endpoints; `/metrics/.../trend` admin-only
  enforcement; AI analysis DISABLED-by-default via the real endpoint;
  AI analysis with a mocked valid/malformed/timeout provider; AI analysis
  caching (exactly 1 provider call for 2 identical requests, 2 calls after
  an explicit `force=True` regenerate).
- **Two real bugs found and fixed** while running these tests: (1) a test
  trying to import across `tests/` files, which isn't an importable
  package under this project's `pythonpath=app`-only pytest config — fixed
  by defining the fake provider locally in the integration test file
  instead; (2) a flawed synthetic-data assumption in the lifecycle test
  (adding same-instant flat samples doesn't shift a 16-day regression) —
  fixed by testing the ACTIVE→CLEARED transition mechanism directly.
- **One real production-code bug found and fixed**: the hardcoded
  `expected_revision` string in `PostgreSQLProvider` (already flagged as a
  known fragility in the Phase 1 report) went stale again the moment this
  phase's migration was added — this time fixed at the root by deriving it
  dynamically from the migrations directory (memoized), instead of
  patching the literal a third time.
- **Full Phase 1+2+3 regression**: 62/62 passed together (no interaction
  regressions between phases).
- **Deploy Agent regression**: 133/133 passed after the raw-bytes addition
  to `/api/ops/summary`.

## Evidence

Given the reasoning-effort/time budget for this already-large multi-phase
session, **UI screenshots for Phase 3 (disk forecast card, DB growth,
recurring-failure panel, anomaly detail, AI Incident Summary, suggested
remediation) were not captured this round** — see Known gaps. The
underlying data/API/lifecycle behavior driving that UI is proven by the
27 automated tests above (real PostgreSQL, real HTTP, real regression
math), and the Predictive Insights section + AI Analysis panel were wired
into `system-health.js`/`ui.css` using the exact same drawer/section
patterns already screenshot-verified in Phase 1/2.

## Known gaps

```
DONE:
  - Disk forecast (linear regression, confidence, risk banding, INSUFFICIENT_DATA)
  - DB growth forecast + top-5-tables snapshot
  - DB growth anomaly (rate-based, section 12)
  - Point-anomaly detection (MAD/z-score) applied to CPU_PERCENT, DB_LATENCY_MS
  - Recurring failure detection (fingerprint grouping, trend, time-pattern)
  - Predictive insight ACTIVE/CLEARED lifecycle
  - AI provider abstraction, structured-output validation, sanitization, caching
  - Suggested remediation structure + risk clamping (SAFE_CHECK/LOW_RISK_ACTION/HIGH_RISK_ACTION)
  - Metric collection + bounded retention (scheduled via `mesflow.cli run-predictive`)
  - Predictive Insights section + AI Analysis panel wired into Health Center UI

PARTIAL:
  - Hourly/daily metric aggregation tiers (section 47) -- retention drops
    old high-resolution samples outright rather than rolling them up first
  - Seasonal/time-of-day baseline for anomaly detection (section 21) --
    only a flat rolling baseline is implemented, not an hour-of-day-aware one
  - Correlation with deployments/QA runs/kiosk network segments
    (sections 65-67) -- not implemented; would need deployment_history/QA
    run timestamps joined against incident opened_at, a reasonable
    follow-up given the tables already exist
  - Growth-driver breakdown by component (section 9: "PostgreSQL +420MB/day,
    QA artifacts +680MB/day...") -- only DB size and disk % are tracked;
    attributing disk growth to specific directories/services is not implemented

DEFERRED:
  - UI screenshots for the Phase 3-specific panels (see Evidence)
  - Web notification integration for predictive insights crossing into
    HIGH risk (Phase 2's dispatcher is not yet wired to predictive_insights,
    only to health_alerts)
  - A real live AI provider run (Anthropic API key not configured/available
    in this environment) -- the DISABLED path and the mocked-provider path
    are both proven; a live SUCCESS response is not

INSUFFICIENT_DATA:
  - Any forecast/anomaly/recurrence figure for the real, currently-running
    MESFlow deployment -- this session only ran against fresh/synthetic
    test databases. The real environment has not yet accumulated the
    minimum 24h/6-sample history this phase deliberately requires before
    it will show anything beyond an empty Predictive Insights section --
    exactly the intended behavior (section 54), not a bug.
```

## NO PRODUCTION MUTATION

Confirmed. All work built/tested against an isolated, disposable
`-p mesflow-p3` Compose project, torn down at the end.
`mesflow-postgres`'s `StartedAt` remained byte-for-byte unchanged
(`2026-08-12T04:18:08Z`) across this entire multi-phase session. The real
`mesflow-deploy-agent` container was not redeployed with the raw-bytes
change (verified via a throwaway image build only, then removed).
