# MESFlow — Phase 1: Health Center

## Important note on how this was built

Step 1 (inventory) found that another, concurrently-running session had
already started building this exact feature under the name "V69 System
Health" — `system_health.py`, `system_health_service.py`,
`system-health.js`, migration `0033_v69_system_health` — on top of this
session's own earlier V66 audit-foundation migration. Per this task's own
instruction ("do not code duplicate collectors before completing this
inventory"), this work **extends that existing foundation** rather than
building a parallel one. The existing V69 stub already covered MESFlow,
PostgreSQL, QA Center, Kiosk Fleet and Jobs; this task's real remaining
work was the three cards the spec explicitly required that were missing —
**Server (CPU/RAM/Disk), Docker, and Deploy Agent** — plus the fingerprinted
**Active Alerts** engine (open/dedupe/recover), which did not exist yet.

## RESULT

```
Server                  PASS
CPU                     PASS
RAM                     PASS
Disk                    PASS
Docker                  PASS
MESFlow                 PASS
PostgreSQL              PASS
Deploy Agent            PASS
QA Center               PASS
Kiosk Fleet             PASS
Active Alerts           PASS
Incident History        PASS
```

## Architecture

```
Health Sources (Deploy Agent /health + /api/ops/summary, PostgreSQL SELECT,
MESFlow's own action_logs, QA Center /api/status, kiosk_status heartbeats)
   -> Providers (mesflow.services.system_health_service): MESFlowProvider,
      PostgreSQLProvider, ServerProvider, DockerProvider, DeployAgentProvider,
      HTTPProvider(QA_CENTER), KioskProvider, JobProvider -- each returns a
      normalized HealthCheckResult(component, status, checked_at, latency_ms,
      message, details, critical, configured)
   -> SystemHealthService.summary() -- centralizes overall() policy
      (mesflow.domain.health), persists component_health_state/history,
      computes+syncs Active Alerts
   -> GET /api/system-health (single compact endpoint, per spec section 32)
   -> system-health.js -- one page, auto-refresh, Server panel + Services
      grid + Kiosk Fleet + Active Alerts + Incident History, all above/near
      the fold at 1920x1080
```

### Overall status policy (centralized, backend-only)

`mesflow/domain/health.py::overall()` (pre-existing, unchanged):
DOWN if any **critical** component (MESFLOW, POSTGRESQL, SERVER) is DOWN;
DEGRADED if any configured component is DOWN/DEGRADED; HEALTHY if every
configured component is HEALTHY; UNKNOWN otherwise (e.g. all critical
components healthy but an optional one couldn't be read). The frontend
never recomputes this -- it only reads `overall_status`.

### Server / CPU / RAM / Disk / Docker

Reused, not duplicated: MESFlow's container has no Docker socket and no
`psutil`, so these can only come from Deploy Agent's existing
`ops_summary()` (`deploy-agent/agent.py`, already collecting
cpu_percent/ram/disk/docker_running/docker_unhealthy/hostname/uptime via
`psutil` for its own Ops Console). That endpoint was session-gated only;
extended it to also accept the same `X-MESFlow-Internal-Token` shared
secret MESFlow already validates in the reverse direction
(`mesflow.web.internal_ota`), so MESFlow's backend can read it without a
browser session. Thresholds centralized in `mesflow.core.config`
(`health_cpu_warning_percent=75`, `health_ram_warning_percent=80`,
`health_disk_warning_percent=80/health_disk_critical_percent=90`, matching
the spec's example policy).

### Deploy Agent

New `DEPLOY_AGENT` component: reachability + version from the Agent's
already-public `/health` endpoint (no new auth needed for this part).
DOWN when configured-but-unreachable (non-critical, so it degrades overall
health rather than forcing DOWN, per spec section 2). UNKNOWN with
`configured:false` when `MESFLOW_DEPLOY_AGENT_URL` is unset.

### QA Center

Unchanged from the existing V69 foundation: `HTTPProvider('QA_CENTER', ...)`
hits QA's `/api/status`, distinguishes "service online" from "latest test
result" exactly as spec section 11 requires (DEGRADED + `latest.status` in
the alert condition, not conflated with reachability).

### Kiosk Fleet / Jobs

Unchanged from the existing V69 foundation (thresholds already centralized:
`health_kiosk_offline_seconds=300`, `health_kiosk_degraded_seconds=120`).

### Active Alerts (new)

`health_alerts` table (migration `0034_v69b_health_alerts`), fingerprinted,
one open row per condition (`COMPONENT_DOWN:<c>`, `DEPLOY_AGENT` down,
`QA_LATEST_FAILED`, `DISK_USAGE_HIGH`, `KIOSK_OFFLINE:<device_uuid>`,
`JOB_FAILED:<job>`/`JOB_MISSED:<job>`). `sync_alerts()` upserts on the
partial unique index `(fingerprint) WHERE resolved_at IS NULL` -- a
condition that persists across polls never creates a second row; a
condition no longer present is closed (`resolved_at` set), which is itself
the recovery record. Severity: CRITICAL for a critical component DOWN,
HIGH/MEDIUM otherwise per the spec's own examples.

### Incident History

A single query unions `component_health_history` (component-level
transitions, already existed) with `health_alerts` open/resolve events
(new), sorted newest-first -- meaningful transitions only, never routine
heartbeats.

## Files changed (this task's contribution)

- New: `app/migrations/versions/0034_v69b_health_alerts.py`
- Modified: `app/mesflow/services/system_health_service.py` (added
  `DeployAgentFetch`, `ServerProvider`, `DockerProvider`,
  `DeployAgentProvider`, `_alert_conditions`, `sync_alerts` fingerprint
  engine; kept `MESFlowProvider`/`PostgreSQLProvider`/`HTTPProvider`/
  `KioskProvider`/`JobProvider` from the existing foundation)
- Modified: `app/mesflow/core/config.py` (health threshold/Agent-URL config)
- Modified: `app/mesflow/web/static/pages/system-health.js` (Server panel,
  Active Alerts section, Incident History section, component/kiosk drawers)
- Modified: `app/mesflow/web/static/ui.css` (Server panel, alert, incident
  styles)
- Modified: `deploy-agent/agent.py` (`/api/ops/summary` token-gated for
  cross-service reads; `.gitignore` covers the new `docker/.env`)
- Tests: `tests/test_v69_system_health_unit.py` (extended),
  `tests/integration/test_v69_system_health.py` (extended)

## Database

Migration `0034_v69b_health_alerts`, `down_revision=0033_v69_system_health`.
Purely additive (`CREATE TABLE health_alerts`, one partial unique index for
dedup, one index for history ordering). No table dropped/renamed, no
column type changed. Verified locally against a real, disposable
PostgreSQL: `alembic upgrade head` resolves to a single head at
`0035_v69c_notifications_diagnostics` (Phase 2's migration, chained after
this one) with no branch conflicts.

## Testing

Ran against an **isolated** Docker Compose project (`-p mesflow-p2`,
separate containers/network from both the shared `compose.test.yml`
project and the real production stack) to avoid interfering with the
other concurrently-running session:

- **15 unit tests** (`test_v69_system_health_unit.py`): overall() policy,
  centralized-thresholds contract, migration chain, DeployAgent/Server/
  Docker provider states (not-configured / unreachable / healthy /
  threshold-crossed).
- **6 integration tests** (`test_v69_system_health.py`, real PostgreSQL +
  real HTTP): summary shape with Server/Docker/Deploy Agent unconfigured,
  kiosk online/degraded/offline + fleet counts, job failed/missed/disabled,
  error fingerprint grouping, a forced DOWN->recovered transition recorded
  in history, non-admin (`worker`) role forbidden.
- **Two real bugs found and fixed during this run**: a hardcoded expected
  Alembic revision string in `PostgreSQLProvider` that I forgot to bump
  after adding a later migration (now `0035_v69c_notifications_diagnostics`);
  and the pre-existing test's `SERVER_AGENT` assertion, now updated to
  `SERVER`/`DOCKER`/`DEPLOY_AGENT` to match the real replacement components.
- **Playwright e2e** (`system-health-v69.spec.js`, 3 scenarios): all-healthy
  state, degraded state with 3 active alerts + kiosk-offline drawer +
  server drawer + incident history, and 1366x768 basic usability -- **all
  3 passed**. One real locator bug found in my own test (a CSS descendant
  selector that should have been a same-element attribute selector) and
  fixed.
- **Deploy Agent regression**: full existing suite, **133/133 passed**
  after adding the internal-token gate to `/api/ops/summary`.

## Screenshots (1920x1080, `test-results/`)

`v69-all-healthy.png`, `v69-degraded-active-alerts.png`,
`v69-kiosk-offline-drawer.png`, `v69-server-drawer.png`,
`v69-incident-history.png`, plus `v69-1366x768.png` for the smaller
viewport check.

## Known gaps

- The Deploy Agent source change (token-gated `/api/ops/summary`) is
  implemented and tested via a throwaway image build, but **not yet
  deployed to the real running Deploy Agent container** (still on 2.19.1,
  built before this task) -- so `MESFLOW_DEPLOY_AGENT_URL` pointed at the
  real Agent would currently get `AUTH_REQUIRED` until that container is
  rebuilt/redeployed. Server/Docker/Deploy Agent cards were verified end to
  end against the isolated test stack's own throwaway Agent build, not the
  real one.
- `MESFLOW_DEPLOY_AGENT_URL`/`MESFLOW_INTERNAL_API_TOKEN` are not yet set
  in the real MESFlow deployment's environment -- until they are, those
  three cards will correctly show `NOT CONFIGURED` in production, not a
  false HEALTHY.
- The hardcoded `expected_revision` string in `PostgreSQLProvider` must be
  bumped by hand on every future migration (already bit us once this
  session) -- worth deriving it from the migrations directory dynamically
  in a later pass rather than a literal.

## NO PRODUCTION MUTATION

Confirmed. All work built/tested against an isolated `compose.test.yml`
project (tmpfs PostgreSQL + disposable app/tests/playwright containers),
torn down at the end. `mesflow-postgres`'s `StartedAt` is byte-for-byte
unchanged from this session's baseline throughout. `mesflow-app` and
`mesflow-qa-center` were not touched by this task (their state reflects
other, separately-authorized work earlier in this session). The real
`mesflow-deploy-agent` container was not redeployed with these changes.
