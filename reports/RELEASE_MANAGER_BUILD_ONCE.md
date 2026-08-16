# Release Manager: Build Once / Promote Same Artifact — fix + verification

Follow-up to `reports/WORKSPACE_AND_DEPLOYMENT_RESTRUCTURE.md`, which
flagged that `mesflow-app:65.8.44.65` had two different image digests.

## Incident recap

`artifacts/releases/65.8.44.65/release.json` recorded digest
`sha256:2eab8b55...` (built 2026-08-12T22:58:32+00:00), but the running
`mesflow-app` container was pinned by digest to `sha256:0c439f758...`
(built 2026-08-13T03:28:51+07:00, per the deployed `/opt/mesflow/release.json`).
Root cause: `build-release.sh` unconditionally overwrote
`artifacts/releases/<version>/{release.json,PROMOTION.json,checksums.txt}`
and retagged `mesflow-app:<version>` on every run, with no check for a
prior build under the same version.

## Fix

1. **`mesflow/scripts/build-release.sh`**
   - Refuses to build if `artifacts/releases/<version>/release.json`
     already exists (`VERSION_ALREADY_RELEASED`).
   - Builds into a disposable tag first; refuses to retag
     `mesflow-app:<version>` over a different existing image id
     (`IMAGE_TAG_CONTAMINATED`).
   - Fixed a second, independent bug found while writing this guard:
     `schema_revision` detection used `find app -path '*alembic*'`, which
     never matches anything (migrations live under
     `app/migrations/versions/`, not a path containing "alembic") — every
     release built before this fix had `schema_revision: ""`. Replaced
     with a proper resolution of the Alembic revision/down_revision graph.
2. **`artifacts/releases/65.8.44.65/CONTAMINATED.json`** — new file (the
   protected `release.json`/`checksums.txt`/ZIP were never touched) marking
   65.8.44.65 permanently unpromotable. Per instruction, it was not
   rebuilt; the next version is 65.8.44.66.
3. **`deploy-agent/agent.py`** — `_release_contamination()` checks the
   marker AND live tag drift (image id recorded in `release.json` vs. what
   the Docker tag currently resolves to) so a future incident of the same
   shape is caught automatically, not just this one version. Refused by
   Deploy Local and Promote Test.
4. **LOCAL_PASS/TEST_PASS were dead code** — `promotion-state.json` was
   read in `_release_summary()` but nothing ever wrote to it; every
   "PASS" shown previously was either stale or a manually-placed file
   (`/opt/mesflow-deploy-agent/docker/promotion-state.65.8.44.65.json`).
   Implemented `_record_local_deploy_result()` (real evidence: running
   image id vs. frozen id, applied Alembic head vs. expected, HTTP smoke
   check) and the Promote Test job, both writing real state.
5. **Promote Production Test** implemented end-to-end (was a disabled
   button with no server endpoint): `POST /api/release-manager/promote-test`
   — see `docs/operations/BUILD_AND_PROMOTE.md`.
6. **Promote Production** wired with full gate logic but does not execute:
   `POST /api/release-manager/promote-production` returns 403/501 unless a
   human sets `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` on the Agent and
   confirms — neither was done in this task.
7. **Installer bug found and fixed while redeploying this change**:
   `installer/install.sh`'s existing-container rollback strategy (rename,
   then restore-by-rename on failure) does not actually work —
   `docker compose up --force-recreate` identifies a service's container by
   Compose project/service labels, not name, so the renamed container was
   removed anyway (verified empirically). Rewrote to capture the previous
   container's image id and roll back by redeploying that id.

## Live verification

- Rebuilt and redeployed the local DEV Agent from workspace source twice
  (2.17.0, then 2.17.1 after finding `git` was missing from the Agent's
  own Docker image — `build-release.sh`'s `git rev-parse HEAD` was
  silently failing inside the container, recording `source_commit:
  "unknown"`; fixed by adding `git` to `docker/Dockerfile`).
- `POST /api/release-manager/build` (both via direct API call and,
  separately, a Playwright browser click) produced a real, immutable
  65.8.44.66 release: `artifacts/releases/65.8.44.66/release.json` shows
  `schema_revision: "0029_kiosk_ota_fleet_safety"` (previously always
  empty) and `image_digest`/`image_id` both `sha256:47c208fd...`.
- Deploy Local, Promote Test button gating, and Promote Production's
  refusal path were exercised live — see the RESULT block in
  `reports/WORKSPACE_AND_DEPLOYMENT_RESTRUCTURE.md` (this file's sibling
  report is the source of record for the exact pass/fail evidence and
  console-error check).
- `deploy-agent` pytest: 56/56 (was 48/56 — 8 pre-existing failures fixed,
  none weakened; see the `test:` commit for the failure-by-failure
  breakdown).

## What was deliberately not done

- 65.8.44.65 was not rebuilt or deleted.
- The `mesflow` sync branch was not merged to `main`.
- No Production deploy was executed; `MESFLOW_PRODUCTION_PROMOTE_ENABLED`
  was not set on any Agent.
- Promote Test was not exercised against the real remote Production Test
  Agent (`deploy.mesflow.net`) — only its safe-fail path (no target
  configured on this DEV Agent) was verified, per instruction to test
  gate/UI/API safely without mutating Production Test unless explicitly
  approved.
