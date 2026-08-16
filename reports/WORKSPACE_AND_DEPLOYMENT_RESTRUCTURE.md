# Workspace and Deployment Restructure

Date: 2026-08-13
Scope: audit → drift detection → safe reconciliation → standardization →
documentation → helper scripts → static verification. Per user decision,
this pass did **not** live-drive the Release Manager UI (Playwright) and
did **not** touch Production or Production Test.

## Method

1. Read `AGENTS.md`, all project READMEs/AGENTS.md, and existing
   `docs/operations/*` before changing anything.
2. Audited `/home/dell/workspace/mesflow`, `/opt/mesflow`,
   `/opt/mesflow-deploy-agent`, `/opt/mesflow-qa-center`,
   `/var/lib/mesflow-deploy-agent`, `docker ps -a`, `docker compose ls`,
   `docker images`, mounts, and git status — read-only.
2b. Asked the user three clarifying questions on genuinely ambiguous
   decisions (git-init for git-less repos, committing mesflow's 14-version
   backlog, and how far to live-test) before mutating anything. All three
   were answered with the recommended option.
3. Diffed `/opt` against workspace for `mesflow`, `deploy-agent`,
   `qa-center`; classified every difference; reconciled the safe ones.
4. Standardized structure, wrote docs/scripts, ran static verification.

## Project audit (state found)

| Project | Workspace version | Deployed version | Workspace commit (before) | Deployed image | Source location | Runtime location | Config location | Data location |
|---|---|---|---|---|---|---|---|---|
| MESFlow | 65.8.44.65 (uncommitted, 14 versions ahead of HEAD) | 65.8.44.65 | `77890f3` (msg said "65.8.44.51" — stale) | `mesflow-app:65.8.44.65@sha256:0c439f758...` (running) vs tag now `2eab8b55...` — **see finding #1** | `mesflow/` | `/opt/mesflow/runtime/*` | `/opt/mesflow/compose.yml`, `.env` | `/opt/mesflow/runtime/postgres-v65` (bind mount) |
| Deploy Agent | 2.16.10-docker-runtime | 2.16.11-docker-runtime | none (no git repo existed) | `mesflow-deploy-agent:2.16.11` | `deploy-agent/` | container `/data` | `/opt/mesflow-deploy-agent/docker/compose*.yml` | `/var/lib/mesflow-deploy-agent` (already live) |
| QA Center | unknown (no VERSION.txt in workspace `current/`) | `current` runtime 1.19.6 (per Agent status) | none (no git repo existed) | `mesflow-qa-runtime:1.0.0` | `qa-center/` | `/opt/mesflow-qa-center/{current,previous,runtime}` | same | `/opt/mesflow-qa-center/runtime` |
| ESP Kiosk | firmware ESP32-KIOSK-5.1.9-WORKER-QTY-FLOW | n/a (flashed devices) | `a1827e3` clean, but 77 stale tracked test-results + untracked new tooling | n/a | `esp-kiosk/` | n/a | n/a | n/a |

## Findings

### Finding 1 — `mesflow-app:65.8.44.65` tag was moved by a second build (HIGH)

`docker images` shows the tag now points at image `2eab8b557723` (built
05:58, matches `artifacts/releases/65.8.44.65/release.json` digest
`sha256:2eab8b55...`), but the **currently running** `mesflow-app`
container is pinned by digest to an **older** build, `0c439f75840b` (built
03:28 — matches `/opt/mesflow/release.json`, the deployed record). Same
version number, two different image bytes. This breaks the "one version =
one immutable artifact" invariant the whole Build-Once/Promote-Same-Artifact
flow depends on. **Not fixed automatically** — resolving it means deciding
which build is authoritative and likely restarting the live `mesflow-app`
container, which is outside this task's read-mostly, no-production-mutation
scope. Documented in `docs/operations/BUILD_AND_PROMOTE.md`. Compare by
digest, not tag, until resolved.

### Finding 2 — Deploy Agent had real, unfinished changes only in `/opt` (RECONCILED)

`/opt/mesflow-deploy-agent` had been edited directly (violating RULE 2)
ahead of a version bump to 2.16.11:
- `compose.linux.yml`: Agent data volume switched from in-tree
  `./runtime/agent-data` to the persistent `/var/lib/mesflow-deploy-agent`
  path — **real improvement, verified running healthy, ported to workspace**.
- `compose.dev.override.yml`: workspace bind mount switched from a relative
  `../../` path to `${MESFLOW_WORKSPACE_ROOT:-/home/dell/workspace/mesflow}`
  — **real improvement, ported to workspace**.
- `templates/index.html`: Release Manager Build/Deploy-Local buttons now
  handle non-OK/non-JSON responses instead of assuming success — directly
  addresses the "don't assume buttons work because they render" requirement
  — **ported to workspace**.
- `package_installer.sh`: referenced a new `installer/migrate-runtime.sh`
  that **was never actually created** in `/opt` either — a dangling,
  half-finished edit. **Deliberately not ported.** Workspace's
  `installer/install.sh` was instead given equivalent (and more complete —
  health-checked, auto-rollback) logic directly, see Finding 3.

`agent.py` itself was already byte-identical apart from the version string
— reconciled by bumping workspace to `2.16.11-docker-runtime`.

### Finding 3 — Confirmed and fixed the exact Phase 11 installer bug (FIXED)

`agent.py` defaulted `MESFLOW_SOURCE_DIR`/`ESP_KIOSK_SOURCE_DIR` to
`Path.home()/"workspace/mesflow/..."`. The Agent process runs as root
(systemd `User=root`, or root inside its container), where `Path.home()`
is `/root` — exactly the `/root/workspace/mesflow` bug the task described,
confirmed present in the actual code, not hypothetical. Fixed:
- `agent.py`: new `_default_workspace_root()` — honors
  `MESFLOW_WORKSPACE_ROOT`, then `SUDO_USER`, then the tty login owner,
  before falling back to the old `Path.home()` behavior as a last resort.
- `installer/install.sh` (the `sudo bash install.sh` entry point): same
  resolution order, plus proper existing-container handling — detects an
  existing `mesflow-deploy-agent` container, renames+stops it (data is
  external, nothing lost), builds/starts the new one, polls `/agent/health`,
  and automatically rolls back to the preserved container if health never
  comes up.
- `install_agent.sh` / `install/linux/install_agent.sh` (legacy systemd
  path): same resolution, written to `/etc/mesflow-deploy-agent.env`.

### Finding 4 — deploy-agent/ and qa-center/ had no version control (FIXED, by user decision)

Confirmed via `git status` — `fatal: not a git repository`. Both are now
git repos (`git init`, baseline commit, `.gitignore` excluding
`docker/runtime/`, `runtime/`, `__pycache__/`, artifacts, etc.). `qa-center/previous/`
(a manual pre-git rollback copy) was kept as-is; it's a cleanup candidate
once git history is trusted to serve the same purpose.

### Finding 5 — mesflow workspace was 14 versions ahead of its last commit (FIXED, by user decision)

Working tree was on `sync/reconcile-mesflow-65.8.44.51` with 18 modified +
12 untracked files, already at content matching deployed 65.8.44.65, never
committed. This meant `release.json.source_commit` for the live deployment
pointed at a commit whose tree didn't actually match what was built (the
release process built from the dirty working tree). Reviewed the diff for
secrets (none found — only `${VAR:-}` env references and one placeholder
default token) and committed on the existing branch (not merged to `main`
— that decision was left for the user).

### Finding 6 — esp-kiosk had 77 stale tracked files (FIXED)

`test-results/` (Playwright output) was committed in the repo's first
commit; all 77 files have since been deleted on disk. Untracked, gitignored,
committed alongside legitimate pending OTA/tutorial tooling changes.

### Finding 7 — loose release artifacts at workspace/artifacts root (FIXED)

`deploy-agent.zip`, `esp-kiosk.zip`, `mesflow.zip` at the workspace root,
and two `MESFlow_*_OTA_Phase3.zip` at `artifacts/` root, moved into their
project subfolders under `artifacts/`.

### Finding 8 — pre-existing test failures, not caused by this session (REPORTED, not fixed)

8 of 56 deploy-agent tests fail, confirmed present **before** any change in
this session (checked out `agent.py`/`templates/index.html` at the pre-restructure
commit and re-ran — same 8 failures minus the version-bump ones):
- 3 in `test_deploy_safety.py` — `_docker_mes_state()`/`_start_stack()` end
  up calling real `docker`/checking real Postgres health instead of being
  fully isolated by the test's `subprocess.run` patch; fails in this
  environment because Postgres for the test's fake target isn't running.
  Pre-existing test fragility, not a code regression.
- 3 hardcode an exact historical `VERSION.txt` string
  (`2.16.9`/`2.15.5`/`2.12.4`) instead of reading it dynamically — stale
  "freeze the current state" tests that break every release.
- 1 (`test_runtime_guard_is_present`) same pattern, hardcodes `2.16.9`.
- 1 (`test_file_picker_auto_submits_without_upload_button`) asserts the old
  auto-submit-only upload pattern that `AGENTS.md` itself says to avoid
  ("Upload UI must have a visible fallback action; never rely on only one
  fragile JavaScript auto-submit path") — the current template already has
  the required visible button; the test is checking for the wrong thing.
Not fixed — this is business-logic/test maintenance, out of this task's
scope ("do not redesign business logic"), but should not be ignored.

### Finding 9 — `/opt` has ~13 accumulated Deploy Agent backup directories

`mesflow-deploy-agent.backup-*` / `mesflow-deploy-agent-backup-*` from
2026-08-11/12 manual reinstalls. Not touched (Phase 15: don't delete
legacy without certainty) — flagged as a cleanup candidate for a human to
confirm and remove.

### Finding 10 — workspace root itself is not a git repository

`docs/`, `reports/`, `scripts/`, `AGENTS.md`, `artifacts/` at the workspace
root are not version-controlled at all (only the four project
subdirectories are). Not changed in this pass — mixing multi-hundred-MB
artifacts into a root repo is a real design decision, left for the user.

## What was NOT done (by explicit user decision or task boundary)

- No live Playwright run against the Release Manager UI this pass (user
  chose "static checks only"). Build/Deploy-Local/Promote-Test buttons
  were read at the code level (see Finding 2's template fix) but not
  click-tested live in this session — see `reports/RELEASE_MANAGER.md`
  and `reports/LOCAL_PRODUCTION_TEST_SETUP.md` for the most recent live
  evidence (from an earlier session, still the best available: LOCAL_PASS
  and TEST_PASS achieved for 65.8.44.65 — but see Finding 1, the tag has
  since moved).
- Promote Production Test control is still `disabled` in the UI — no
  dedicated server-side endpoint exists yet; `scripts/promote-test.sh`
  performs the equivalent flow manually via the existing `/upload` +
  `/deploy/<version>` endpoints, matching what was already proven to work
  by hand.
- No retention/cleanup script was run against `/opt` backups or
  `artifacts/staging`.
- No merge of the `mesflow` sync branch into `main`.
- Production and Production Test were not mutated in any way.

## Files moved

- `artifacts/deploy-agent.zip` → `artifacts/deploy-agent/deploy-agent_2.16.10_workspace_20260813.zip`
- `esp-kiosk.zip` → `artifacts/esp-kiosk/esp-kiosk_workspace_20260812.zip`
- `mesflow.zip` → `artifacts/mesflow/mesflow_workspace_20260813.zip`
- `artifacts/MESFlow_65.8.44.60_OTA_Phase3.zip`, `artifacts/MESFlow_65.8.44.61_OTA_Phase3.zip` → `artifacts/mesflow/`

## Files created

- `docs/operations/SOURCE_OF_TRUTH.md`
- `docs/operations/BUILD_AND_PROMOTE.md`
- `docs/operations/SERVER_LAYOUT.md`
- `docs/operations/NEW_SERVER_INSTALL.md`
- `scripts/status.sh` (rewritten), `scripts/audit-environments.sh`,
  `scripts/build-release.sh` (wrapper), `scripts/deploy-local.sh`,
  `scripts/promote-test.sh`
- `deploy-agent/.git`, `qa-center/.git` (new repositories)
- This report.

## Files modified

- `AGENTS.md` — added the RULE 1–8 permanent-rules block.
- `mesflow/`: `VERSION.txt`, `release.json`, `compose.yml`,
  `compose.test.yml`, `Dockerfile.playwright`, several `app/mesflow/*`
  files, tests, new OTA readiness module + migrations (committed, was
  already-pending work, not authored this session).
- `deploy-agent/`: `agent.py`, `VERSION.txt`,
  `docker/compose.linux.yml`, `docker/compose.dev.override.yml`,
  `templates/index.html`, `installer/install.sh`, `install_agent.sh`,
  `install/linux/install_agent.sh`.
- `esp-kiosk/`: `.gitignore` (untracked `test-results/`).

## Tests

```
git status (mesflow, deploy-agent, qa-center, esp-kiosk): clean, 4/4
git diff --check: clean
python3 -m py_compile agent.py ota_control.py reset_password.py: OK
python3 -m py_compile (all mesflow app/*.py): OK
bash -n on all scripts/ + deploy-agent shell scripts: OK
docker compose config (deploy-agent workspace + /opt, all overrides): VALID
docker compose config (/opt/mesflow, with MESFLOW_IMAGE supplied): VALID
docker compose config (/opt/mesflow-qa-center): VALID
docker compose config (mesflow/compose.test.yml): VALID
deploy-agent pytest (isolated venv, isolated HOME dirs): 48 passed, 8 failed
  — all 8 confirmed pre-existing (see Finding 8), none caused by this session
scripts/status.sh: ran successfully, local Agent reachable/healthy
scripts/audit-environments.sh: ran successfully after fixing a pipefail bug
  found during its own first run (diff exit-1-on-differences was aborting
  the script under `set -e`)
```

No Playwright/browser run was performed this pass (user decision). No
Production or Production Test mutation was performed.

## RESULT

```
SOURCE OF TRUTH:
WORKSPACE ROOT:        /home/dell/workspace/mesflow

MESFLOW SOURCE:        /home/dell/workspace/mesflow/mesflow
DEPLOY AGENT SOURCE:   /home/dell/workspace/mesflow/deploy-agent
QA CENTER SOURCE:      /home/dell/workspace/mesflow/qa-center
ESP SOURCE:            /home/dell/workspace/mesflow/esp-kiosk

ARTIFACT ROOT:         /home/dell/workspace/mesflow/artifacts

MESFLOW /OPT:          /opt/mesflow (config/runtime only — already compliant)
DEPLOY AGENT /OPT:     /opt/mesflow-deploy-agent (compose/config; some legacy
                       source still present pending Phase 12 full Dockerize)
QA CENTER /OPT:        /opt/mesflow-qa-center (compose/config only — already compliant)

DEPLOY AGENT DATA:     /var/lib/mesflow-deploy-agent (live, verified)
QA DATA:               /opt/mesflow-qa-center/runtime

CODE FOUND ONLY IN /OPT: deploy-agent compose volume paths + template JS
                       fix (Finding 2) — reconciled. dangling
                       migrate-runtime.sh reference — not reconciled
                       (never existed, unfinished).
CODE RECONCILED:       deploy-agent/docker/compose.linux.yml,
                       deploy-agent/docker/compose.dev.override.yml,
                       deploy-agent/templates/index.html,
                       deploy-agent VERSION.txt/agent.py version string

LEGACY SOURCE STILL PRESENT: ~13 /opt/mesflow-deploy-agent(-)backup-* dirs;
                       qa-center/previous/ (pre-git rollback copy)
SAFE TO CLEAN:         above, only after human confirmation — not removed
                       this pass

DEV ROLE:              DEV / MESFLOW_BUILD_ENABLED=true (confirmed via
                       running local Agent status endpoint)
DEV BUILD:             enabled, workspace bind-mounted

TEST ROLE:             PRODUCTION_TEST / MESFLOW_BUILD_ENABLED=false (per
                       reports/LOCAL_PRODUCTION_TEST_SETUP.md, not
                       re-verified live this pass)
TEST BUILD:            disabled (by design)

BUILD RELEASE BUTTON:  present, calls /api/release-manager/build — not
                       live-clicked this pass (see reports/RELEASE_MANAGER.md
                       for last live evidence)
DEPLOY LOCAL BUTTON:   present, calls /api/release-manager/deploy-local,
                       error handling fixed this pass (Finding 2) — not
                       live-clicked this pass
PROMOTE TEST BUTTON:   disabled in UI (no server endpoint yet);
                       scripts/promote-test.sh provides the equivalent
                       manual flow
PROMOTE PRODUCTION BUTTON: disabled, gated on production_gate — untouched

LATEST RELEASE:        65.8.44.65 (artifacts/releases/65.8.44.65)
ZIP SHA:                see artifacts/releases/65.8.44.65/checksums.txt
IMAGE DIGEST:           sha256:2eab8b5577239a799d2cfdd7366fb2d110dd9ab9a1425ad6636a752d14588b69
                       (tag) vs sha256:0c439f75840b149dcdc51d8164bcd20ee9695ed1636491543fb05a52b289a6e1
                       (actually running) — see Finding 1, these differ

LOCAL_PASS:             last recorded YES for 65.8.44.65 in
                       reports/LOCAL_PRODUCTION_TEST_SETUP.md (prior
                       session; not re-verified live this pass; Finding 1
                       means it should be re-verified against the current
                       tag before being trusted)
TEST_PASS:              last recorded YES in the same report; same caveat

FILES MOVED:            5 (see above)
FILES CREATED:          11+ (see above)
FILES MODIFIED:         ~20 across 4 projects + AGENTS.md (see above)

TESTS:                  git/py_compile/bash -n/compose-config all PASS;
                       deploy-agent pytest 48/56 pass, 8 pre-existing
                       failures unrelated to this session (Finding 8)

PRODUCTION ACTION REQUIRED: Human review of Finding 1 (image tag/digest
                       mismatch) before trusting any future "65.8.44.65"
                       promotion; human decision on merging the mesflow
                       sync branch to main; human confirmation before
                       deleting any legacy /opt backups.
PRODUCTION DEPLOYED:   NO
```
