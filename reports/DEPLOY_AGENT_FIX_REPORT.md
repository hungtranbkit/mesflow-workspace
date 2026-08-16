# Deploy Agent fix report — 2026-08-12

AGENT VERSION: `2.14.1-docker-runtime` local image/runtime.

ROOT CAUSE: App cutover started both `postgres` and `mesflow`; Compose recreated PostgreSQL. The corrected start contract requires an existing healthy PostgreSQL and starts only `mesflow` with `--no-deps`.

UPLOAD TEST: Real authenticated multipart upload of `MESFlow_65.8.44.48_e2e.zip` (2,250,673 bytes) reached backend. Logs record request, saving, bytes, extraction, root, version, stored release, and job start.

ZIP VALIDATION: Valid ZIP, single root, `VERSION.txt`, `compose.yml`, `release.json`, version `65.8.44.48`; retry correctly reported replacement of old release staging. Zip-slip/symlink and extraction-size guards were added to source.

COMPOSE VALIDATION: PASS. `docker compose --env-file /opt/mesflow/.env -f <staging>/compose.yml config --quiet` completed. `.env` was readable at `0600` by the root Agent container; no mode change was made.

BUILD: PASS. Log contains `BUILD START`, `BUILD IMAGE mesflow`, `BUILD DONE elapsed=1.0s` (cached local image).

DEPLOY: PASS locally. Application container recreated; PostgreSQL was preserved on final retry.

SHARED DATABASE: YES. Data mutation remains possible through normal UI/API actions. No clone/reset/new database, volume deletion, or migration occurred.

HEALTH: PASS: application and PostgreSQL containers healthy; `/api/system/health` reports PostgreSQL and healthy status.

VERSION VERIFY: PASS: `/api/system/version` returned `65.8.44.48`, equal to expected release version.

BROWSER TEST: Playwright login/select-file test: file selector and manual `Upload & Deploy` button present; selected filename/size shown; auto-upload POST reached `/agent/upload`; no browser console errors. The browser-triggered job reached `Deployment verified: 65.8.44.48`.

QA REGRESSION: Smoke PASS: QA Center health remained online at `1.19.6`; QA upload controls remain present. No QA deployment was run.

TUTORIAL REGRESSION: Smoke PASS: rebuild and preflight controls remain present; no long-running rebuild was started.

FILES CHANGED: `deploy-agent/agent.py`, version/image/compose files, installer scaffolding, package script, documentation, and this report set. Generated installer: `artifacts/deploy-agent/MESFlow_Server_Bootstrap_Agent_First_v2.14.1-docker-runtime.zip`.

KNOWN ISSUES: Source tree was unexpectedly restored to an older `2.13.1` baseline during the work; the key version/safety/timeout changes were reapplied and syntax/Compose config checked. The live local image tested was built from the complete earlier `2.14.1` state. Historical static tests are not runnable as-is because they reference a missing old `payload/` path and old versions.

PRODUCTION ACTION REQUIRED: YES — human review is required before any production installation/deploy. This task performed local-only deployment; no production action was taken.

Migration: no. Production action performed: no.
