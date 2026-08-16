# Reconcile deployed source from /opt

```bash
cd ~/workspace/mesflow
./scripts/reconcile-from-opt.sh mesflow
./scripts/reconcile-from-opt.sh deploy-agent
./scripts/reconcile-from-opt.sh qa-center
./scripts/reconcile-from-opt.sh all
```

The command:
- reads `/opt/...`
- creates sanitized snapshots under `tmp/reconcile/`
- excludes secrets/runtime/database/logs/certs/caches
- creates source diffs
- writes reports under `reports/`
- never overwrites workspace
- never modifies `/opt`

Short Codex instruction:

`sync deployed rồi làm tiếp`
