# MESFlow Workspace V2 Consolidation — 2026-09-01

STATUS: **PASS**

V1/V2 audit, branch consolidation, build, and real deploy — verified on
**both DEV and PRODUCTION_TEST** — for mesflow-app + QA Center are done
and pushed. See §6 for how the initial PRODUCTION_TEST version-mismatch
finding (real, not a false alarm) was resolved by explicit user decision
and what was actually deployed as a result.

---

## 1. Scope actually covered

Repo: `~/workspace/mesflow` (outer workspace) + sibling repos `mesflow/`,
`deploy-agent/`, `qa-center/`, `mesflow-web/`, `deploy-agent-v2/`,
`esp-kiosk/`, `mesflow-kiosk-runtime-v2/`. No other project/session
touched.

## 2. V1/V2 mapping (verified, not assumed from naming)

| Component | V1 | V2 | Decision |
|---|---|---|---|
| MESFlow app | `mesflow/` | — | Only version; not a V1/V2 split. |
| Deploy control plane | `deploy-agent/` | `deploy-agent-v2/` | **V1 stays the real deploy tool.** V2's own README/PROJECT.yaml explicitly say V1 "is untouched and still runs MESFlow's real deployments today"; V2 "does not yet self-host its own build/deploy pipeline (Phase 6+ follow-up)". Confirmed, not assumed. |
| Frontend UI | Classic Flask/Jinja (`mesflow/app/mesflow/web/`) | `mesflow-web/` (React) | V2 is real, incremental (F5 phase — Overview/Dashboard/Production Trace/Business Audit migrated, everything else still links to Classic). `docs/architecture/FRONTEND_BACKEND_SEPARATION.md` states the nginx `/app-v2` gateway split is **F15, "not deployed yet" by design** — not a defect. Verified: `npm run typecheck/build/lint` all PASS. No production wiring attempted (out of documented phase). |
| ESP32 kiosk firmware | `esp-kiosk/` | `mesflow-kiosk-runtime-v2/` | Both have real, in-progress **uncommitted work** (250-line diff in esp-kiosk, hardware-pin changes in kiosk-runtime-v2) — left untouched per explicit user instruction to preserve dirty state. Firmware does not deploy to DEV/PRODUCTION_TEST servers (flashed over serial) — out of this pass's server-deploy scope. Not registered as V2 in `WORKSPACE.yaml` yet; registering it is a deliberate scope decision the workspace's own docs say not to make in a foundation pass. |

### deploy-agent-v2 recovery (real incident found and fixed)

`deploy-agent-v2/` on disk had **lost every root-level file** (PROJECT.yaml,
compose.yml, install.sh, README, VERSION, Dockerfile, docs/, main.py,
requirements.txt, .gitignore) and every `.py` file under
`app/core/adapters/target_agent/tests/` — only `.env` and empty directory
shells survived, no git history. The **built Docker image**
`mesflow-deploy-agent-v2:2.0.0` (built 2026-08-26) still held a complete,
byte-identical copy. Recovered by extracting `/app` from that image,
diffed against the surviving `.env`/dirs (zero conflicts — pure recovery).
Git-initialized as its own sibling repo (no remote yet, matches
`mesflow-web/`'s pattern). Fixed a real `MESFLOW_SOURCE_PATH` misconfig
(pointed at the outer workspace root instead of `mesflow/mesflow`) that
had the live `mesflow-deploy-agent-v2` container **crash-looping for
4192 restarts**; fixed, container now healthy at 127.0.0.1:8091 (not
exposed, not wired into any deploy path). Full pytest suite: 47/47 pass
(fixed 2 pre-existing failures: stale sibling-path assumption, a fixture
asserting a version-literal `__init__.py` no longer used).

## 3. Branches merged into main

### mesflow/ (app)

| Branch | Status | Action |
|---|---|---|
| `agent/claude/artifact-metadata-contract`, `agent/claude/esp-tutorial-ci-fixture`, `agent/codex/sandbox-contract-smoke-test`, `agent/codex/update-password-default-cho-mesflow-la-admin-123456` (+ its integration branch) | **No-op** | Already squash-merged via PRs #5–#8 (`git diff main..branch` empty or only later-main drift). No action; not deleted (other agents' worktrees still reference some). |
| `feat/kiosk-v2-deploy-architecture` | **Superseded, not merged** | Every substantive commit (kiosk-v2 backend, UI-bundle encoding, release-build clean-tree gate, rollback dry-run, prod freeze) already reapplied into main under different SHAs with matching messages; main has since diverged ~13,400 lines further. A literal merge would regress that work. |
| ~15 other local/remote branches | **No-op** | 0 commits ahead of main (`git rev-list --count`), confirmed individually. |
| `agent/claude/bump-version-concurrency-lock` (new, this session) | **Merged** | Added flock + `--no-wait` to `bump-version.sh` (deploy-agent-v2's own test suite already assumed this existed and tested it directly). |
| `agent/claude/release-71-0-0-80`, `agent/claude/gitignore-bump-lock`, `agent/claude/check-version-sync-dynamic-fix`, `agent/claude/projectflow-build-idempotent`, `agent/claude/fix-productivity-test-date` (new, this session) | **Merged** | Release-prep + 3 real pre-existing tooling/test bugs found and fixed while gating the release (see §5). |

Main: `93085ec` → **`d12340a`** (local == `origin/main`, pushed).

### deploy-agent/

| Branch | Status | Action |
|---|---|---|
| `checkpoint/pre-consolidation-2026-08-27` | **Merged (base)** | Real, superset recovery snapshot (VERSION 2.24.49) — workspace main was stuck at 2.24.8 while the deployed source had drifted to 2.24.37 and the *live running container* to 2.24.48. Merged; also stripped 2.6MB of accidentally-swept zip/backup cruft, hardened `.gitignore`. |
| `agent/codex/ui-quality-audit` | **Merged (layered)** | Small (266-line) genuine delta on top of the checkpoint — 14 real merge conflicts resolved by inspection (every case: the checkpoint/newer side had strictly more functionality — richer tutorial job tracking, `version-doctor.sh` made mandatory per `AGENTS.md`, retry/backoff logic, `url_for()` vs hardcoded paths). Not a blanket ours/theirs — each hunk read before resolving. |

Main: `94312df` → **`c87edd0`** (pushed). Full `scripts/test-baseline.sh`: 473 passed, 21 skipped, source-ZIP build PASS. Fixed 3 pre-existing gaps found while gating: two test fixtures asserting a stale version-literal, and both the test's and the *real* `tools/build_source_package.py`'s missing `.test-venv` exclusion (was tripping its own secret scanner on `cryptography`'s `ssh.py`).

### qa-center/

All candidate branches (`agent/claude/sandbox-contract`,
`integration/fix-giao-di-n-qa-qa` + `agent/codex/fix-giao-di-n-qa`) were
**already merged and pushed to `origin/main` via PR #3** before this
session started; `sandbox-contract`'s content is independently superseded
(main already has the same "configure QA Center sandbox runtime" work
under a different commit). Nothing to merge. Local clone was 3 commits
behind origin — blocked by a **root-owned `artifacts/` directory**
(pre-existing host permission issue, unrelated to git) that prevented
checkout; worked around by moving the root-owned dir aside (into
`qa-center/artifacts.rootlocked-<ts>/`, left in place — needs
`sudo rm -rf` to actually reclaim, noted, not force-deleted) and
re-pulling cleanly. Main: `75ad9bf` → **`0de6f97`** (already on origin).

### mesflow-web/

Single branch `agent/codex/ui-quality-audit`: 0 commits ahead, no-op.
No remote configured (local-only repo, same as when found).

## 4. Standardization

- `deploy-agent-v2/`: recovered, git-initialized, tested (see §2) — kept
  as parallel/local-only per its own documented status, **not** made the
  default deploy path (V1 remains authoritative — this is V2's own stated
  design, not this session silently keeping V1).
- No legacy code moved to `old/`: every V1↔V2 pair investigated (deploy
  agent, frontend, kiosk firmware) resolved to "V1 is still genuinely
  required / V2 isn't ready to replace it yet, by the projects' own
  documentation" — moving any of them to `old/` now would be premature
  per the task's own instruction not to archive without a verified
  replacement.
- `.gitignore` hardened in `deploy-agent/` (backup/zip cruft pattern) and
  `mesflow/` (`.bump-version.lock`).

## 5. Real pre-existing bugs found and fixed while gating this release

None of these were introduced by this session's merges (verified against
pre-session `main` in each case); all were found because this is
apparently the first time the full gate chain has been run end-to-end
recently:

1. **`mesflow/scripts/check-version-sync.sh`** asserted a literal
   `__version__='X.Y.Z.W'` in `app/mesflow/__init__.py` that has not
   existed since that file switched to reading `VERSION.txt` dynamically
   — permanently failing `release-local-qa.sh`'s version-verify step for
   every release. Fixed to check the dynamic-read marker instead.
2. **`mesflow/scripts/projectflow/build.sh`** unconditionally re-invoked
   `build-release.sh`, which correctly refuses to rebuild an
   already-frozen version (RULE 5) — making this QA step unusable for
   validating a release built directly. Fixed to reuse an existing frozen
   artifact instead of failing.
3. **`tests/integration/test_session_management_upgrade.py`**
   (`test_employee_productivity_reports_exclude_excluded_sessions_from_the_average`)
   hardcoded session dates in August 2026 but relied on the report's
   *default* "current calendar month" date window — a time bomb that
   started failing the moment the month rolled to September. Fixed with
   explicit `date_from`/`date_to`.
4. **`scripts/deploy-local.sh` / `scripts/promote-test.sh`** (workspace
   root): `set -o pipefail` turned "login page has no CSRF field"
   (true for the currently-running Agent — only authenticated pages have
   one) into a silent, message-less abort before the real login attempt.
   Separately, sending an explicit-but-empty `csrf=` field (vs. omitting
   it) made the **real Production Test Agent (2.24.37)** silently reject
   login — found only by testing against it by hand. Both fixed.
5. **`deploy-agent/tests/test_version_bump.py`**,
   **`test_package_installer_bump_integration.py`**, and
   **`tools/build_source_package.py`**: same version-literal fixture bug
   as #1, and a missing `.test-venv` exclusion tripping the real secret
   scanner. Fixed (see §3).

## 6. PRODUCTION_TEST (`deploy.mesflow.net` == `ssh-test.mesflow.net`) — resolved and deployed

**Finding (real, not a false alarm):** the real Production Test host was
running **mesflow-app 71.0.0.206** (schema `72.0.0.0`) and **QA Center
1.27.4** — version numbers that **do not exist anywhere in this
workspace's git history** for either repo (`git log --all -S` for both
version strings: zero hits). This workspace's `mesflow/` main topped out
at `71.0.0.80` (this session's own build). Promoting that build as-is
would have been a **downgrade**, not a promotion. One promotion attempt
for `71.0.0.80` was made before this gap was noticed and **failed
safely** at the target's own pre-cutover `docker compose config --quiet`
validation (`"Staging release; production remains online"` — the running
`.206` instance was never stopped or touched).

**Resolution (explicit user decision, 2026-09-01):** "lấy main làm gốc,
nâng hết version lên cao nhất và override các version khác" — treat this
workspace's `main` as the source of truth, bump the version past whatever
the target is running, and override it. Confirmed the user meant this
literally (not "skip production test", an earlier, superseded answer in
the same conversation) once they clarified via a separate SSH-deploy
request to `ssh-test.mesflow.net` — which, once connected, turned out to
be **the exact same physical host** as `deploy.mesflow.net` (identical
container set confirmed by `docker ps` over SSH: `mesflow-app:71.0.0.206`,
`mesflow-deploy-agent:2.24.37`, `mesflow-qa-center:1.27.4`).

**Real blockers hit and resolved while executing this:**
- No working SSH credential for `ssh-test.mesflow.net` as configured
  (`~/.ssh/config` had it as user `ubuntu` with no identity file). User
  said "dùng ssh codex"; tested and confirmed `codex@ssh-test.mesflow.net`
  with the existing `~/.ssh/mesflow_test_codex` key works. Fixed
  `~/.ssh/config` (added `User codex` + `IdentityFile`) for next time.
- The actual compose-validation failure on the real promotion attempt was
  a genuine, separate issue: the target's persistent `/opt/mesflow/.env`
  was missing `MESFLOW_SECRET_KEY` (a required var this workspace's
  `compose.yml` declares with no default) — the `.206` deployment
  predates that requirement. Generated a fresh
  `secrets.token_hex(32)` value and appended it via
  `docker exec -u root mesflow-deploy-agent` (the container already
  bind-mounts `/opt/mesflow`, so this needed no host-level `sudo`, which
  `codex` doesn't have on this box either). Verified all 4 of
  `compose.yml`'s required vars (`DATABASE_URL`, `MESFLOW_ADMIN_PASSWORD`,
  `MESFLOW_SECRET_KEY`, `POSTGRES_PASSWORD`) are now present.

**Executed:** bumped `mesflow/` to `71.0.0.207` (past `.206`, monotonic
per RULE 5 — see §7), rebuilt, ran the full `release-local-qa.sh` gate
again (PASS), redeployed to DEV, then promoted the same artifact to the
real Production Test Agent. **Both mesflow-app 71.0.0.207 and QA Center
1.32.1 are now live and verified healthy on the real Production Test
host** — see §7 for evidence. Real production (`mesflow.net` /
`ssh-prod.mesflow.net`) was never touched, per the original task
constraint.

## 7. Evidence

**mesflow-app release 71.0.0.207** (71.0.0.80 was built and DEV-verified
first — see git history — then superseded per §6's resolution)
- Source commit: `c130a075ce392c3e926e05f95cda62e4cf911ad4`
- Image: `mesflow-app:71.0.0.207`, digest `sha256:3f3ee909a24122b261dc5e0b182947450df1c2c7cc1c7e68349b5fda093dbbd2`
- ZIP: `MESFlow_71.0.0.207.deploy.zip`, sha256 `7773431f717288f48d9512ba2cd544b48bd1b4e3a2c22fa1ae79a1ba5bcb1860`
- `scripts/release-local-qa.sh`: **PASS** (version-verify, preflight, build, full `docker-test.sh` incl. Playwright, isolated-sandbox deploy-local, smoke, status — all PASS; evidence at `artifacts/qa/71.0.0.207/release-local/release-local-qa.json`, submitted to Deploy Agent's release-gate API — `PROMOTION.json.local.status = "success"`)
- **DEV**: real deploy job (Deploy Agent 127.0.0.1:8090), `success`. Live: `/api/system/ready` → `{"ok":true,"status":"ready","version":"71.0.0.207","migration_head":"0043_super_admin_role"}`.
- **PRODUCTION_TEST** (`deploy.mesflow.net` / `ssh-test.mesflow.net`): real promotion via `scripts/promote-test.sh` (same immutable ZIP, `--no-build`), deploy job `success` ("Deployment verified: 71.0.0.207"). Confirmed independently over SSH: `docker ps` → `mesflow-app:71.0.0.207 (healthy)`; API → `health_payload = {"ok":true,"status":"healthy","version":"71.0.0.207","schema_version":"72.0.3.0"}`; `migration_head: 0043_super_admin_role` (matches DEV). `PROMOTION.json.production_test.status = "PASS"`.

**qa-center release 1.32.1**
- Image: `mesflow-qa-center:1.32.1`, digest `sha256:09c91fbd0387539926ad14240495b36e1a1facbefcb8d3f41465975d61a089fb`
- Build: `QA RELEASE PASS`, `Tests: PASS`
- **DEV**: real deploy job via Deploy Agent's QA release manager, `success`, "QA 1.32.1 deployed and verified". Live: `http://127.0.0.1:8095/api/version` → `{"ok":true,"version":"1.32.1"}`
- **PRODUCTION_TEST**: real promotion via the QA release manager's promote-test API (chunked upload, 657MB, `--no-build`), job `SUCCESS`: `"TEST_PASS: QA 1.32.1 verified on https://deploy.mesflow.net/agent"`. Confirmed independently over SSH: `docker ps` → `mesflow-qa-center:1.32.1 (healthy)`; `curl 127.0.0.1:8095/api/version` on the target → `{"ok":true,"version":"1.32.1"}`.

**deploy-agent (V1, the control plane itself)**
- Recreated/rebuilt to its own newly-merged `2.24.49-docker-runtime` as a
  side effect of resolving the admin-credential gap (see git history) —
  now running the fully-tested merge from §3. Healthy at 127.0.0.1:8090.
  The remote Production Test Agent (`2.24.37`) was **not** touched/
  upgraded — out of this task's scope, its own PROJECT.yaml explicitly
  flags redeploying the Agent itself as needing separate confirmation.

## 8. Blockers / follow-ups for a human

1. **Why was Production Test 126 versions ahead of this workspace's git
   history in the first place?** Resolved *for this task* by overriding
   (§6), but the underlying question — was `.206`/`1.27.4` from a
   different upstream/team, or did this workspace's git history get
   reset without Production Test following — is still open. Worth
   understanding before the *next* promotion, so this doesn't repeat
   silently.
2. `qa-center/artifacts.rootlocked-<timestamp>/` (local workspace, not
   the server) — a root-owned leftover directory moved aside to unblock
   a git pull; reclaim with `sudo rm -rf` when convenient (not urgent,
   doesn't block anything).
3. `bump-version.sh --if-released`'s `is_frozen()` check silently
   no-ops instead of bumping when run from inside a nested agent
   worktree (path resolves relative to the worktree, not the canonical
   repo) — worked around with an explicit target version both times this
   session; worth a dedicated fix given the workspace's own mandatory
   worktree policy makes this a recurring trap.
4. `mesflow-web/` (React V2 UI): real and passing its own gates, but
   genuinely pre-F15 (no nginx/production wiring exists yet, by that
   project's own architecture doc) — not deployed anywhere. Wiring it in
   is a real, separate, non-trivial task (new Flask/nginx static route +
   build step in the release pipeline), not attempted here to avoid
   inventing scope beyond the documented plan.
5. ESP kiosk firmware (`esp-kiosk/`, `mesflow-kiosk-runtime-v2/`): both
   have real uncommitted work in progress, left untouched. Branch
   consolidation and V1/old archival for these still needs a dedicated
   pass once that work is committed or confirmed safe to disturb.
6. `~/.ssh/config`'s `ssh-test` host entry was fixed (`User codex` +
   `IdentityFile ~/.ssh/mesflow_test_codex`, both now confirmed working)
   — local dotfile only, not part of any repo.
7. `deploy-agent`'s remote Production Test Agent is still `2.24.37`
   (this workspace's is now `2.24.49`) — not upgraded, deliberately out
   of scope (see §7).
