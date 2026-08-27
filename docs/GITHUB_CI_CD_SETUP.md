# GitHub CI/CD Admin Setup — MESFlow Workspace

Companion to `docs/CI_CD_STANDARD.md`. This is an admin checklist, not
something an agent can complete on its own — it requires GitHub
organization/repo admin access, and (per this workspace's own rules)
never includes an agent inventing/creating a new GitHub repository on
its own initiative.

## 0. Repository model (verified, not assumed)

This workspace is a **multi-repo workspace**, not a monorepo:

```bash
find . -mindepth 2 -maxdepth 3 -type d -name .git
# ./deploy-agent/.git  ./qa-center/.git  ./mesflow-web/.git
# ./esp-kiosk/.git     ./mesflow/.git
git ls-files mesflow   # -> nothing: the outer repo tracks NONE of it
git ls-files qa-center # -> nothing
```

`mesflow/`, `qa-center/`, `deploy-agent/`, `esp-kiosk/`, `mesflow-web/`
are independent git repositories with their own remotes already:

| Project | Remote |
|---|---|
| `mesflow/` | `git@github.com:hungtranbkit/mesflow.git` |
| `qa-center/` | `https://github.com/hungtranbkit/mesflow-qa-center.git` |
| `deploy-agent/` | `https://github.com/hungtranbkit/mesflow-agent.git` |
| `esp-kiosk/` | `git@github.com:hungtranbkit/mesflow-esp32-kiosk.git` |

The **outer workspace repo** (`/home/dell/workspace/mesflow` itself —
`AGENTS.md`, `WORKSPACE.yaml`, `docs/`, `scripts/ci/`,
`.github/workflows/`) has **no `git remote` configured at all**. It is
the standards/registry surface, not a container of the other repos'
source. Consequence: a fresh GitHub checkout of the outer repo never has
`mesflow/`'s or `qa-center/`'s actual source present, so CI for those
projects cannot run as a matrix inside the outer repo's own workflow —
each project's own repo runs its own thin `ci.yml` that calls this
repo's reusable `_project-ci.yml` (`uses:
<owner>/<standards-repo>/.github/workflows/_project-ci.yml@<ref>`, which
GitHub resolves against the CALLING repo's checkout, not the standards
repo's). See `docs/CI_CD_STANDARD.md` for the full rationale.

Do not assume branch protection/Actions/Environments already exist just
because `.github/workflows/*.yml` files exist locally — a workflow file
only runs once it reaches a repo GitHub actually hosts.

**GITHUB_REMOTE_STATUS (outer/standards repo): READY_TO_CONFIGURE.**
No canonical name/URL for this repo exists in any local config or
documentation, so one is not invented here. `gh` is installed and already
authenticated as `hungtranbkit` (the same account that owns
`mesflow`/`mesflow-qa-center`/`mesflow-agent`/`mesflow-esp32-kiosk`) —
useful context for whoever runs the commands below, not something this
pass uses to create a repo on its own.

Once a name is chosen (e.g. following the existing `hungtranbkit/mesflow-*`
convention), the admin runs:

```bash
cd /home/dell/workspace/mesflow
git remote add origin git@github.com:<ORG>/<REPO>.git
git push -u origin feature/workspace-cicd-v1
```

Do not change the remote of `mesflow/`, `qa-center/`, `deploy-agent/`, or
`esp-kiosk/` — they already have real, working remotes.

## 1. Repository / branch protection

Per repository (the outer/standards repo, and each of
`mesflow`/`qa-center`/`deploy-agent`/`esp-kiosk` once each is ready to
enforce this):

- [ ] `main` branch protection:
  - [ ] Require a pull request before merging.
  - [ ] Require status checks to pass before merging.
  - [ ] Require branches to be up to date before merging.
  - [ ] Disallow force pushes to `main`.
  - [ ] Disallow branch deletion for `main`.
  - [ ] Optional: require conversation resolution before merging.
  - [ ] Optional: require review approval count per team policy.

**Exact required check names** (GitHub only lists a check in the branch
protection picker after it has run at least once):

| Repo | Required check name |
|---|---|
| outer/standards repo | `CI (workspace standards repo) / summary` |
| `mesflow/` | `PostgreSQL Docker Tests / test` (existing, already active) |
| `qa-center/` | not yet activated — see `docs/CI_CD_STANDARD.md`; once `ci-standard.yml` is switched from `workflow_dispatch` to `pull_request`/`push`, it will be `CI (workspace standard, manual) / ci / <project>` |

The outer repo's `ci.yml` was deliberately given one stable aggregate job
(`summary`) precisely so branch protection has one check name to require
regardless of how many other informational jobs exist or change.

## 2. GitHub Actions permissions

- [ ] Settings -> Actions -> General, per repo:
  - [ ] Allow actions and reusable workflows (required for
        `_project-ci.yml`/`_project-release.yml` to be callable
        cross-repo from `mesflow/`/`qa-center/`/etc.).
  - [ ] If reusable workflows are restricted to specific repos, allow
        each child repo (`mesflow`, `qa-center`, ...) to call workflows
        from the standards repo explicitly.
  - [ ] Workflow permissions: default to read-only `GITHUB_TOKEN` repo-wide;
        every workflow in this pass already declares `permissions:
        contents: read` explicitly rather than relying on the repo
        default.

## 3. Environments

- [ ] Create a `test` environment:
  - [ ] No required reviewers (TEST qualification should be fast/automatic
        per `docs/CI_CD_STANDARD.md` §3).
  - [ ] Environment secrets: whatever the TEST deploy step needs (kept out
        of repo secrets so a PR from a fork cannot read them — see §5).
- [ ] Create a `production` environment:
  - [ ] **Required reviewers**: at least one human approver, matching
        `AGENTS.md` "Production mutation requires explicit human
        approval." This is the mechanical enforcement of that rule.
  - [ ] Optionally restrict which branches can deploy to it (`main` only).
  - [ ] Environment secrets scoped to production only.
  - [ ] Not usable yet in practice: `PRODUCTION_CD` is
        `BLOCKED_BY_DEPLOY_RUNTIME` (`docs/CI_CD_STANDARD.md` §10) — set
        this up ahead of time, but nothing calls it yet.

**Plan limitation to verify, not assume**: required reviewers on
environments needs a GitHub plan that supports Environments with
protection rules (available on GitHub Team/Enterprise for private repos;
public repos get it on the free plan). If a repo stays private on a plan
that does not support environment approval, document that limitation here
explicitly rather than silently trusting an unenforced human approval
convention — check the actual plan before relying on this gate.

## 4. Secrets

- [ ] Repo-level secrets: none that a production deploy needs (keep those
      environment-scoped, §3).
- [ ] Per-environment secrets for whatever `deployment.test`/
      `deployment.production` in each project's `PROJECT.yaml` actually
      requires (target host, credentials) — inventory this per project
      before wiring real deploy jobs; this phase does not wire production
      deploy at all (see `docs/CI_CD_STANDARD.md` §10).
- [ ] `pull_request` (not `pull_request_target`) is used for every CI
      trigger in this pass, so a fork PR's workflow run never has access
      to repo/environment secrets — verify this stays true before adding
      anything that needs a secret on a `pull_request`-triggered job.

## 5. Artifact retention

- [ ] Actions -> General -> Artifact and log retention: set a retention
      period appropriate for release manifests/JUnit XML (e.g. 30-90
      days). Release artifacts that must live longer than the retention
      window belong in `artifacts/releases/` (already the case per
      `AGENTS.md` RULE 8), not solely in Actions artifact storage.

## 6. Lint the workflows themselves

If `actionlint` is available, run it against every file under
`.github/workflows/` before relying on them:

```bash
actionlint .github/workflows/*.yml
```

`actionlint` was not available in the environment this standard was
built in — validated with plain PyYAML syntax parsing instead:

```bash
python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" file.yml
```

Do not skip validation entirely just because the linter is unavailable.

## 7. Rollout order

1. Choose and create the standards repo's GitHub remote (§0) — human
   decision, not automated here.
2. Push it; confirm `CI (workspace standards repo) / summary` appears on
   a PR.
3. Require that check in the standards repo's own branch protection.
4. In each child repo (`mesflow`, `qa-center`, ...), fill in the real
   `standards_repository` in `ci-standard.yml` and switch its `on:` from
   `workflow_dispatch` to `pull_request`/`push` (see that file's own
   inline TODO).
5. Require the resulting check in that child repo's branch protection.
6. Add the `test` and `production` environments in each repo that will
   eventually build/qualify a release; add required reviewers on
   `production` only.
7. Only then consider wiring any real deploy step behind
   `_project-release.yml` — until a generic deployment runtime exists,
   it should build/manifest/qualify only, per `docs/CI_CD_STANDARD.md` §10.
