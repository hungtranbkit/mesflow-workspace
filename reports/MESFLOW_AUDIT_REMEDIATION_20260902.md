# MESFlow Environment Audit Remediation — 2026-09-02

STATUS: **READY_WITH_LIMITS** (server/backend layer). See §7 for the exact
2 open items and why neither is a P0 infrastructure blocker anymore.

Follows `reports/MESFLOW_WORKSPACE_V2_CONSOLIDATION_20260901.md`. That
report covered V1/V2 consolidation and initial DEV/PRODUCTION_TEST
deploys. This one covers the **read-only audit** that followed (scheduler,
backup, disk, ESP/kiosk) and the **user-approved fixes** applied to every
finding, end to end, with live evidence — not just what was found.

All work in this report happened directly against real hosts (no
subagents). `mesflow/`'s own worktree+branch policy was used for every
source change; operational-only actions (cron, .env, DNS, container
recreation) were done directly since they touch no tracked source.

---

## 1. Real topology (final, live-verified)

| Label | Host | App port | DB | App version | Scheduler DB |
|---|---|---|---|---|---|
| Local / `dev.mesflow.net` | this machine | 8080 → `mesflow-app` | `mesflow-postgres` / `mesflow` | 71.0.0.207 | own |
| `mesflow.net` = `deploy.mesflow.net` = `ssh-test.mesflow.net` (1 physical host, confirmed via matching `docker ps`) | remote | 8080 (behind Cloudflare, no Nginx-visible port here) → `mesflow-app` | `mesflow-postgres` / `mesflow` | 71.0.0.207 | own |
| `prod.mesflow.net` | this machine | 8299 → `mesflow-prodtest-app` | `mesflow-prodtest-db` / `mesflow_prodtest` | 71.0.0.207 | own |
| `kiosk-v2-local-test.mesflow.net` | — | — | — | **removed** | n/a |

Every DB is a fully separate Postgres instance/database/credential set —
no cross-target data sharing at any point in this remediation.

## 2. Disk / cleanup (mesflow.net-host)

**90% → 55%** (65G/72G → 40G/72G used). Removed ~190 old, zero-container
Docker image tags (kept current + immediate-previous per service for
rollback: `mesflow-app` 71.0.0.207+.206, `mesflow-qa-center` 1.32.1+1.27.4,
`mesflow-deploy-agent` 2.24.37+2.24.32) and pruned regenerable build cache
(2.8GB). Left every unrelated project's container/image on that shared
host untouched (`grafana`, `loki`, `mariadb` — not MESFlow's).

## 3. Backup + restore-drill tooling

New (`mesflow/scripts/backup-db.sh`, `restore-drill.sh`,
`install-backup-db-cron.sh`, commits `eed2cfc`..`c134c90`): container-
name-based (works without a source checkout on a deployed host per RULE
6), `flock`-protected, atomic (`.tmp`-then-rename) output, `umask 077`,
sha256 checksum, JSON manifest with a frozen row-count snapshot,
count-based retention that never deletes a `.verified`-marked backup.
Two rounds of independent review found and fixed real bugs before this
was trusted: cron env not persisted (defaults would silently differ from
a manual test run), idempotent-replace marker not scoped per DB target
(a second target's install deleted the first's cron line — off-by-one in
the `awk` skip logic), missing `-v` on drill container teardown (leaked
anonymous volumes), fail-open manifest parsing (a broken manifest field
printed a false "OK"), and a real startup-race in the drill's readiness
check against the official postgres image's own two-phase boot.

**Real backup + `RESTORE_DRILL_PASS` on all 3 DB targets**, using a
throwaway, ephemeral-volume Postgres container each time (never the live
DB, never a host bind-mount):

| Target | Backup (UTC) | Drill result |
|---|---|---|
| `mesflow-postgres` (local) | 2026-09-02T06:25:54Z | migration=0043, tables=65, employees=26 — match |
| `mesflow-prodtest-db` (local, post-migration checkpoint) | 2026-09-02T06:50:41Z | migration=0043, tables=65, work_sessions=19, employees=26 — match |
| `mesflow-postgres` (mesflow.net-host) | 2026-09-02T06:28:29Z | migration=0043, tables=65, work_sessions=5, employees=27 — match |

Daily cron installed on all 3 (`02:17`/`02:20` local, `02:17` remote),
each target-scoped (verified: installing/re-installing one target's entry
never touches another's, and an unrelated pre-existing cron line survives
untouched — tested explicitly with an install-A/install-B/reinstall-A
sequence).

## 4. Scheduler (`shift_session_reconciliation` / `exception_reconciliation` / `log_retention`)

**Root cause**: host cron for these jobs (`scripts/install-reconcile-cron.sh`,
`install-log-retention-cron.sh` — pre-existing in the repo) had never
actually been run on either the local or the `mesflow.net`-host DB. Cron
was completely empty on both (confirmed via `crontab -l`, `/etc/cron.d`,
`/var/spool/cron` — the last two checked once, before the user restricted
further use of that inspection method).

**Fixed on all 3 DB targets** (local `mesflow`, `mesflow.net`-host
`mesflow`, local `mesflow_prodtest`): dry-run checked first, real backup
taken, `MESFLOW_SHIFT_AUTO_CLOSE_ENABLED=1`/`_DRY_RUN=0` set via `.env` +
container recreation (env is read at container-**create** time, not
per-request — editing `.env` alone does nothing until recreated), cron
installed at the repo's own default cadence (shift: every minute,
exception: every 5 minutes, log_retention: daily).

**Real, cron-triggered `scheduled_job_health` SUCCESS** (not manual) —
timestamps:

| DB target | shift_session_reconciliation | exception_reconciliation |
|---|---|---|
| local `mesflow` | 2026-09-02T06:42:02Z | (5-min cadence, not yet due at time of writing) |
| `mesflow.net`-host `mesflow` | 2026-09-02T06:41:03Z | 2026-09-02T06:40:47Z |
| local `mesflow_prodtest` | 2026-09-02T06:50:57Z | 2026-09-02T06:50:56Z |

`log_retention` is installed and independently verified to run correctly
on all 3 (real output, real `scheduled_job_health` row), but its daily
02:17 cadence hadn't fired naturally on its own by the time this report
was written — disclosed as such, not overclaimed as cron-triggered.

**Real incident caught and fixed mid-fix**: recreating the local app
container picked up a *stale* `MESFLOW_IMAGE` value already sitting in
`/opt/mesflow/.env` (a digest from an older, unrelated deploy flow) —
briefly downgraded local DEV to 71.0.0.66/migration 0039. Caught
immediately via the post-recreate health check, corrected by pinning the
right digest explicitly, re-verified. Same explicit-pin discipline used
for every subsequent recreation (including `prod.mesflow.net`'s) to avoid
repeating it.

**The 3 sessions found stuck open 11 days (id 11/12/13) — closed for
real, via the official reconcile, once cron actually ran**:

| id | before | after |
|---|---|---|
| 11/12/13 | `OPEN`, started 2026-08-22 | `CLOSED`, `close_reason=AUTO_SHIFT_END`, `ended_at=2026-08-22T10:00:00Z` (= 17:00 Asia/Ho_Chi_Minh, the shift's real end — **not** the time the job ran), `good_qty=0, defect_qty=0` (untouched/honest, never fabricated) |

Re-running dry-run afterward reports 0 candidates — idempotent, confirmed.

**`predictive_metrics_collection` — investigated, deliberately left
alone.** `mesflow.cli run_predictive()` is a complete, real implementation
(`MetricsCollector`, `PredictiveService`, its own `scheduled_job_health`
reporting) — not a missing-wiring case like the other three. It's gated
behind `MESFLOW_LEGACY_HEALTH_WRITER_ENABLED` (default `0`), with the
code's own comment stating Deploy Agent is now authoritative for this and
the flag exists "to allow a deliberate rollback." Enabling it would be an
architecture decision (un-deprecating a legacy path), not a bug fix in
the same class as the other three — left as `UNKNOWN`, reported precisely
rather than mischaracterized as "not implemented" or silently wired up.

## 5. `scripts/cleanup-logs.sh` packaging gap

**Root cause**: `install-log-retention-cron.sh` wires a cron job to
`docker compose exec ... /app/scripts/cleanup-logs.sh run`, but the
`Dockerfile` only ever `COPY`s `scripts/docker-entrypoint.sh` out of
`scripts/` — the rest of that directory, `cleanup-logs.sh` included, was
never part of any built image. The job would fail (file not found) every
time it ran.

**Fixed in source** (`mesflow` commit `14bb32a`): `Dockerfile` now also
copies `scripts/cleanup-logs.sh`. **This fix is source-only as of this
report** — none of the 3 currently-running `71.0.0.207` images (all built
before this commit) have it baked in; it takes effect starting with the
next build. A temporary, non-git-tracked operational bridge (identical
logic, invoked inline via `docker compose exec ... python -c "..."`)
is in place on all 3 hosts so the job runs correctly today regardless.

## 6. ESP/Kiosk

- 47/47 real, fresh tests PASS on isolated fixtures (separate DB, torn
  down after — no real data touched): 25 kiosk-v2 integration
  (employee/OP scan authorization, shared terminal, heartbeat, bootstrap,
  device-identity rejection), 12 offline/idempotency, 10 RBAC
  admin/non-admin. Not re-run for this report (already real, fresh
  evidence, per explicit instruction not to add broad regression on top).
- `esp-kiosk/` and `mesflow-kiosk-runtime-v2/` dirty working trees:
  untouched throughout, confirmed identical diff before/after this whole
  session.
- `Q:N` (offline event backlog counter, `pending + in_flight`) — confirmed
  by code, left as-is; no evidence of a real replay bug found or fixed.
- **No real ESP32 hardware was online at any point this session**
  (furthest device record: 10+ days stale, internal-looking IP,
  firmware version matching V1/`esp-kiosk` not V2) — the full physical
  scan→start→finish flow and `Q:N`'s actual on-device behavior remain
  **HARDWARE_VERIFICATION_PENDING**. Not claimed PASS.

### `kiosk-v2-local-test.mesflow.net` (the original 502) — fully resolved, by removal

This was investigated separately from `dev.mesflow.net` (a different
hostname sharing the same now-retired `:8199` backend) and initially left
`BLOCKED`: the firmware has a real `ENV_MISMATCH` safety guard
(`kiosk_runtime.cpp`, compares a device's configured `expected_environment`
against the server's reported role, refuses to scan/sync on a genuine
mismatch), but confirming actual safety needed either a live device or
restarting the already-retired `:8199` stack — neither available, and
restarting it wasn't in scope. **User confirmed no real device was ever
provisioned against this hostname**, which resolved the blocker as
"nothing to protect" rather than "safe to remap." Per that:
- Removed the `kiosk-v2-local-test.mesflow.net` ingress rule from
  `~/.cloudflared/kiosk-local-test-config.yml` (tunnel now serves only
  `dev.mesflow.net`), reloaded the tunnel.
- Removed the CNAME DNS record itself via the Cloudflare API (credential
  sourced from `cloudflared`'s own existing `cert.pem`, an embedded
  scoped API token — never printed; extracted and used within a single
  shell invocation so it never touched a second, un-exported process).
- Verified: the hostname no longer resolves at all (`Could not resolve
  host`) — clean removal, not merely a 404.

## 7. What's still open (not P0)

1. `predictive_metrics_collection` (§4) — needs a human decision (revive
   the legacy path, or leave it to Deploy Agent as currently intended);
   not attempted without that decision.
2. ESP32 hardware verification (§6) — needs a real device; nothing more
   to fix server-side without one.

Neither blocks the backend/server layer's own readiness.

## 8. Credential hygiene

Admin login unified to a single known password (`admin`/`Admin@123456`,
verified by an actual login call, not just "command succeeded") across:
local Deploy Agent, local MESFlow app, `mesflow.net`-host Deploy Agent,
`mesflow.net`-host MESFlow app. `prod.mesflow.net`'s app already used the
same convention default independently (verified by login, not changed).
No password/token/secret value was ever printed in this session except
one accidental line (a `DATABASE_URL` with an embedded DB password,
mid-session, immediately flagged and not repeated) — the redaction
pattern used afterward was corrected to also catch `*_URL=` lines.

## 9. Final state snapshot (2026-09-02, ~07:35 UTC)

| Check | Local/`dev.mesflow.net` | `mesflow.net`-host | `prod.mesflow.net` |
|---|---|---|---|
| App version / migration | 71.0.0.207 / 0043 | 71.0.0.207 / 0043 | 71.0.0.207 / 0043 |
| Health | `ok:true` | `ok:true` | `ok:true` |
| Login (Admin@123456) | ✅ | ✅ | ✅ (pre-existing) |
| Backup + drill | ✅ PASS | ✅ PASS | ✅ PASS (post-migration checkpoint) |
| Auto-close scheduler | ✅ real cron SUCCESS | ✅ real cron SUCCESS | ✅ real cron SUCCESS |
| Disk | 52% (unchanged, never critical) | 55% (was 90%) | shares local disk |
