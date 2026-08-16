# Environment Parity Audit

Audit time: 2026-08-12 (Asia/Ho_Chi_Minh). Evidence was collected read-only from DEV LOCAL and SSH alias `mesflow-test`. No secret values were read or recorded.

## Reconciliation baseline

The required reconciliation scripts ran for all three projects. Sanitized diffs showed workspace source ahead of `/opt`, with no files present only in deployed source:

| Project | Workspace | `/opt` snapshot | Decision |
|---|---:|---:|---|
| MESFlow | 65.8.44.56 at reconcile (now 65.8.44.57) | 65.8.44.52 | Keep newer workspace; do not import backward |
| Deploy Agent | 2.15.x at reconcile (now 2.15.4) | 2.13.1 | Keep newer workspace; do not import backward |
| QA Center | 1.19.7 at reconcile (now 1.19.8) | 1.19.6 | Keep newer workspace; do not import backward |

The workspace contained pre-existing MESFlow changes. They were preserved.

## DEV LOCAL inventory

| Item | Observed |
|---|---|
| OS / architecture | Ubuntu 26.04 LTS, amd64 |
| Docker / Compose | 29.7.2 / 5.4.0 |
| Host timezone / locale | Asia/Bangkok / C.UTF-8 (business contract is Asia/Ho_Chi_Minh) |
| MESFlow | `mesflow-app:65.8.44.52`, healthy, `127.0.0.1:8080` |
| PostgreSQL | 17-alpine, healthy, internal 5432 |
| Deploy Agent | running image 2.14.1 at audit; source 2.15.3; health later observed unhealthy during fingerprint |
| QA Center | runtime image 1.0.0, API reports 1.19.6, healthy at audit |
| Gateway | nginx 1.28-alpine, healthy, ports 80/443 |
| Networks | `mesflow_network`, external `mesflow-edge`; test network also present |
| Persistent storage | bind mounts under `/opt/mesflow/runtime`; Docker named volumes are not used by MESFlow |
| Restart policy | application/PostgreSQL/Agent/QA/nginx: `unless-stopped` |
| Schema | 65.8.44.46; migration head `0026_night_shift_same_day_midnight` |
| Health contract | `/api/system/health`, `/api/system/version`, `/api/system/ready`; Agent `/health`; QA `/api/version` |
| Compose source | MESFlow `/opt/mesflow/compose.yml`; Agent workspace linux compose + bootstrap port override; QA `/opt/mesflow-qa-center/current/docker/compose.yml` |
| `.env` | `/opt/mesflow/.env`, mode 0600; key names audited only |

DEV contains additional short-lived UI/test containers. They are not part of the deployable environment contract.

## Expected Production Test contract

Source defines PostgreSQL 17, Python 3.13 MESFlow runtime, application service/container `mesflow`/`mesflow-app`, internal port 8080, healthcheck `/api/system/ready`, persistent runtime bind mounts and both `mesflow_network` plus external `mesflow-edge`. Deploy Agent must mount its persistent `/data`, Docker socket and the same absolute `/opt` target paths. QA joins `mesflow-edge` and targets `http://mesflow-app:8080`.

The canonical key/type/default/secret classification is in `config/env.schema`. Actual env values remain outside Git. The app health semantics are:

- health: application and PostgreSQL reachable, includes runtime/schema version;
- version: runtime package version;
- ready: database reachable, schema version and Alembic head available;
- Agent verification: expected version equals runtime version and app/database/container are healthy.

Tutorial persistence uses host `runtime/tutorials/` mounted read-only at `/data/tutorials`, with ESP content at `runtime/tutorials/esp-kiosk/`. The publisher/Agent requires host write permission while the application must not.

## Production Test evidence

| Item | Observed |
|---|---|
| OS / architecture | Ubuntu 25.04, amd64 |
| Docker / Compose | 29.2.1 / 5.0.2 |
| Timezone / locale | Asia/Ho_Chi_Minh / C.UTF-8 |
| MESFlow | 65.8.44.51, healthy |
| PostgreSQL | 17.10, healthy |
| Deploy Agent | 2.12.9, Docker unhealthy; endpoint responds in about 5.54s vs 5s healthcheck timeout |
| QA Center | direct host API identifies 1.19.0, but Deploy Agent reports QA offline; legacy `mesflow-testcenter` exited 137 |
| Gateway | nginx 1.28-alpine, healthy |
| Schema | 65.8.44.46; migration head `0026_night_shift_same_day_midnight` |
| Runtime paths | tutorials exists; `runtime/tutorials/esp-kiosk` missing |
| `.env` | exists, root:root mode 0600; SSH user cannot enumerate keys, so key parity is NOT VERIFIED |

## Audit conclusion

PARITY STATUS: **BLOCKED / NOT READY FOR PROMOTION**.

The PostgreSQL major, architecture, schema and migration head align. Blocking evidence remains: Agent major/minor mismatch and unhealthy state; required ESP tutorial path absent on both captured environments; Production Test QA unreachable from its Agent; protected Production Test app env-key names cannot be verified with the current SSH account; and deployed Agent/QA containers on both targets lack newly required contract keys. DEV host timezone is a warning. No local Agent release deployment or frozen same-artifact promotion was performed in this task, so local and Production Test deploy gates remain NOT VERIFIED.
