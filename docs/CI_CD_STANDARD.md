# MESFlow Workspace — Universal CI/CD Standard V1

Status: **PASS_FOUNDATION**. This document is normative for every project
in this workspace. It does not replace GitHub (PR/Actions/Environments) or
turn Deploy Agent into a CI/CD platform; it defines the contract every
project already has or should adopt, and the shared logic
(`scripts/ci/`) that reads that contract generically.

Every coding agent must read this file, `AGENTS.md`, and the affected
project's `PROJECT.yaml` before making a non-trivial change.

## 0. Terms

- **Workspace** — this repository, `/home/dell/workspace/mesflow`.
- **Project** — a directory with its own version/build/test/artifact/
  deploy lifecycle, registered in `WORKSPACE.yaml` and described by its
  own `PROJECT.yaml`. Today: `mesflow/`, `deploy-agent/`, `qa-center/`,
  `esp-kiosk/`. See the "PROJECT DISCOVERY" section of the most recent
  `AGENT RULES`/audit report for the full current classification
  (MANAGED / UNMANAGED / registry gaps).
- **Contract** — a project's `PROJECT.yaml`: machine-readable
  preflight/test/build/smoke/deploy commands, artifact strategy, and
  deployment policy.

## 1. Git workflow

```
main
 ^
 feature/*
```

Flow: `feature branch -> PR -> CI -> review -> merge main`.

No GitFlow (no `develop`, no long-lived `release/*` branches) by default.
`main` is always deployable-in-principle (CI green); production promotion
is a separate, human-gated step (§3), not "merge to main = deployed".

Branch naming: `feature/<slug>`, `fix/<slug>`, matching whatever a given
project's own history already uses if more specific.

## 2. CI lifecycle

For every affected project, in order (a project skips a stage it has not
declared in `PROJECT.yaml`; the runner reports that explicitly, it never
silently treats "not declared" as "passed"):

```
discover affected projects
  -> load project contracts (PROJECT.yaml)
  -> preflight
  -> static/lint
  -> unit
  -> integration
  -> migration
  -> critical/behavior
  -> E2E where applicable
```

MESFlow's reference contract expresses "static/lint, unit, integration,
migration, critical/behavior, E2E" as ONE `commands.test` entry
(`scripts/projectflow/test.sh` -> `scripts/test/docker-test.sh`, which
already runs all of those buckets against real PostgreSQL/API containers
in sequence) rather than one YAML step per bucket — this is intentional
reuse, not a gap. A project may instead declare separate stages if that
fits its own tooling better; the workspace CI matrix does not require one
specific granularity, only that declared stages are real and pass.

## 3. Release lifecycle

```
main @ exact SHA
  -> BUILD ONCE
  -> artifact
  -> SHA256
  -> manifest
  -> qualification (TEST)
  -> approval
  -> PRODUCTION
```

- **Build once**: a given `(project, version)` is built exactly once. Never
  rebuild the same version onto different bytes (MESFlow already enforces
  this in `scripts/build-release.sh` and the Deploy Agent's
  `_release_contamination()` check — see `AGENTS.md` RULE 5).
- **Artifact identity**: `{project}-{version}.deploy.zip` (or the
  project's existing artifact naming) plus a manifest (§6).
- **Qualification**: TEST environment runs the exact same artifact. This
  reuses ProjectFlow's qualification/evidence vocabulary conceptually
  (PASS/FIX_REQUIRED/BLOCKED, evidence-backed) without importing
  ProjectFlow as a dependency of this workspace.
- **Approval**: production promotion is a human-gated action. No agent
  triggers it on its own judgment.

## 4. Same-artifact rule (normative)

```
TEST_ARTIFACT_SHA256 == PRODUCTION_ARTIFACT_SHA256
```

If the digest that qualified in TEST does not match the digest about to be
promoted to PRODUCTION:

```
PRODUCTION BLOCKED
```

No exceptions, no "rebuild and it should be equivalent." This is checked
mechanically by `scripts/ci/same_artifact_check.py` (§7), not left to
reviewer judgement.

## 5. Evidence

Every release/deploy record should carry, at minimum:

- project
- version
- commit (git SHA)
- artifact digest (SHA256)
- tests (what ran, pass/fail, what was skipped and why)
- environment (local/test/production)
- target
- health check result
- smoke test result
- deployment result
- rollback result (if triggered)

`scripts/ci/release_manifest.py` (§7) writes the subset of this that is
knowable at build time (project/version/commit/artifact/digest); the rest
is produced by each project's own smoke/deploy tooling, which this
foundation does not replace (§9).

## 6. Multi-project discovery

Discovery prefers the existing registry, `WORKSPACE.yaml`
(`projects:` list, each with `code`/`root`/`manifest`). If a project
directory has a valid `PROJECT.yaml` but is not (yet) listed in
`WORKSPACE.yaml`, it is not silently ignored or silently promoted to
managed status — it is reported distinctly (`UNREGISTERED_CONTRACT`).
`scripts/ci/discover_projects.py` also runs a conservative fallback scan
(`*/PROJECT.yaml`, one level below workspace root) so a missing registry
entry is never fatal to discovery.

Classification per project:

- `MANAGED` — registered in `WORKSPACE.yaml`, `PROJECT.yaml` present and
  parses with the required minimum fields (`project.code`, `source.root`,
  `commands`).
- `UNREGISTERED_CONTRACT` — has a valid `PROJECT.yaml` on disk but is not
  in `WORKSPACE.yaml`'s registry yet.
- `INVALID_CONTRACT` — registered in `WORKSPACE.yaml`, but its
  `PROJECT.yaml` is missing or fails to parse/validate.
- `UNMANAGED` — a real project directory (its own git repo and/or its own
  `AGENTS.md`/`VERSION`) with no `PROJECT.yaml` at all.

A project without a CI contract is never silently treated as passing.

## 7. Changed-project detection

`scripts/ci/changed_projects.py` maps a set of changed paths to affected
projects:

1. **Direct**: a changed path under a managed project's `root` (e.g.
   `mesflow/app/**`) affects that project.
2. **Shared-path expansion**: a changed path under a workspace-shared
   location (`WORKSPACE.yaml` `shared:` entries — `artifacts/`, `reports/`,
   `docs/`, `scripts/` — or the root contract files themselves:
   `AGENTS.md`, `WORKSPACE.yaml`, `PROJECT.yaml` schema, `scripts/ci/**`)
   expands to **every managed project**, since it is a shared-contract or
   shared-tooling change.
3. **Dependency expansion**: if a project `B` changed and another project
   `A` declares a dependency on `B` (via `WORKSPACE.yaml` `dependencies:`
   or `A`'s own `PROJECT.yaml` `dependencies:`), `A` is also marked
   affected (a dependent must react to its dependency changing, even if
   its own files did not change).

When dependency/shared-path metadata is incomplete, the tool is
conservative: it runs more projects rather than silently skipping one it
is unsure about (safety over speed).

## 8. CI matrix

```
detect_projects
  -> matrix
     |- mesflow
     |- qa-center
     |- ...
```

Independent affected projects run in parallel. Each matrix job invokes
that project's own contract via the generic runner:

```bash
scripts/ci/run_project.py mesflow --stage preflight
scripts/ci/run_project.py mesflow --stage test
```

CI never hard-codes a project's own implementation into the workflow YAML
— the YAML only invokes `run_project.py <project> --stage <stage>` for
each affected project/stage pair; the actual command lives in that
project's `PROJECT.yaml`.

## 9. Deploy Agent

Deploy Agent remains the legacy/migration-scope execution mechanism for
real deploys (TEST/staging/production). This standard does not turn it
into (or replace it with) a new CI/CD platform. See "Deploy Agent
migration" in the audit report and `AGENTS.md`'s "Deploy Agent rule".

## 10. Production CD status

A generic, workspace-level deployment runtime (one that any project can
plug into for TEST/PRODUCTION execution, distinct from Deploy Agent) does
not exist yet in this pass. Building it is out of scope for V1. Until it
exists:

```
CI: IMPLEMENTED
BUILD: IMPLEMENTED (per project, already existed for mesflow/deploy-agent/qa-center/esp-kiosk)
ARTIFACT + SHA256 + MANIFEST: IMPLEMENTED (scripts/ci/release_manifest.py)
TEST qualification contract: REUSED (each project's own `deployment.test.enabled`)
PRODUCTION CD: BLOCKED_BY_DEPLOY_RUNTIME
```

This is not worked around with an ad hoc `ssh root@host ...` step. See the
"PRODUCTION CD STATUS" section of the audit report.

## 11. PROJECT.yaml — authoritative contract

Existing schema (already in use by `mesflow/`, `deploy-agent/`,
`qa-center/`, `esp-kiosk/`, `deploy-agent-v2/`) is authoritative and is
**reused, not replaced**:

```yaml
schema_version: 1

project:
  code: ...
  name: ...
  type: ...
  role: ...

source:
  root: .

version:
  file: VERSION.txt   # or version.source_define for firmware

runtime:
  type: docker-compose   # or firmware

commands:
  preflight: {command, working_directory, timeout_seconds}
  test: {...}
  build: {...}
  smoke: {...}
  # ... any other project-specific stage

artifacts:
  strategy: immutable
  directory: ...
  metadata: ...

deployment:
  build_once: true
  promote_same_artifact: true
  local: {enabled, approval_required, notes}
  test: {enabled}
  staging: {enabled, notes}
  production: {enabled, approval_required, projectflow_direct_execution}

dependencies:            # optional, project-local (complements WORKSPACE.yaml)
  - target: ...
    type: TEST | DEPLOY
    evidence: "..."
```

This already covers section-11's suggested `release:`/`deployment:` split
semantically: `artifacts.strategy: immutable` = `release.immutable_artifact`,
`deployment.promote_same_artifact` = `release.same_artifact_required`,
`deployment.production.approval_required` = `release.production_approval`.
**Do not add a second, parallel `release:` block that duplicates
`deployment:`/`artifacts:` — extend those instead.**

### Additive V1 extension: `ci.required`

The one genuinely new, optional, backward-compatible field this standard
adds is `ci.required`: an explicit list of `commands.*` keys that MUST
pass for that project's CI to be green.

```yaml
ci:
  required: [preflight, test]
```

If a project's `PROJECT.yaml` omits `ci:` entirely (every existing file
today does, except `mesflow/PROJECT.yaml` after this pass), the runner
falls back to a conservative default: whichever of `preflight`/`test` the
project has actually declared under `commands:` is required; anything
else declared is optional/best-effort. This means every existing
`PROJECT.yaml` in the workspace continues to work unmodified.

## 12. Artifact model

Each project builds its own artifact under its own name/version — never
one combined workspace artifact:

```
mesflow-71.0.0.80.deploy.zip
qa-center-2.5.0.deploy.zip
```

Manifest (reuses `release.json` semantics where a project already has
one; this is not a second source of truth for version):

```json
{
  "project": "mesflow",
  "version": "71.0.0.75",
  "git_sha": "...",
  "artifact": "mesflow-71.0.0.75.deploy.zip",
  "sha256": "...",
  "built_at": "...",
  "builder": "github-actions"
}
```

## 13. Unmanaged projects

A project without a `PROJECT.yaml` is reported as `UNMANAGED`, never
silently passed. Policy:

- A PR that does **not** touch an unmanaged project's files: CI does not
  block on it. It is listed in the CI summary as "unmanaged, not run."
- A PR that **does** touch an unmanaged project's files: CI **warns**
  (does not hard-block) — because in V1, most of these directories
  (`bootstrap/`, `mesflow-web/`, `esp32-cyd-clock/`) are real, actively
  developed projects that simply have not been given a `PROJECT.yaml` yet,
  and hard-blocking every change to them before migration would defeat
  the point of an incremental rollout. This is a deliberate, documented
  choice, not an oversight — revisit it once a given project is migrated.
