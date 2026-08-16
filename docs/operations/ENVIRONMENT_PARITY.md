# MESFlow Environment Parity

## Promotion rule

```text
CODE
  ↓
LOCAL BUILD (once)
  ↓
LOCAL AGENT DEPLOY
  ↓
LOCAL VERIFY
  ↓
FREEZE ARTIFACT + SHA256
  ↓
PRODUCTION TEST PREFLIGHT + PARITY COMPARE
  ↓
SAME ARTIFACT DEPLOY THROUGH AGENT
  ↓
PRODUCTION TEST VERIFY
  ↓
HUMAN APPROVAL
  ↓
PRODUCTION
```

Local success never proves Production Test readiness. Promotion requires two current fingerprints, zero `BLOCKER` differences, and verification of the exact artifact hash.

## Environment contract

MESFlow uses the release `mesflow/compose.yml` in both environments. Environment-specific values belong in protected files outside Git. A tiny override is permitted only for ports, domain/gateway integration and reviewed resource limits. Service names, images, entrypoint, application port, healthchecks, dependency ordering, network semantics and persistent mounts must not fork.

The canonical environment-key contract is [`config/env.schema`](../../config/env.schema). [`.env.example`](../../.env.example) contains placeholders only. Real `.env` files must normally be mode `0600` (or `0640` with a deliberately controlled group). Never copy production secrets into the workspace.

The application/business timezone is `Asia/Ho_Chi_Minh`. PostgreSQL uses `PGTZ=UTC`; application timestamps remain UTC internally and UI/business rules convert using the configured MESFlow timezone. A host timezone difference is a warning that requires explicit review, especially for midnight/night-shift and multi-day QA tests.

Persistent paths are:

- `/opt/mesflow/runtime/postgres-v65`
- `/opt/mesflow/runtime/uploads`
- `/opt/mesflow/runtime/backups`
- `/opt/mesflow/runtime/tutorials`
- `/opt/mesflow/runtime/tutorials/esp-kiosk`
- Deploy Agent `/data` mapped to its protected runtime directory

Do not fix permissions with `chmod -R 777`. Use the owning service user/group, setgid directories where shared publishing is required, and the least write access necessary. MESFlow mounts tutorials read-only; the Agent/publisher owns publication.

## Commands

Run read-only preflight and create a fingerprint:

```bash
./scripts/environment-preflight.sh local
./scripts/parity-check.sh local

./scripts/environment-preflight.sh production-test
./scripts/parity-check.sh production-test
```

On a remote test server, run the same checked-out tooling there or stream the fingerprint collector over SSH without installing it. Compare captured reports:

```bash
./scripts/compare-environments.sh \
  reports/environment/local.json \
  reports/environment/production-test.json
```

Preflight is audit-only: it does not create networks/directories, change permissions, edit env files, start containers or migrate databases. Missing prerequisites are `FAIL`, not auto-repaired.

## Build once and promotion record

Build one versioned ZIP locally and immediately freeze it:

```bash
sha256sum artifacts/mesflow/MESFlow_<version>.zip
```

Create `artifacts/releases/<version>/PROMOTION.json` from the reviewed promotion template/record. It must contain the ZIP filename, version, SHA256, source commit, build time, local Agent version, schemas before/after, browser result, QA result and Production Test status. It must not contain credentials. Never regenerate the ZIP after local verification; any byte change creates a new artifact and invalidates the local gate.

Before Production Test upload, verify filename/version and SHA256 against `PROMOTION.json`, query the current runtime version/schema, review the migration path and confirm the backup policy. A mismatch stops promotion. Metadata is evidence, not trust: Deploy Agent must still validate ZIP structure, compose, migrations, health, database and running version.

## Verification gates

Local Agent deployment must record upload, ZIP validation, compose validation, image preparation, migration preflight, deploy, `/api/system/health`, `/api/system/version`, `/api/system/ready`, database/schema and browser smoke results in `reports/LOCAL_DEPLOY_VERIFICATION.md`.

Production Test uses the same ZIP and Agent workflow. After deployment verify health, exact version, schema/head, recent logs, browser smoke, a safe Session start/finish flow, tutorial tab, ESP tutorial playback, Agent health and QA connectivity. On failure, use the Agent rollback contract; never repair the test database manually to make a deployment appear successful.

## QA profiles

QA Center uses one scenario source. `LOCAL` and `PRODUCTION_TEST` profiles may change only base/internal URL, credentials, duration and load. Test data differences are expected and must not influence application behavior. Cleanup remains limited to recognizable QA-owned fixtures.

## Approval boundary

This workflow stops after Production Test evidence. Production deploy, restart, migration, nginx cutover and other production mutations require explicit human approval.
