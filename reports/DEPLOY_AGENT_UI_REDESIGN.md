# MESFlow Deploy Agent — IT Operations Center UI Redesign

Date: 2026-08-14  
Deploy Agent version: `2.23.0-docker-runtime`  
Scope: local DEV source and isolated local browser runtime only.

## CURRENT UI AUDIT

The Agent already had the required operational capabilities. The main issue was information architecture: `index.html` mixed release promotion, QA administration, ESP firmware/tutorial, logs and settings; `ops.html` and `ota.html` were separate visual applications without shared navigation.

## FEATURE INVENTORY

| Feature | Current page/source | Current API | Current JS | Decision | Target page |
|---|---|---|---|---|---|
| MESFlow/QA release gate | `index.html` | `/api/release-manager/*`, `/api/qa-release-manager/*` | inline release handlers | KEEP/MOVE | Release & Deploy |
| Production Test/Production promotion | `index.html` | promotion/preflight endpoints | inline guarded actions | KEEP/MOVE | Release & Deploy |
| Release/QA history | `index.html` | persisted Agent state | server-rendered | KEEP/MOVE | Release history anchors |
| Agent update | `index.html` | `/api/release-manager/update-agent` | inline handler | KEEP/MOVE | Agent Update section |
| Host health/predictive | `ops.html` | `/api/ops/summary`, `/api/ops/predictions` | Ops polling | KEEP/REFACTOR | System Health |
| Alerts/incidents/AI diagnosis | `ops.html` | `/api/incidents*` | incident rows/drawer | KEEP/REFACTOR | Alerts / Incidents |
| Docker/services/ports | `ops.html` | `/api/ops/docker`, services, ports | Ops tables | KEEP/REFACTOR | Dedicated system views |
| Bounded logs | `ops.html` | `/api/ops/logs` | bounded log reader | KEEP | System Logs |
| Terminal/SSH | `ops.html` | local/SSH command APIs | allowlisted runner | KEEP/SEPARATE | Advanced Terminal / SSH |
| ESP fleet/OTA | `ota.html` | `/api/esp-ota/*` | OTA polling/upload | KEEP/REFACTOR | ESP Kiosk workspace |
| ESP firmware builder | `index.html` | `/api/esp-builder/*` | build handler | KEEP/MOVE | ESP Firmware anchor |
| ESP tutorials | `index.html` | tutorial upload/publish APIs | upload handler | KEEP/MOVE | ESP Tutorial anchor |
| Password/security | `index.html` | `/change-password` | HTML form | KEEP/MOVE | Users & Security |

No duplicate backend feature or replacement deployment API was introduced.

## NEW NAVIGATION

Persistent grouped sidebar: Overview; Operations (Health, Alerts, Incidents, Logs, Diagnostics); Deployment (Release & Deploy, History, Agent Update); ESP Kiosk; System (Docker, Services, Ports, Terminal); Security. Missing capabilities such as a standalone PostgreSQL administration page are not represented as fake pages.

## OVERVIEW

`/` is now a read-only operational summary showing MESFlow, PostgreSQL signal, Deploy Agent, QA Center, server resources, active alerts, core services and recent activity. Build logs, firmware controls, upload forms and terminal are excluded.

## OPERATIONS CENTER

`/ops?view=<workspace>` deep-links to Health, Alerts, Incidents, Diagnostics, Docker, Ports, Logs or Terminal while reusing the existing APIs and polling. Unknown views fall back to Health.

## RELEASE MANAGER

Moved to `/releases`. Existing element IDs, forms, gate evidence, immutable digest verification and API calls remain. MESFlow and QA pipelines remain independent. Production remains visually dangerous and gate-disabled in the local evidence run.

## DOCKER

Dedicated deep link. Restart/stop/start actions are behind an explicit “Thao tác nâng cao” disclosure rather than primary row buttons. Backend permissions, confirmation and audit semantics were not changed.

## SYSTEM LOGS

Dedicated deep link retains bounded 100/200/500/1000-line controls and console presentation.

## DIAGNOSTICS

Existing read-first host/service evidence is preserved. No destructive remediation was added.

## ESP KIOSK

New consolidated Fleet/OTA page uses the existing device, job, upload and cancellation APIs. Firmware and tutorial links lead to their existing working implementations without duplicating business logic.

## QA CENTER

QA deployment remains in Release & Deploy; QA operational status appears on Overview/Health. No duplicate QA runner was created.

## TERMINAL/SSH

Moved under the advanced System group and now carries a visible system-administration/audit warning. Credentials are not displayed or persisted by the UI.

## FILES REFACTORED

- `deploy-agent/agent.py`
- `deploy-agent/templates/index.html`
- `deploy-agent/templates/ops.html`
- `deploy-agent/templates/dashboard.html`
- `deploy-agent/templates/kiosk.html`
- `deploy-agent/templates/_operations_shell_start.html`
- `deploy-agent/templates/_operations_shell_end.html`
- `deploy-agent/static/css/agent.css`
- `deploy-agent/static/js/core/navigation.js`
- `deploy-agent/tests/test_it_operations_ui.py`
- version contract files and version-source test

## API CONTRACT CHANGES

None. Existing API paths and payload semantics were preserved. `/releases` is a new presentation route; `/` is now Overview. `/ops` accepts the additive `view` query parameter.

## BACKEND CHANGES

Small rendering-only extraction `_console_context()`, new `/releases` route, validated Operations `view`, and template context for the shared shell. No deploy/build/OTA backend rewrite.

## BUTTONS LIVE-TESTED

Browser: Playwright 1.62 + installed Google Chrome, isolated Agent on `127.0.0.1:18090/agent`.

- BUILD RELEASE: request observed; queued/success message rendered. Network response was safely stubbed at browser boundary; no build mutation.
- DEPLOY LOCAL: request observed; deploying/success message rendered. Safely stubbed; no local deployment mutation.
- PROMOTE TEST: request observed; uploading/success message rendered. Safely stubbed; no TEST mutation.
- PROMOTE PRODUCTION GATE: disabled; no production request sent.
- OTA: page, fleet loading, selection/form contract and job controls rendered against the real Agent; external kiosk dependency was stubbed to an empty successful fleet for zero-console-error verification.
- FIRMWARE BUILD: request observed and `QUEUED` UI rendered; browser response stubbed; no firmware build executed.
- TUTORIAL: existing form/action IDs and upload contract covered by regression tests; no tutorial package published in this task.

## PLAYWRIGHT 1920x1080

PASS: Overview, Releases, Health, Incidents, Docker, Logs, Kiosk; no page-level horizontal overflow.

## PLAYWRIGHT 1366x768

PASS: same seven workspaces; sidebar/layout remained usable; no page-level horizontal overflow.

## PAGE ERRORS

`0` in the dependency-isolated final browser run.

## CONSOLE ERRORS

`0` in the dependency-isolated final browser run.

## HORIZONTAL OVERFLOW

`0/14` tested viewport/page combinations.

## SCREENSHOTS

Stored in `reports/deploy-agent-ui/`: `overview`, `releases`, `health`, `incidents`, `docker`, `logs`, `kiosk` at both target viewports, plus an incident drawer evidence image.

## TESTS

- Python compile: PASS.
- Focused UI/route/API regressions: PASS.
- Full Deploy Agent suite: `164 passed in 35.73s`.
- Playwright real-browser navigation: PASS.
- Primary release action browser requests: observed for Build, Local, Test and Firmware using safe browser stubs.

## SAFETY

PRODUCTION TOUCHED: **NO**  
PRODUCTION DEPLOYED: **NO**  
TEST DEPLOYED: **NO**  
Destructive Docker command: **NO**

## Known limits

- Firmware and tutorial remain anchors within the Release workspace rather than independent server-rendered pages; their capability is not duplicated or removed.
- PostgreSQL status on Overview uses the health/container evidence already available; no fake database administration page was created.
- Browser button tests deliberately stub mutation endpoints. They prove UI request wiring and feedback, not deployment execution.
