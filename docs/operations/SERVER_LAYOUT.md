# Server Layout

Filesystem layout on a MESFlow host (DEV, Production Test, or Production —
the paths are the same; what's *allowed to run* on each differs, see
`BUILD_AND_PROMOTE.md`).

```
/home/<user>/workspace/mesflow/     DEV ONLY — source of truth, not present
                                     on Production Test/Production hosts
├── mesflow/                        git repo — MESFlow core source
├── deploy-agent/                   git repo — Deploy Agent source
├── qa-center/                      git repo — QA Center source
├── esp-kiosk/                      git repo — ESP32 firmware source
├── artifacts/
│   ├── mesflow/                    ad-hoc/legacy release zips
│   ├── deploy-agent/
│   ├── qa-center/
│   ├── esp-kiosk/
│   ├── esp-firmware/               firmware build output (never in esp-kiosk/)
│   ├── tutorials/                  tutorial video packages
│   └── releases/<version>/         canonical build-release.sh output:
│                                   release.json, PROMOTION.json,
│                                   checksums.txt, *.deploy.zip
├── reports/                        audit/review/test reports
├── scripts/                        status.sh, audit-environments.sh,
│                                   build-release.sh, deploy-local.sh,
│                                   promote-test.sh, reconcile-from-opt.sh
└── docs/

/opt/mesflow/                       DEPLOYED — no app source
├── compose.yml
├── .env                            secrets, 0600
├── release.json                    frozen identity of what's deployed
├── VERSION.txt
├── checksums.txt
├── PROMOTION.json
├── MESFlow_<version>.tar           image bundle (image-release mode)
├── certs/
└── runtime/                        bind-mounted into the container
    ├── postgres-v65/               PostgreSQL data — DO NOT MOVE casually
    ├── backups/
    ├── uploads/
    ├── tutorials/
    └── firmware/

/opt/mesflow-deploy-agent/          DEPLOYED — compose/config, Dockerfile
├── docker/
│   ├── compose.linux.yml
│   ├── compose.bootstrap.override.yml
│   ├── compose.dev.override.yml    (DEV role only)
│   ├── compose.production-test.override.yml
│   └── Dockerfile
├── installer/
│   └── install.sh                  sudo bash install.sh — see NEW_SERVER_INSTALL.md
└── (legacy: agent.py, templates/, tests/ — becoming build-context-only,
    see PHASE 12 / Dockerize note below)

/opt/mesflow-qa-center/             DEPLOYED — compose/config + versioned dirs
├── current/
├── previous/
└── runtime/

/var/lib/mesflow-deploy-agent/      PERSISTENT — survives reinstall
├── config/
├── state/
├── releases/
├── staging/
├── uploads/
├── backups/
├── logs/
└── ota/
```

## Notes specific to this host (verified during the restructure audit)

- MESFlow's PostgreSQL data is a **bind mount**, not a named Docker volume:
  `/opt/mesflow/runtime/postgres-v65` → `/var/lib/postgresql/data`. This is
  the existing safe location; it was **not** moved, per policy (never
  migrate PostgreSQL storage for directory aesthetics alone).
- The running `mesflow-deploy-agent` container already mounts
  `/var/lib/mesflow-deploy-agent` as `/data` — the runtime-path migration
  described in `reports/SOURCE_OF_TRUTH_MIGRATION_20260813_102803.md` is
  live, not just documented. The old `/opt/mesflow-deploy-agent/docker/runtime/agent-data`
  (and the equivalent path that used to exist under the workspace source
  tree) is legacy and should not be treated as the live data location.
- `/opt` currently also holds ~13 timestamped `mesflow-deploy-agent.backup-*`
  / `mesflow-deploy-agent-backup-*` directories from prior manual
  reinstalls. These were **not** touched by this restructure (Phase 15:
  don't delete legacy without certainty) — they are cleanup candidates once
  someone confirms none of them are needed for rollback.
- `/opt/mesflow-qa-center` has no app source either (`current/` and
  `previous/` hold docs/config/compose, not a full editable source tree) —
  already compliant with the target model.

## New-server checklist

See `NEW_SERVER_INSTALL.md`.
