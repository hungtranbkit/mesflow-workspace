# Deploy Agent UI tab/button audit — 2.23.5

Date: 2026-08-14

## Defects found and fixed

- Operations had two elements with `id="alerts"`; tab selection could resolve the KPI element instead of the tab. The KPI is now `healthAlerts`.
- Sidebar links `#deploymentHistory`, `#agentUpdate`, and `#securitySettings` had no target. All now resolve to real targets and scroll visibly.
- Operations refresh actions changed data without user feedback. A shared `aria-live` feedback row now reports loading, result counts and errors.
- Operations tabs now expose `aria-selected` and immediate visible feedback.
- ESP Kiosk Fleet/OTA navigation now has a visible active state and feedback message.
- Services, Network/Ports and Terminal sidebar entries now show their active route.

## Browser evidence

- 1920x1080: Overview, all eight Operations tabs, MESFlow/QA release tabs, Release anchors, Kiosk Fleet/OTA — PASS; horizontal overflow 0.
- 1366x768: Overview, Operations, Releases, Kiosk — PASS; horizontal overflow 0; page errors 0 in isolated DEV fixture.
- Live deployed 2.23.5: tabs and anchors PASS; horizontal overflow 0.
- Live OTA fleet request reports HTTP 503 `MESFLOW_UNAVAILABLE` because `MESFLOW_INTERNAL_API_TOKEN` is not configured for kiosk inventory. The page renders this as an error state; OTA mutation was not attempted.

Screenshots are under `reports/generated/deploy-agent-ui-2.23.4/` (pre-deploy viewport evidence) and `reports/generated/deploy-agent-ui-2.23.5-live/` (live deployed evidence).

## Deployment

- 2.23.4 local verification failed due an incorrect runtime user in the temporary overlay image; `/data` remained preserved but inaccessible. It was immediately rolled back to healthy 2.23.1 and permanently retired without rebuilding the same version.
- 2.23.5 restored the established `USER root` runtime contract, passed source verification, deployed locally and became healthy.
- Running image: `mesflow-deploy-agent:2.23.5`
- Image ID: `sha256:7ffce86a4e6be70ca27206a1fd4317d644c668662e76e9479a20d5ebba894396`
- MESFlow, PostgreSQL, and QA Center container IDs were unchanged across cutover.

## Tests

- Full baseline before final version bump: `191 passed`.
- Final focused UI/version/package suite: `23 passed`.
- Python compile: PASS.
- Source package: `mesflow-deploy-agent-source-2.23.5-docker-runtime.zip`, SHA256 `0a29bc7d78713443c9e14c1c35342b611276aea57aa88f2d66410323c8476ba5`.

## Safety

- Production touched: NO
- Production Test touched: NO
- MESFlow/PostgreSQL/QA restarted: NO
- Destructive Docker command: NO
