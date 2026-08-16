# DEV / Production Test setup

- Workspace reconcile completed for MESFlow and Deploy Agent.
- DEV artifact: MESFlow `65.8.44.65`, digest `sha256:0c439f75840b149dcdc51d8164bcd20ee9695ed1636491543fb05a52b289a6e1`.
- Production Test host `mesflow-test` has an Agent bound to `127.0.0.1:8090`.
- Its current runtime does not declare `SERVER_ROLE` or `MESFLOW_BUILD_ENABLED`; it is not yet compliant with receive-only Production Test mode.
- This workspace has no local Agent listening on `127.0.0.1:8090`, so real local Agent cutover is not verified in this run.

Required bootstrap: run DEV Agent with `compose.linux.yml` plus `compose.dev.override.yml`; configure Test Agent with `SERVER_ROLE=PRODUCTION_TEST` and `MESFLOW_BUILD_ENABLED=0`. No MESFlow/Test database mutation was performed.

```text
DEV Agent: NOT VERIFIED
Production Test Agent: NEED CONFIGURATION
Build artifact: PASS
Local image deployment: NOT VERIFIED
Production Test promotion: NOT RUN
Production: NOT DEPLOYED
```
# LOCAL / PRODUCTION TEST SETUP

## Current evidence (2026-08-13)

DEV Agent is running on `127.0.0.1:8090` with `SERVER_ROLE=DEV`,
`MESFLOW_BUILD_ENABLED=true`, source bind-mounted at `/workspace/mesflow`,
and the release artifact directory readable in-container.

The image release `65.8.44.65` was deployed through the local Agent image-release
path (not a manual compose deploy). The deployed image is
`mesflow-app:65.8.44.65@sha256:0c439f75840b149dcdc51d8164bcd20ee9695ed1636491543fb05a52b289a6e1`.
Local Agent job status was `success`; MESFlow health and version endpoints returned
healthy / `65.8.44.65`; login HTML smoke passed.

Production Test Agent was then configured through a TEST-only compose override with
`SERVER_ROLE=PRODUCTION_TEST` and `MESFLOW_BUILD_ENABLED=false`. Its health endpoint
is healthy and reports Agent `2.16.10-docker-runtime`; it still runs MESFlow
`65.8.44.64` because no promotion was performed.

## Promotion state

```text
LOCAL_PASS: YES (65.8.44.65, digest sha256:0c439f...)
PRODUCTION_TEST_AGENT: HEALTHY / PRODUCTION_TEST / BUILD_DISABLED
PRODUCTION_TEST_PROMOTION: TEST_PASS (same artifact deployed)
PRODUCTION: NOT DEPLOYED
```

The target URL used was `https://deploy.mesflow.net/agent` through the existing
HTTPS nginx route. Authentication used the existing Agent admin session contract
for the controlled test upload; no token or password was written to source.

Evidence:

* DEV ZIP SHA256: `556617feffeda5bdda2484da4b774d6feb6568f638c068934f3cd5c8b20c97ac`
* Test Agent job: `success`, deployment verified `65.8.44.65`
* Test container image: `mesflow-app:65.8.44.65@sha256:0c439f75840b149dcdc51d8164bcd20ee9695ed1636491543fb05a52b289a6e1`
* Test MESFlow health/version: healthy / `65.8.44.65`
* Test schema: `65.8.44.60`
* Test login smoke: PASS
* Test deploy log explicitly records `IMAGE RELEASE MODE`, image bundle load,
  `IMAGE VERIFIED ... no server-side docker build`, and final health/version PASS.
