# MESFlow Workspace Architecture

```text
mesflow/
├── AGENTS.md
├── mesflow/          Core MES application
├── deploy-agent/     Release upload/deploy/rollback/gateway
├── qa-center/        Independent QA/regression/soak test
├── esp-kiosk/        ESP32-S3 firmware
├── server-agent/     Optional server monitoring/SSH agent
├── docs/
├── prompts/
├── scripts/
├── reports/
├── test-data/
├── artifacts/
└── tmp/
```

Runtime relationship:

```text
ESP Kiosk
    |
    v
MESFlow API <---- QA Center
    |
    +---- PostgreSQL

Deploy Agent ----> MESFlow release lifecycle
     |
     +---- QA Center release lifecycle
     |
     +---- nginx gateway integration

Server Agent ----> host/service/docker/ssh monitoring
```

Development workspace is intentionally separate from production runtime directories.
