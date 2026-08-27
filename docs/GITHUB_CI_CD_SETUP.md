# GitHub CI/CD Admin Setup — MESFlow Workspace

Companion to `docs/CI_CD_STANDARD.md`. This is an admin checklist, not
something an agent can complete on its own — it requires GitHub
organization/repo admin access.

## 0. Current state (verified, not assumed)

At the time this was written, `/home/dell/workspace/mesflow` (this
workspace repo) has **no `git remote` configured at all** —
`git remote -v` returns nothing. Every item below therefore starts from
"connect a GitHub remote"; none of it is active yet. Do not assume
branch protection/Actions/Environments already exist just because
`.github/workflows/*.yml` files exist locally — a workflow file only runs
once it reaches a repo GitHub actually hosts.

The nested project repos (`mesflow/`, `deploy-agent/`, `qa-center/`,
`esp-kiosk/`, `mesflow-web/`) are separate git repositories with their
own remotes; `mesflow/`'s remote is `git@github.com:hungtranbkit/mesflow.git`
and already runs its own `.github/workflows/postgres-docker-tests.yml`.
This workspace-level setup is about the **outer workspace repo**, which is
a distinct repository from `mesflow/`.

## 1. Repository / branch protection

- [ ] Push this repo to a GitHub remote (org or personal, per the
      workspace owner's choice — not decided by this pass).
- [ ] `main` branch protection:
  - [ ] Require a pull request before merging.
  - [ ] Require status checks to pass before merging — select the CI
        matrix job(s) from `.github/workflows/ci.yml` once the first run
        exists (GitHub only lists checks that have run at least once).
  - [ ] Require branches to be up to date before merging.
  - [ ] Disallow force pushes to `main`.
  - [ ] Disallow branch deletion for `main`.
  - [ ] Optional: require review approval count per team policy.

## 2. GitHub Actions permissions

- [ ] Settings -> Actions -> General:
  - [ ] Allow actions and reusable workflows (needed for
        `_project-ci.yml`/`_project-build.yml` reusable workflows if
        added).
  - [ ] Workflow permissions: default to read-only `GITHUB_TOKEN`; grant
        write only to the specific job that needs it (e.g. uploading
        artifacts), not repo-wide.

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

**Plan limitation to verify, not assume**: required reviewers on
environments needs a GitHub plan that supports Environments with
protection rules (available on GitHub Team/Enterprise for private repos;
public repos get it on the free plan). If this repo stays private on a
plan that does not support environment approval, document that limitation
here explicitly rather than silently trusting an unenforced human
approval convention — check the actual plan before relying on this gate.

## 4. Secrets

- [ ] Repo-level secrets: none that a production deploy needs (keep those
      environment-scoped, §3).
- [ ] Per-environment secrets for whatever `deployment.test`/
      `deployment.production` in each project's `PROJECT.yaml` actually
      requires (target host, credentials) — inventory this per project
      before wiring real deploy jobs; V1 does not wire production deploy
      at all (see `docs/CI_CD_STANDARD.md` §10).

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

If `actionlint` is not installed, at minimum validate YAML syntax
(`python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" file.yml`
for each file) — do not skip validation entirely just because the linter
is unavailable.

## 7. Rollout order

1. Connect the GitHub remote.
2. Push `.github/workflows/ci.yml` on a branch, open a PR, confirm the
   check appears and can be required.
3. Turn on branch protection requiring that check.
4. Add the `test` and `production` environments; add required reviewers
   on `production` only.
5. Only then start wiring any real deploy step into `release.yml` —
   until then, `release.yml` should build/manifest/qualify only, per
   `docs/CI_CD_STANDARD.md` §10.
