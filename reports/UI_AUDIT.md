# Deploy Agent UI Audit

The detailed audit and feature inventory are maintained in `DEPLOY_AGENT_UI_REDESIGN.md`.

Highest-priority findings:

1. Release, QA, ESP and settings were mixed on one long home page.
2. Operations and OTA used independent visual shells.
3. System mutations were too visible in Docker/service tables.
4. There was no status-first default page.
5. Existing APIs were sufficient; the task required navigation and presentation refactoring, not backend replacement.
