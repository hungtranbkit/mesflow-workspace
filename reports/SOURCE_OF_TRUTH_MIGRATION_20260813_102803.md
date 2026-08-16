# MESFlow Source-of-Truth Migration

- Date: 2026-08-13T10:28:03+07:00
- Mode: apply
- Workspace source-of-truth: `/home/dell/workspace/mesflow`
- Policy: `/opt` is deployed/runtime state, not development source.

## Project audit

### mesflow

- Workspace: `/home/dell/workspace/mesflow/mesflow`
- Deployed: `/opt/mesflow`
- Workspace version: `65.8.44.65`
- Deployed version: `65.8.44.65`
- Source diff: **DIFF**
- Diff file: `/home/dell/workspace/mesflow/.reconcile/20260813_102803/mesflow/diff.txt`

### deploy-agent

- Workspace: `/home/dell/workspace/mesflow/deploy-agent`
- Deployed: `/opt/mesflow-deploy-agent`
- Workspace version: `2.16.10-docker-runtime`
- Deployed version: `2.16.11-docker-runtime`
- Source diff: **DIFF**
- Diff file: `/home/dell/workspace/mesflow/.reconcile/20260813_102803/deploy-agent/diff.txt`

### qa-center

- Workspace: `/home/dell/workspace/mesflow/qa-center`
- Deployed: `/opt/mesflow-qa-center`
- Workspace version: `unknown`
- Deployed version: `unknown`
- Source diff: **DIFF**
- Diff file: `/home/dell/workspace/mesflow/.reconcile/20260813_102803/qa-center/diff.txt`

## Deploy Agent runtime

- Old path: `/opt/mesflow-deploy-agent/docker/runtime/agent-data`
- New path: `/var/lib/mesflow-deploy-agent`
- Migration: copied runtime to new path
- Old runtime: preserved for rollback

## Recommended final layout

```text
/home/dell/workspace/mesflow/
├── mesflow/            # source
├── deploy-agent/       # source
├── qa-center/          # source
├── esp-kiosk/          # source
├── artifacts/          # generated deployable artifacts
├── reports/
└── scripts/

/opt/mesflow/                  # deployed runtime/config only
/opt/mesflow-deploy-agent/     # compose/config only
/opt/mesflow-qa-center/        # deployed runtime/config only
/var/lib/mesflow-deploy-agent/ # persistent Agent data
```

## Safety

- No /opt source was deleted.
- No database was changed.
- No production deploy/restart was performed.
- Review generated diffs before deleting any legacy /opt source.
