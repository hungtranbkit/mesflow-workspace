# MESFlow Workspace — Universal CI/CD Standard V1

Status: **PASS_FOUNDATION**. This document is normative for every project
in this workspace. It does not replace GitHub (PR/Actions/Environments) or
turn Deploy Agent into a CI/CD platform; it defines the contract every
project already has or should adopt, and the shared logic
(`scripts/ci/`) that reads that contract generically.

Every coding agent must read this file, `AGENTS.md`, and the affected
project's `PROJECT.yaml` before making a non-trivial change.

## 0. Terms and repository model

- **Workspace** — this repository, `/home/dell/workspace/mesflow`.
- **Project** — a directory with its own version/build/test/artifact/
  deploy lifecycle, registered in `WORKSPACE.yaml` and described by its
  own `PROJECT.yaml`. Today: `mesflow/`, `deploy-agent/`, `qa-center/`,
  `esp-kiosk/`. See the "PROJECT DISCOVERY" section of the most recent
  audit report for the full current classification (MANAGED / UNMANAGED /
  registry gaps).
- **Contract** — a project's `PROJECT.yaml`: machine-readable
  preflight/test/build/smoke/deploy commands, artifact strategy, and
  deployment policy.

**Repository model (verified, not assumed): multi-repo workspace, not a
monorepo.** `mesflow/`, `qa-center/`, `deploy-agent/`, `esp-kiosk/`,
`mesflow-web/` each have their own `.git` and their own remote already
(`git ls-files mesflow` from the outer repo returns nothing — a `.git`
boundary, not a tracked subtree). The outer workspace repo is the
standards/registry surface (`AGENTS.md`, `WORKSPACE.yaml`, `docs/`,
`scripts/ci/`, `.github/workflows/`), not a container of the other
repos' source, and currently has no GitHub remote of its own. This has
one concrete, load-bearing consequence: **a fresh GitHub checkout of the
outer repo never contains a project's actual source**, so CI cannot run
as "one matrix job per project, checked out from the outer repo." See
§8 for the resulting architecture.

`scripts/ci/*` therefore supports two modes:

- **discover mode** (default) — used on this dev machine, where every
  project really is a sibling directory: `discover()` reads
  `WORKSPACE.yaml` + does the sibling scan, exactly as documented below.
- **local/single-project mode** (`--local --root <path>`) — used from
  inside a project's own CI (a normal single-repo checkout with no
  siblings present at all): `workspace.load_local_project()` reads
  `<path>/PROJECT.yaml` directly, no registry, no sibling scan. Every
  `PROJECT.yaml`'s own `source.root: .` already means "relative to this
  project's own root," so local mode's `record.root = "."` makes
  `working_directory` resolution, `artifacts.directory`, etc. behave
  identically in both modes.

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

### Dirty-tree policy

An **official** release manifest (`scripts/ci/release_manifest.py`,
called from `_project-release.yml`) refuses by default to build from a
project tree with uncommitted changes (`DIRTY_TREE_BLOCKED`) — a release
must be traceable to one exact, clean, committed commit. A local/dev
build may pass `--allow-dirty`; the resulting manifest is then marked
`"dirty": true, "release_type": "NON_RELEASE"` so it can never be
mistaken for an official release artifact downstream (e.g. by
`same_artifact_check.py`, which compares digests, not this flag, but a
human/CI reading the manifest sees it immediately).

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

## 8. CI matrix and cross-repo workflow architecture

Given the multi-repo model (§0), the CI matrix is split across two
layers instead of one:

```
outer/standards repo (.github/workflows/)
  ci.yml               -- gates the standard itself (scripts/ci/tests,
                           workflow YAML syntax); cannot and does not try
                           to run nested project source it doesn't have
  _project-ci.yml      -- reusable (on: workflow_call); called cross-repo
  _project-release.yml -- reusable (on: workflow_call); called cross-repo

each child repo (mesflow/, qa-center/, ...)
  .github/workflows/ci.yml (thin)
    uses: <owner>/<standards-repo>/.github/workflows/_project-ci.yml@<ref>
    with: {project: <code>, standards_repository: <owner>/<standards-repo>}
```

`_project-ci.yml`'s first step is a plain `actions/checkout@v4` with no
`repository:`/`ref:` override — GitHub resolves that against the
*calling* repo's own ref (the run's `github.repository` context is the
caller's, not the reusable workflow file's own repo), so this checks out
the project's real source. A second `actions/checkout@v4` explicitly
pulls in just `scripts/ci/` from the standards repo into `.ci-standard/`
(sparse checkout), so the contract-reading logic is never copy-pasted
into every child repo. The job then runs, in local/single-project mode:

```bash
python3 .ci-standard/scripts/ci/run_project.py <project> --local --root .
```

CI never hard-codes a project's own implementation into the workflow YAML
— it only invokes `run_project.py <project> [--local --root .]`; the
actual command lives in that project's own `PROJECT.yaml`.

On this dev machine (where every project really is a sibling directory),
the same tooling also works in the original discover-mode form, useful
for local verification:

```bash
scripts/ci/run-project mesflow-app --stage preflight
scripts/ci/run-project mesflow-app --stage test
```

**Status of activation**: each child repo's thin `ci.yml` exists today as
`ci-standard.yml`, deliberately left `workflow_dispatch`-only with a
placeholder `standards_repository` (the standards repo has no GitHub
remote yet — see `docs/GITHUB_CI_CD_SETUP.md` §0/§7 for the exact
activation steps). It is not wired into `pull_request`/`push` until that
reference is real, so it can never silently break a repo's real CI in the
meantime.

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

**`git_sha` is always the project's own repository HEAD, never the outer
workspace repo's SHA** — load-bearing given §0's multi-repo model:
`scripts/ci/release_manifest.py`'s `_git_sha()` resolves `git rev-parse
HEAD` with `cwd` set to the project's own root first (which, for an
independent nested repo like `mesflow/`, IS that repo, so this is correct
by construction), falling back to the workspace root only if the project
root is not itself a git repository. Regression-tested directly:
`scripts/ci/tests/test_local_project_mode.py::test_artifact_git_sha_is_the_projects_own_repo_head_not_an_outer_workspace_sha`
builds two repos with deliberately different histories and asserts the
manifest's `git_sha` matches the project's, not the outer one's.

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
silently passed. `scripts/ci/changed_projects.py` surfaces this as an
explicit `warnings` entry (`"<path>: belongs to project '<code>'
(status=<status>) -- no managed CI gate runs for it"`) whenever a changed
path falls under an unmanaged/unregistered/invalid project's root and
isn't already covered by a managed project or shared-path expansion — a
silent, empty affected-projects list would otherwise look identical to
"nothing relevant changed." Policy:

- A PR that does **not** touch an unmanaged project's files: CI does not
  block on it. It is listed in the CI summary as "unmanaged, not run."
- A PR that **does** touch an unmanaged project's files: CI **warns**
  (does not hard-block) — because in V1, most of these directories
  (`bootstrap/`, `mesflow-web/`, `esp32-cyd-clock/`) are real, actively
  developed projects that simply have not been given a `PROJECT.yaml` yet,
  and hard-blocking every change to them before migration would defeat
  the point of an incremental rollout. This is a deliberate, documented
  choice, not an oversight — revisit it once a given project is migrated.
