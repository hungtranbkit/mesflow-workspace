# P1 Deployment Platform — Implementation Report

Date: 2026-08-14  
Deploy Agent source version: `2.23.3-docker-runtime`

## Current deployment inventory

| Component | Current build/deploy path | Artifact identity | Verification | Rollback/retention | P1 action |
|---|---|---|---|---|---|
| MESFlow | Release Manager builds on DEV, deploys LOCAL, promotes the frozen ZIP/image to TEST/PRODUCTION | Release metadata, ZIP SHA, image ID/digest, schema revision | HTTP health/smoke, running image ID, version/schema | Automatic rollback path and guarded release cleanup already existed | Kept proven mechanics; added common component/read model, state/evidence vocabulary, lock/idempotency/retention service |
| QA Center | Dedicated immutable QA image release, LOCAL deploy, remote TEST promotion | QA release metadata, ZIP SHA, image ID/digest | `/api/version`, image ID and health | Legacy takeover/rollback and guarded QA cleanup already existed | Added to common component/read model and retention preview |
| Deploy Agent | Immutable Agent update ZIP sent to the independent updater | Manifest checksum and image ID | Updater health/version polling | Updater restores previous compose/image on failure | Added to common component/read model; updater contract is covered by regression tests |

The `/opt/mesflow-deploy-agent` reconciliation was read-only. It is an older deployed snapshot (`2.16.11`) and was not copied over workspace source.

## Architecture added

`deployment_platform.py` provides a common high-level platform without replacing component-specific deployment commands:

- explicit `MESFLOW`, `QA_CENTER`, `DEPLOY_AGENT` components;
- explicit `LOCAL`, `TEST`, `PRODUCTION` targets;
- immutable release identity with artifact SHA verification;
- shared deployment state/evidence records and normalized failure categories;
- per-component/per-environment non-blocking deployment lock;
- request idempotency and correlation IDs;
- precheck → stage → activate → repeated health/version/digest verify → commit;
- automatic rollback and post-rollback health/version verification;
- manual rollback service contract;
- rollback-sensitive migration guard (no automatic destructive DB downgrade);
- retention dry-run/apply service protecting current, previous, pinned, active and evidence-referenced releases.

The Release Manager now exposes a common three-component summary and these authenticated APIs:

- `GET /api/deployment-platform`
- `GET /api/deployment-platform/deployments`
- `POST /api/deployment-platform/retention/preview`

Existing mutation APIs remain unchanged. Production still requires the existing explicit approval gates; the common service independently requires per-run Production approval as well.

## Component matrix

| Capability | MESFlow | QA Center | Deploy Agent |
|---|---:|---:|---:|
| Build Once | YES | YES | YES |
| Immutable digest | YES | YES | YES |
| LOCAL deploy | YES | YES | Isolated updater flow only |
| TEST deploy | YES | YES | Staged remote updater path |
| Production-ready flow | YES, approval gated | YES, approval gated | YES, updater target configured and gated |
| Health verify | YES | YES | YES |
| Automatic rollback | YES | YES | YES |
| Manual rollback service contract | YES | YES | YES |
| Retention policy/dry-run | YES | YES | YES |
| Retention apply connected to existing cleanup | YES | YES | PARTIAL — generic safe service tested; no live Agent cleanup endpoint enabled |
| Common history/read model | YES | YES | YES |

## Deployment evidence

The isolated behavioral tests create append-only evidence containing:

```text
release_id        <component>:2.0.0
component         MESFLOW / QA_CENTER / DEPLOY_AGENT
artifact_digest   verified sha256 of the test artifact
from_version      1.0.0
to_version        2.0.0
target            LOCAL (explicit typed environment)
result            HEALTHY or DEPLOY_FAILED + ROLLED_BACK
health_result     PASS/FAIL
rollback_result   NOT_REQUIRED/SUCCESS/MANUAL_SUCCESS
```

No real LOCAL/TEST target was mutated for this task, so there is deliberately no fabricated live deployment ID.

## Retention

Default common policy keeps current, previous, pinned, active deployment, evidence-protected releases and the configured recent-success window. Cleanup preview is non-mutating and reports reclaimable bytes. Apply accepts only exact child directories under the configured release root and refuses symlinks.

Test evidence:

- current release retained;
- previous rollback release retained;
- pinned release retained;
- active deployment retained;
- old unprotected releases selected;
- dry-run performs no deletion;
- apply removes only previewed temporary test releases.

Space reclaimed on real LOCAL/TEST artifact storage: `0 bytes` (no live cleanup was authorized or run).

## Tests

| Command | Result |
|---|---|
| `./scripts/test-baseline.sh` | PASS — `188 passed`; Python compile and source package verification PASS |
| `.venv/bin/pytest -q tests/test_p1_deployment_platform.py tests/test_release_retention_cleanup.py tests/test_qa_release_manager_regressions.py tests/test_updater.py` | PASS — `50 passed` |
| Extract clean source ZIP, compile `agent.py`/`deployment_platform.py`, run extracted `tests/test_p1_deployment_platform.py` | PASS — `20 passed` |

Covered scenarios include successful deploy for all components, invalid/tampered artifact, activation/health/version failure, automatic rollback, manual rollback, duplicate request idempotency, concurrent target lock, Production approval boundary, rollback-sensitive migration, retention dry-run/apply, QA takeover/regression and Agent updater failure/recovery.

## Source artifact

```text
filename: mesflow-deploy-agent-source-2.23.3-docker-runtime.zip
file count: 101
size: 236510 bytes
SHA256: 6997f5515d024e19bcb770d2647ad5abf40d63cb016a434976b27ce06e24f2a5
```

## Remaining gaps

- `DONE`: common identity/state/evidence/lock/rollback/retention service and three-component Release Manager projection.
- `DONE`: isolated rollback and retention behavioral coverage, including Agent updater recovery.
- `PARTIAL`: common evidence store is available to the new orchestration service; older component-specific deployment history remains readable but has not been destructively migrated into it.
- `PARTIAL`: Deploy Agent release cleanup has dry-run/common service coverage; a live apply endpoint is intentionally deferred until its protected-release policy is exercised against a configured non-production target.
- `BLOCKED`: true same-artifact LOCAL → TEST demonstration was not run because this task did not explicitly request TEST mutation and no target artifact was selected. Do not claim P1 end-to-end deployment complete until that demonstration exists.

## Production safety

```text
NO PRODUCTION DEPLOY
NO PRODUCTION RESTART
NO PRODUCTION DB MIGRATION
NO PRODUCTION ROLLBACK
NO FIREWALL/NGINX/SYSTEMD CHANGE
NO DESTRUCTIVE DOCKER ACTION
```
