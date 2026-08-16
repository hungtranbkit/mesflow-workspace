# Build Once on LOCAL — Implementation Evidence

Date: 2026-08-14 (Asia/Bangkok)

## Current flow audit

| Component | Canonical LOCAL builder | Immutable output | Target activation | Legacy rebuild found | Resolution |
|---|---|---|---|---|---|
| MESFlow | `mesflow/scripts/build-release.sh` | Docker archive, release manifest, ZIP SHA, image ID/digest | Agent verifies, loads and starts with `--no-build` | Legacy source staging could run `compose build` on any role | Source fallback now fails with `TARGET_SOURCE_BUILD_FORBIDDEN` unless role is DEV and build is explicitly enabled |
| QA Center | `qa-center/scripts/build-release.sh` | Docker archive, release manifest, ZIP SHA, image ID/digest | QA image pipeline verifies, loads and recreates with `--no-build` | Legacy QA source deployment could rebuild runtime on a target | Any legacy QA build now fails outside an enabled DEV Agent; image release path remains receive/load/activate only |
| Deploy Agent | `deploy-agent/scripts/build-agent-release.sh` | Agent image archive, manifest, checksums and immutable update ZIP | Stable updater/Compose loads or selects the image and uses `--no-build` | No target source build in updater; LOCAL bootstrap/build remains intentional | Added advertised `build_once_local` capability and normalized policy output |

The old source deployment compatibility code remains only for explicit DEV/LOCAL use. It is no longer a fallback on TEST or PRODUCTION. Transfer/load failure is a deployment failure, never an instruction to rebuild source.

## Policy enforced

Normal target actions are:

1. receive
2. verify
3. load
4. activate
5. health/version verification
6. rollback from retained artifact

`_source_build_allowed()` requires both `SERVER_ROLE=DEV` and `MESFLOW_BUILD_ENABLED=true`. The Deployment Platform API reports:

- build environment: `LOCAL`
- TEST rebuild: `false`
- Production rebuild: `false`
- target action contract listed above

The legacy MESFlow start helper was also changed from rebuilding MESFlow and PostgreSQL together to app-only `up -d --no-build --no-deps mesflow`.

## LOCAL immutable Agent release evidence

- Component: Deploy Agent
- Version: `2.23.6-docker-runtime`
- Source commit recorded by builder: `833dfb8738411e95c52f6ba7a8524cc5059a3df3`
- Artifact: `artifacts/deploy-agent/releases/2.23.6-docker-runtime/AGENT_UPDATE_2.23.6-docker-runtime.zip`
- Artifact size: `193182845` bytes
- ZIP SHA256: `a4808bb11657e57577cca448118a5c48d0db5903a984471e7656d162faf0c2a5`
- Image: `mesflow-deploy-agent:2.23.6`
- Manifest/running image digest: `sha256:529316e0829c03530ba2d9d106d158f402bde7739d4e3b4b5cb5eeb5e494848f`
- Internal archive checks: PASS (`tar` and `agent-release.json`)
- LOCAL activation: `docker compose ... up -d --no-build --no-deps --force-recreate mesflow-deploy-agent`
- Running health/version: PASS, `2.23.6-docker-runtime`
- Running digest match: PASS
- MESFlow container restarted: NO (ID unchanged)
- PostgreSQL container restarted: NO (ID unchanged)
- QA Center container restarted: NO (ID unchanged)

The first activation command used the wrong Compose project name and was rejected by Docker before mutation because the existing container name was owned by project `docker`. Ownership labels were inspected, then activation was repeated using the exact existing Compose project/files. No manual container removal was used.

## Tests

- Focused build/deploy/rollback/retention/self-update: `72 passed, 8 subtests passed`
- Full Deploy Agent suite, split only to preserve reliable output from a legacy stdout-affecting test:
  - group 1: 117 cases, exit code 0
  - group 2: `80 passed`
  - total collected/executed: 197, required failures: 0
- Python compile: PASS
- `git diff --check`: PASS
- New policy regression tests cover target source-build rejection, QA no-build activation, three canonical immutable builders, advertised capability and Deployment Platform policy.

## Component matrix

| Capability | MESFlow | QA Center | Deploy Agent |
|---|---:|---:|---:|
| LOCAL build only (normal release path) | YES | YES | YES |
| Immutable artifact | YES | YES | YES |
| LOCAL consumes artifact | YES (existing pipeline) | YES (existing pipeline) | YES (verified live this task) |
| TEST rebuild | NO | NO | NO |
| Production rebuild path | NO (normal path; legacy source rejected on target) | NO (normal path; legacy source rejected on target) | NO |
| Digest verification | YES | YES | YES |
| Rollback without build | YES | YES | YES |

## Resource behavior removed

Normal TEST/Production promotion performs no Docker build, frontend/npm build, Python packaging build or source compilation. It consumes the Docker archive already built on LOCAL. Environment differences remain runtime configuration; no per-environment application image is created.

## Verification boundaries

- Actual TEST promotion was not executed in this task. Target behavior is covered by capability/contract and deployment regression tests.
- Production candidate paths are prepared and build-disabled, but Production was not contacted or mutated.
- No claim is made that a new MESFlow or QA application release was deployed; those canonical builders and image-promotion implementations were inspected and protected by the new target-side guard.

## Safety

- Production deploy: NO
- Production restart: NO
- Production database migration: NO
- Production rollback: NO
- nginx/firewall/systemd mutation: NO
- destructive Docker cleanup: NO
