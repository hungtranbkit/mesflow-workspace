# P4 — Backup / DB / Storage Center

Date: 2026-08-14
Deploy Agent version: 2.23.7-docker-runtime → 2.23.8-docker-runtime (source tree only; see safety note)
Scope: `deploy-agent/agent_backend/db_backup.py` (new, 661 lines: `BackupService`, `RetentionService`,
`RestoreDrillService`, `StorageService`, `postgres_summary()`), wired into `agent.py` as a new,
clearly-separated API namespace (`/api/ops/db-backups`, `/api/ops/db/summary`, `/api/ops/storage`,
`/api/ops/restore-drills`, `/api/ops/db-audit`), plus a new "Backup / DB / Storage" tab in
`templates/ops.html`.

Reused, not rebuilt: the project's existing proven backup mechanism (`mesflow/scripts/backup.sh`'s
`pg_dump -Fc` / `pg_restore -l` / SHA256 approach, reimplemented as argument-array subprocess calls),
the JSON-file-store convention from `incidents.json`/`notifications.json`, the `environment_label()`
function from P3, and the existing `predictive_summary()`'s `fastest_growing_tables` forecast.

---

## Summary

| Area | Result |
|---|---|
| Manual PostgreSQL Backup (vertical slice 1) | PASS |
| Backup Retention (vertical slice 2) | PASS |
| Restore Drill (vertical slice 3) | PASS |
| Storage Pressure (vertical slice 4) | PASS |
| Checksum + manifest verification | PASS |
| BACKUP_SUCCESS / BACKUP_VERIFIED / RESTORE_TESTED as distinct states | PASS |
| Retention protection invariants (pinned / newest verified / active restore source) | PASS |
| Restore drill blocked in PRODUCTION environment | PASS |
| Audit trail for every mutation | PASS |
| PostgreSQL Center (size, connections, long queries, locks, revision, tables) | PASS |
| Storage Center (filesystem + category breakdown) | PASS |
| `mes_backups/` (source rollback) vs. DB backups kept architecturally distinct | PASS |
| `_postgres_database_size`/`_postgres_table_sizes` `docker exec` auth bug (found this task) | FIXED |
| `/ops?view=backup` silently downgrading to `overview` (found this task) | FIXED |
| Real production containers touched | NONE |
| Scheduled/automatic periodic backup triggering | **DEFERRED** (see Scope discipline) |

---

## Design

**Architecture** (section 73 of the spec): `BackupService` / `RetentionService` / `RestoreDrillService` /
`StorageService`, one JSON-file-backed record store per concern — `db_backups.json`, `restore_drills.json`,
`db_audit.json` under `CONFIG_DIR` — matching the existing `incidents.json`/`notifications.json`
convention. No new database, no Redis, no scheduler framework.

**Backup mechanism**: `docker exec mesflow-postgres sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump
-U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'`, captured as raw bytes (`run_capture_binary` — never
text-decoded, which would silently corrupt the binary archive), written to a `.tmp` path, then atomically
renamed to its final `.dump` name only after a clean exit. A crashed or partial dump can never appear as
a real backup file.

**Three distinct states per backup** (section 19, explicitly required to stay separate):
- `status: SUCCESS` — the `pg_dump` completed and was written.
- `verification_status: VERIFIED` — checksum matches AND `pg_restore -l` can read a real manifest from
  the archive. Runs automatically once, immediately after `create()`, and can be re-run any time.
- `restore_tested: true` — a real restore drill into an isolated database actually succeeded. Only a
  successful `RestoreDrillService.run()` can set this; it is never inferred from verification alone.

**Retention protection invariants** (section 63, `RetentionService._protected_ids`): the newest
`SUCCESS` + `VERIFIED` backup, every `pinned` backup, and the backup currently in use by an in-flight
restore drill are computed as a protected set *before* any policy is applied — a numeric retention
policy can never make all three empty even if misconfigured to `0`. Retention is preview-first: every
`preview()` call returns exactly what `apply()` would delete, with reasons; `apply()` will not run without
an explicit `{"confirm": true}` in the request body, in addition to login + CSRF (section 61: destructive
actions must never run automatically).

**Restore drills** (section 21/55): `temp_db = f"mesflow_restore_drill_{uuid4().hex[:12]}"` — always
generated server-side, never accepted from the caller — created on the *same* configured Postgres target,
restored into via `pg_restore --no-owner`, validated (`information_schema.tables` count > 0, and the
`alembic_version` revision if present), then unconditionally dropped with `DROP DATABASE ... WITH
(FORCE)` in a `finally` block regardless of validation outcome, so a failed drill never leaves a stray
database behind. `POST /api/ops/db-backups/<id>/restore-test` additionally returns
`403 RESTORE_DRILL_BLOCKED_IN_PRODUCTION` whenever `environment_label(SERVER_ROLE) == "PRODUCTION"` —
restore drills are LOCAL/TEST only, by construction, not just by convention.

**Storage Center**: `StorageService.category_sizes()` walks explicitly configured roots only (Backups,
PostgreSQL release-backups, Releases, Logs, Uploads — never arbitrary paths from the web UI, section 48).
`filesystem_summary()` classifies `pressure_level` as `OK`/`WARNING`/`CRITICAL` via a pure threshold
function (`storage_pressure_level`, default 80%/90%), the same vocabulary the existing `DISK_CRITICAL`
incident condition uses, so Storage Center and the incident engine can never disagree about what
"pressure" means.

**Audit trail** (`_db_audit` in `agent.py`): every mutation — `BACKUP_STARTED/COMPLETED/FAILED/VERIFIED/
VERIFY_FAILED/PINNED/UNPINNED`, `RESTORE_DRILL_STARTED/COMPLETED`, `BACKUP_DELETED_BY_RETENTION`,
`RETENTION_APPLIED` — is written to `db_audit.json` (capped at 1000 entries, newest first via
`/api/ops/db-audit`) *and* to the existing human-readable `AGENT_LOG`, so nothing happens silently.

---

## Real bugs found and fixed while building this

1. **`_postgres_database_size()`/`_postgres_table_sizes()` in `agent.py` were silently broken** since
   they were first written (by a concurrent session, undetected because no test exercised them):
   `docker exec <container> psql ...` with no `-U`/`-d` runs as the container's root OS user, not the
   `postgres` role, and fails closed with `FATAL: role "root" does not exist` — confirmed empirically
   against both a throwaway container and the real `mesflow-postgres`. Fixed by connecting explicitly as
   `$POSTGRES_USER`/`$POSTGRES_DB` (the target container's own already-set env vars, never typed or
   stored by this Agent). The new `db_backup.py` uses the same corrected pattern from the start.
2. **`/ops?view=backup` silently downgraded to `overview`**: `ops_page()`'s `allowed` view whitelist was
   never updated when the new tab was added, so the query param was silently discarded — caught while
   capturing Playwright screenshots (the button and section both worked once actually reached; the
   server just never routed there). Fixed by adding `'backup'` to the whitelist; regression-tested in
   `tests/test_p4_ops_page.py` so this class of bug (a new tab whose `?view=` param is quietly ignored)
   can't recur unnoticed.

---

## Vertical slices (tested, in priority order)

All four run against a throwaway, self-managed PostgreSQL container (`postgres:17-alpine`, started and
torn down by the test fixtures themselves) — never `mesflow-postgres`. `tests/test_p4_vertical_slices.py`.

### 1. Manual PostgreSQL Backup — PASS
Observe (`/api/ops/db/summary` reachable) → Backup (`POST /api/ops/db-backups`, real `pg_dump -Fc`) →
Verify (checksum + `pg_restore -l` manifest, both real) → Audit (`BACKUP_STARTED`/`COMPLETED`/`VERIFIED`
all present). Confirms `SUCCESS`/`VERIFIED`/`restore_tested=False` are independently correct at this
point — `restore_tested` has not been claimed prematurely.

### 2. Backup Retention — PASS
Three backups created, oldest unpinned, newest and one explicitly pinned. Under a tightened
`manual: 1` policy, `preview()` correctly identifies only the middle (unpinned, non-newest) backup as
eligible; `apply()` without `{"confirm": true}` is rejected (`400`) and deletes nothing; with confirmation
it deletes exactly that one backup's file and record, leaving the pinned and newest backups untouched.
`BACKUP_DELETED_BY_RETENTION` and `RETENTION_APPLIED` both appear in the audit trail.

### 3. Restore Drill — PASS
A verified backup is restored into a real, generated-name temporary database (`mesflow_restore_drill_*`)
on the throwaway target, validated (table count ≥ 2, `alembic_version` revision readable and correct),
and the temp database is confirmed gone afterward via a direct `pg_database` lookup. `restore_tested`
flips to `true` only after this succeeds — proven to have been `false` beforehand.

### 4. Storage Pressure — PASS
The `backups` category is measured before/after two new backups are created (must grow), retention
`preview()` reports exactly the reclaimable byte count of the eligible backup, and applying retention
measurably shrinks the category again. `filesystem.pressure_level` is present and one of
`OK`/`WARNING`/`CRITICAL` on every call. The pure threshold function itself
(`storage_pressure_level(percent, warning, critical)`) is unit-tested at the 0/79.9/80.0/89.9/90.0/100
boundary values plus custom thresholds.

---

## PostgreSQL Center evidence

Live-verified (not just unit-tested) against a real throwaway Postgres container with two real
concurrent sessions: one holding a row lock inside `BEGIN; UPDATE ... SELECT pg_sleep(20)`, a second
blocked on the same row. `postgres_summary()` correctly reported:

```json
{
  "database_size_bytes": 7820979,
  "connections": {"active": 4, "idle": 0, "total": 9, "max": 100},
  "long_running_queries": [
    {"pid": 99,  "duration_seconds": 8, "state": "active", "query": "SELECT pg_sleep(20);"},
    {"pid": 100, "duration_seconds": 8, "state": "active", "query": "BEGIN; UPDATE employees ..."},
    {"pid": 107, "duration_seconds": 6, "state": "active", "query": "UPDATE employees ..."}
  ],
  "blocked_lock_count": 1,
  "db_revision": "0037_v72",
  "largest_tables": [{"table": "public.employees", "size_bytes": 32768}, ...]
}
```

Every field is a real observed value, not a placeholder — including the exact blocked-lock count (1) and
all three concurrently-running sessions with correct durations.

---

## Backup / Restore / Retention / Storage evidence (screenshots)

See UI evidence below — the same live data (3 real backups, 1 pinned, 1 restore-tested, real audit
trail, real retention-eligible row, real storage category bytes) is visible directly in the Operations
Center UI, not just in test output.

---

## UI evidence (1920px wide, full-page)

Captured against a real, locally-served Agent instance (isolated `WORKSHOP_AGENT_HOME`, real throwaway
Postgres container, real backups/verify/restore-drill run through the exact same service instances the
app itself uses) — never the real `mesflow-postgres`/`mesflow-deploy-agent`. Zero console errors, zero
page errors (`{"consoleErrors": [], "pageErrors": []}`).

- `reports/screenshots/p4/backup-db-storage-overview.png` — the new "Backup / DB / Storage" tab:
  PostgreSQL Center (7.6 MB DB, 1/6 connections, 0 slow queries, 0 blocked locks, revision `0037_v72`),
  Storage (3.4 GB / 7.4 GB · 46% · "Bình thường"/OK, category breakdown), largest tables, the 3-row
  PostgreSQL Backups table (all `SUCCESS`/`VERIFIED`, one `RESTORE_TESTED`, one 📌 pinned), the Restore
  Drill history (1 `SUCCESS`, cleanup ✓), and the full Audit trail (every `BACKUP_*`/`RESTORE_DRILL_*`
  event in order).
- `reports/screenshots/p4/retention-preview.png` — after clicking "Xem trước" (Preview): "1 backup đủ
  điều kiện · có thể giải phóng 7.9 KB · 2 backup được bảo vệ" with the eligible row's exact reason
  ("Expired by manual retention (keep 1)") — proving the preview-before-apply flow is real, not
  decorative.

---

## Tests

```
$ .venv/bin/python -m pytest tests/test_p4_db_backup.py -v          # BackupService/RetentionService/
23 passed                                                            # RestoreDrillService/StorageService/
                                                                       # postgres_summary, live + pure-logic

$ .venv/bin/python -m pytest tests/test_p4_db_backup_routes.py -v   # Flask route wiring, live
11 passed

$ .venv/bin/python -m pytest tests/test_p4_vertical_slices.py -v    # the 4 required vertical slices
4 passed

$ .venv/bin/python -m pytest tests/test_p4_ops_page.py -v           # regression test for the view-
3 passed                                                             # whitelist bug found this task

$ ./scripts/test-baseline.sh   # py_compile + full pytest -q + source package build/verify
264 passed, 8 subtests passed
{"file_count": 111, "filename": "mesflow-deploy-agent-source-2.23.8-docker-runtime.zip",
 "sha256": "5a395bace41e6e2d59f9d0bd379fc94e723bcfbef5b55a6f58a4e607157f7f42",
 "size": 281743, "status": "PASS", "version": "2.23.8-docker-runtime"}
```

41 new tests added this task (23 unit + 11 route + 4 vertical-slice + 3 regression), zero pre-existing
tests broken. All docker-dependent tests self-manage their own throwaway Postgres container(s) and skip
cleanly (not fail) in an environment without docker; none ever reference `mesflow-postgres` by name.

---

## Files changed

New: `agent_backend/db_backup.py`, `tests/test_p4_db_backup.py`, `tests/test_p4_db_backup_routes.py`,
`tests/test_p4_vertical_slices.py`, `tests/test_p4_ops_page.py`, `reports/screenshots/p4/*.png`.

Modified: `agent.py` (import + service instantiation + 15 new API routes + `protect()` exemptions +
the `ops_page()` whitelist fix), `templates/ops.html` (new "Backup / DB / Storage" tab + ~110 lines of
JS), `VERSION.txt`/`README.md`/`docker/Dockerfile`/`docker/compose.linux.yml`/
`docker/compose.windows.yml`/`docs/DEPLOY_DOCKER.md` (version bump, all 7 locations verified
synchronized by the existing `test_authoritative_versions_are_synchronized` hygiene test).

---

## Scope discipline

**Built** (Definition of Done: backup → verify → retain → restore-test → audit, all four vertical
slices): manual on-demand PostgreSQL backup with atomic completion and immediate verification; explicit
preview-then-apply retention with hard protection invariants; LOCAL/TEST-only restore drills into
isolated generated-name databases; filesystem + category storage breakdown with pressure classification;
a structured audit trail for every mutation; a read-only PostgreSQL Center (size/connections/long
queries/locks/revision/tables).

**Explicitly deferred, not built**: automatic/scheduled periodic backup triggering (a cron-style loop
analogous to `_incident_monitor_loop`/`_predictive_monitor_loop` that calls `BackupService.create()` on
a timer) — the spec's vertical-slice priority order (sections 89–92) lists only Manual Backup, Retention,
Restore Drill, and Storage Pressure as required; scheduled triggering was named as a nice-to-have
("manual **and** scheduled backup tracking") but not as a priority slice, and adding an unattended
background job that runs `pg_dump` against production on its own is exactly the kind of automatic
mutation this task's own safety section says must never happen without a human decision point. It is a
natural next step (the `BackupService.create(retention_class="daily", triggered_by="scheduler")` call
already exists and works — only the timer loop and its own explicit enable/disable config would need to
be added) but was left out this task rather than rushed in without equally careful testing.
Also not built: incident-engine integration for `BACKUP_FAILED`/`BACKUP_MISSED` conditions (would reuse
the existing `_incident_conditions()`/notification pipeline from P2/P3 in the same way — straightforward,
but out of scope for this task's four required slices); a UI control to change the retention policy
numbers at runtime (currently env/code-configured, defaults documented above); concurrent-restore-drill
locking (only one drill is realistically triggered by a single admin at a time in this UI, so a
`BackupService`-style `ConflictError` guard was not added — noted here rather than silently assumed
covered).

## Safety

```
NO AUTOMATIC PRODUCTION RESTORE     CONFIRMED — RestoreDrillService is only ever invoked from an explicit,
                                     authenticated, CSRF-protected POST with {"confirm": true}; the route
                                     additionally 403s outright whenever SERVER_ROLE resolves to PRODUCTION
NO AUTOMATIC DATABASE TERMINATION   CONFIRMED — this task adds no code path that stops, restarts, or drops
                                     any database other than a restore drill's own throwaway temp database
NO AUTOMATIC DOCKER PRUNE           CONFIRMED — StorageService.docker_storage() only ever runs read-only
                                     `docker system df`; no prune/rm code was added
NO ARBITRARY FILE DELETE            CONFIRMED — RetentionService.apply() only ever deletes a file it itself
                                     wrote (backup_dir/<stem>.dump, from its own record store), never a
                                     caller-supplied path; StorageService never accepts arbitrary paths
                                     from the web UI (only pre-configured category roots)
NO UNAPPROVED PRODUCTION MUTATION   CONFIRMED — no production deploy, restart, DB write, or config change
                                     was made by this task; all backups/verifies/retention/restore-drills
                                     were run exclusively against throwaway postgres:17-alpine containers,
                                     created and destroyed by this task's own scripts/tests
```

**Production containers, before/after this task's work:**

```
mesflow-postgres:      StartedAt=2026-08-12T04:18:08Z  RestartCount=0  (unchanged)
mesflow-app:            healthy, RestartCount=0
mesflow-deploy-agent:    healthy, RestartCount=0, running image mesflow-deploy-agent:2.23.6
```

**Transparency note (same pattern as every report this session):** `mesflow-app` and
`mesflow-deploy-agent` were observed to have restarted at some point during this task's work (both with
`RestartCount=0`, i.e. clean restarts, not crash loops) — by something outside this conversation, not by
any command run here; no `docker restart`/`stop`/`rm` was ever issued against `mesflow-app`,
`mesflow-postgres`, or `mesflow-deploy-agent` in this task. `mesflow-postgres`'s `StartedAt` timestamp is
byte-for-byte unchanged from the P3 report's baseline. This task's own new code (source version
`2.23.8-docker-runtime`) has **not** been deployed anywhere — it exists only in this working tree and was
verified entirely through isolated local test instances and throwaway Postgres containers, all of which
have been stopped and removed.
