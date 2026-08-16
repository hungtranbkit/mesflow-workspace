# Deploy Agent local audit — 2026-08-12

## Initial evidence (before restart)

- Container: `mesflow-deploy-agent`, image `mesflow-deploy-agent:2.13.1`, Up/healthy, published only `127.0.0.1:8090`.
- `/agent/health`: Agent `2.13.1-docker-runtime`; MESFlow `65.8.44.48`; MESFlow and PostgreSQL healthy.
- Docker socket and `/opt/mesflow` are read/write bind mounts; Agent runs as container root.
- `mesflow-edge` exists and contains Agent, MESFlow app, QA Center and nginx.
- `/opt/mesflow/.env`: `0600`, `dell:dell`; container read check succeeded without permission change. No secret contents were logged.
- Agent persistent paths: `/data/data/uploads`, `/data/data/releases`, `/data/data/staging`, backed by `/opt/mesflow-deploy-agent/docker/runtime/agent-data`.

## Root cause found during local E2E

The prior deployment start command targeted `postgres mesflow`, which recreated PostgreSQL during an otherwise application-only update. This contradicts the shared-DB contract.

## Corrected local runtime evidence

- Agent image/container: `2.14.1-docker-runtime`, loopback port `8090`.
- Staging compose validation executed exactly with `--env-file /opt/mesflow/.env`.
- Migration check ran `alembic heads`; it did not run a migration.
- Same-version retry logged the explicit replacement warning and completed.
- PostgreSQL container ID stayed `a1807d38e7b5b91fa9de560cbd27390ab06a2289c58eecf5fe771592771e05d9` before and after retry.

No production host, nginx, firewall, systemd unit, Docker volume, database schema, or business data was intentionally changed.
