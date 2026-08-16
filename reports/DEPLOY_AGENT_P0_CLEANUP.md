# Deploy Agent P0 cleanup

## Baseline inventory

- Workspace source was newer than the stale `/opt/mesflow-deploy-agent`
  snapshot; reconciliation was read-only and imported nothing.
- `agent.py` had 4,773 lines and combined bootstrap, auth, deployment,
  promotion, QA, OTA/tutorial, Operations, incident/predictive, logs and SSH.
- Unscoped pytest traversed ignored `docker/runtime` backups and produced 687
  collection errors. These were environment/test-discovery errors, not 687
  product failures.
- Current-version references disagreed across `VERSION.txt`, README, Docker
  documentation and Windows Compose.
- The bootstrap packager used `cp -a` over the project and removed only a
  subset of local runtime files afterward.

## Result

- Canonical version: `2.23.2-docker-runtime`.
- Canonical baseline: `168 passed`, zero failures/skips.
- Clean extracted package subset: `141 passed`; excluded tests require sibling
  MESFlow source or frozen workspace artifacts and passed in the workspace run.
- Docker validation image built and imported successfully.
- Source ZIP: 99 files, 226,882 bytes,
  `085bed801b4e7f95bcc7f25cd122c8c2649ac34e6e470e7d7e7f7036958d7c15`.
- First backend extraction: read-only health collection and bounded command
  result handling moved to `agent_backend/system_health.py`; existing route,
  startup and response contracts remain in `agent.py`.
- Alembic migration check is not applicable to Deploy Agent because it has no
  Alembic-managed database schema.

No Production deployment, restart, database, nginx, firewall, systemd or
destructive Docker action was performed.
