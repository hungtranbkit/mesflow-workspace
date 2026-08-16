# Source of Truth

## The rule

```
/home/dell/workspace/mesflow   = SINGLE SOURCE OF TRUTH FOR DEVELOPMENT
/opt                            = DEPLOYED/RUNTIME CONFIG ONLY
/var/lib                        = PERSISTENT RUNTIME DATA
```

Workspace source is edited, committed, built, and released. `/opt` receives
built artifacts and holds only what a running deployment needs (compose
files, `.env`, release metadata, and for MESFlow a runtime/ data mount).
`/var/lib` holds data that must survive redeploys and reinstalls.

Do not maintain two editable source copies. If code needs to change, change
it in the workspace, build a new versioned release, and deploy that release
— never edit `/opt` directly and never treat `/opt` as a second working copy.

## Per-project mapping

| Project | Workspace source | Deployed to | Config/compose | Persistent data |
|---|---|---|---|---|
| MESFlow core | `mesflow/` | `/opt/mesflow` (image + runtime bind mounts only, no app source) | `/opt/mesflow/compose.yml`, `/opt/mesflow/.env` | `/opt/mesflow/runtime/postgres-v65` (PostgreSQL, bind mount — do not move), `/opt/mesflow/runtime/{uploads,backups,tutorials,firmware}` |
| Deploy Agent | `deploy-agent/` | `/opt/mesflow-deploy-agent` (compose + Dockerfile; image built from this source) | `/opt/mesflow-deploy-agent/docker/compose*.yml` | `/var/lib/mesflow-deploy-agent` (config/state/releases/staging/uploads/backups/logs/ota) |
| QA Center | `qa-center/` | `/opt/mesflow-qa-center` (`current/`, `previous/`, `runtime/`) | `/opt/mesflow-qa-center/current/docker/compose.yml` | `/opt/mesflow-qa-center/runtime` |
| ESP Kiosk | `esp-kiosk/` | firmware flashed to devices; tutorial/firmware artifacts published via Deploy Agent | n/a (device firmware, not a server deployment) | device flash only |

## Reconciliation rule

`/opt` can drift ahead of workspace when someone edits a running deployment
directly under time pressure (this has happened — see
`reports/WORKSPACE_AND_DEPLOYMENT_RESTRUCTURE.md` for a concrete example
where Deploy Agent's compose files and templates were fixed in `/opt` and
never brought back). When that happens:

1. Run `scripts/reconcile-from-opt.sh <project>` (or `scripts/audit-environments.sh`
   for a quick count) — **read-only**, produces a sanitized diff, never
   overwrites the workspace.
2. Classify every difference: `RUNTIME_ONLY`, `CONFIG_ONLY`, `GENERATED`,
   `LOG`, `CACHE`, `ARTIFACT`, `LEGACY_SOURCE`, `REAL_CODE_CHANGE`, `UNKNOWN`.
3. Only `REAL_CODE_CHANGE` entries are candidates to port into workspace,
   and only after reading the actual diff — never a wholesale copy of `/opt`
   over the workspace.
4. Never overwrite newer workspace code with older deployed code.
5. If a `REAL_CODE_CHANGE` in `/opt` looks unfinished or you cannot confirm
   it is safe, STOP and report it — do not guess.

## What must never live in `/opt`

- Full application source for image-release-mode deployments (MESFlow,
  Deploy Agent's runtime image, QA Center images — the image already
  contains it).
- `.git` history — `/opt` is not where commits happen.
- Anything that should instead be workspace source or `/var/lib` data.

## What must never live in the workspace source repos

`runtime/`, `docker/runtime/`, database dumps, Docker image `.tar` files,
release ZIP archives, `node_modules/`, `.venv/`, `__pycache__/`,
`.pytest_cache/`, Playwright output (`test-results/`, `playwright-report/`),
large logs — unless a specific fixture is intentionally committed. Each
project's `.gitignore` enforces this; see the per-project `.gitignore` for
the exact patterns.

## Git status (as of this restructure)

`mesflow/` and `esp-kiosk/` were already git repositories. `deploy-agent/`
and `qa-center/` had **no version control at all** despite being the
canonical source for their deployed images — this restructure initialized
git for both (`git init`, baseline commit, `.gitignore`). Going forward all
four are real repositories; commit real changes there instead of leaving
them as an undated pile of files.
