# MESFlow Workspace V2 Consolidation — 2026-09-01 → 2026-09-02

STATUS: **PASS**

V1/V2 audit, branch consolidation across `mesflow/`, `deploy-agent/`,
`qa-center/`, `mesflow-web/`, real builds, and real deploys — verified on
every host actually in use — are done and pushed. §6 covers a real
topology confusion this session hit and resolved with the user
mid-session (worth reading before trusting hostnames like "dev"/"test"/
"production" in this workspace again). §9 is the current, final state of
every host touched.

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
| ESP32 kiosk firmware | `esp-kiosk/` | `mesflow-kiosk-runtime-v2/` | Both have real, in-progress **uncommitted work** (250-line diff in esp-kiosk, hardware-pin changes in kiosk-runtime-v2) — left untouched per explicit user instruction to preserve dirty state. Not registered as V2 in `WORKSPACE.yaml` yet; registering it is a deliberate scope decision the workspace's own docs say not to make in a foundation pass. **Update (§7):** the LOCAL_TEST backend `kiosk-v2-local-test.mesflow.net` these firmware repos' hardware tests rely on was taken down as part of consolidating `dev.mesflow.net` — see §7.4. |

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
| `agent/claude/release-71-0-0-80`, `agent/claude/gitignore-bump-lock`, `agent/claude/check-version-sync-dynamic-fix`, `agent/claude/projectflow-build-idempotent`, `agent/claude/fix-productivity-test-date`, `agent/claude/release-71-0-0-207` (new, this session) | **Merged** | Release-prep (two release cycles, 71.0.0.80 then 71.0.0.207 — see §6) + 3 real pre-existing tooling/test bugs found and fixed while gating the release (see §5). |

Main: `93085ec` → **`c130a07`** (local == `origin/main`, pushed).

### deploy-agent/

| Branch | Status | Action |
|---|---|---|
| `checkpoint/pre-consolidation-2026-08-27` | **Merged (base)** | Real, superset recovery snapshot (VERSION 2.24.49) — workspace main was stuck at 2.24.8 while the deployed source had drifted to 2.24.37 and the *live running container* to 2.24.48. Merged; also stripped 2.6MB of accidentally-swept zip/backup cruft, hardened `.gitignore`. |
| `agent/codex/ui-quality-audit` | **Merged (layered)** | Small (266-line) genuine delta on top of the checkpoint — 14 real merge conflicts resolved by inspection (every case: the checkpoint/newer side had strictly more functionality — richer tutorial job tracking, `version-doctor.sh` made mandatory per `AGENTS.md`, retry/backoff logic, `url_for()` vs hardcoded paths). Not a blanket ours/theirs — each hunk read before resolving. |

Main: `94312df` → **`c87edd0`** (pushed). Full `scripts/test-baseline.sh`: 473 passed, 21 skipped, source-ZIP build PASS. Fixed 3 pre-existing gaps found while gating: two test fixtures asserting a stale version-literal, and both the test's and the *real* `tools/build_source_package.py`'s missing `.test-venv` exclusion (was tripping its own secret scanner on `cryptography`'s `ssh.py`). This repo's own local admin password was also reset — see §7.5.

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
- **Local topology consolidated** (§7.4): this dev machine used to run
  two separate MESFlow app instances (`127.0.0.1:8080` "DEV/production
  role" + `127.0.0.1:8199` "LOCAL_TEST", each with their own Postgres).
  Per explicit user request, unified: `dev.mesflow.net` now points at
  `:8080` (the single remaining instance); the `:8199` stack
  (`compose.local-test.yml`) was stopped and removed.

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

## 6. Topology confusion hit mid-session — read before trusting any hostname here

This is the most important section for whoever reads this report next.

**What the workspace's own docs say** (`docs/DEV_PRODTEST_ENVIRONMENTS.md`,
written 2026-08-25):
```
DEV:              https://dev.mesflow.net  -> localhost:8199 (kiosk v2 LOCAL_TEST stack)
PRODUCTION-TEST:   https://prod.mesflow.net -> localhost:8299
Real production:   https://mesflow.net, https://deploy.mesflow.net -> mesflow-nginx -> mesflow-app:8080
```

**What this session found by actually connecting** (2026-09-01/02):
`deploy.mesflow.net`'s configured `MESFLOW_PRODUCTION_TEST_AGENT_URL` in
the local Deploy Agent's own `.env`, and the SSH host `ssh-test.mesflow.net`
the user pointed at for "production test", turned out to be **the exact
same physical machine** (identical container set over SSH: `mesflow-app`,
`mesflow-deploy-agent:2.24.37`, `mesflow-qa-center`). Deploying there and
then checking `https://mesflow.net` directly confirmed **`mesflow.net`
currently routes to that same machine too** — i.e. in this account's
actual current Cloudflare configuration, `mesflow.net` /
`deploy.mesflow.net` / `ssh-test.mesflow.net` are one host, and the docs'
"real production, out of scope" label for that host is **stale** — the
user confirmed explicitly, after seeing this, that this host is what they
consider their "prod test" environment today, not an untouchable separate
real-production box, and that deploying to it was correct, not an
accident. (A promotion attempt for `71.0.0.80` was made and initially
looked like a possible accidental-production-deploy incident before this
was clarified; nothing was rolled back per the user's explicit
confirmation once the situation was understood on both sides.)

**Real, separate blockers hit and resolved while acting on this host:**
- No working SSH credential for `ssh-test.mesflow.net` as configured
  (`~/.ssh/config` had it as user `ubuntu`, no identity file). User said
  "dùng ssh codex"; confirmed `codex@ssh-test.mesflow.net` with the
  existing `~/.ssh/mesflow_test_codex` key works. Fixed
  `~/.ssh/config` (`User codex` + `IdentityFile`) for next time.
- The real (separate) reason the first `71.0.0.80` promotion failed at
  `docker compose config --quiet`: the target's persistent
  `/opt/mesflow/.env` was missing `MESFLOW_SECRET_KEY` (a required var
  this workspace's `compose.yml` declares with no default) — whatever was
  running there before predates that requirement. Generated a fresh
  `secrets.token_hex(32)` value and appended it via
  `docker exec -u root mesflow-deploy-agent` (that container already
  bind-mounts `/opt/mesflow`, so this needed no host-level `sudo`, which
  `codex` doesn't have on this box either).
- Per explicit user direction ("lấy main làm gốc, nâng hết version lên
  cao nhất và override các version khác"): bumped `mesflow/` past
  whatever that host was running (`71.0.0.206` — a version that does not
  exist anywhere in this workspace's git history) to `71.0.0.207`,
  monotonic per RULE 5, rather than reusing/colliding with a number this
  repo never produced.

**Net effect**: `docs/DEV_PRODTEST_ENVIRONMENTS.md` needs a rewrite by
someone with full context on the real current Cloudflare/DNS setup — not
attempted here, since this session doesn't have enough certainty about
*why* the docs and reality diverged (a later manual DNS change? the doc
was aspirational and never fully executed?) to safely rewrite it. What's
certain and stated here is only what was directly observed.

## 7. Evidence

### 7.1 mesflow-app release 71.0.0.207
(71.0.0.80 was built and DEV-verified first — see git history — then
superseded once §6's topology finding came up)
- Source commit: `c130a075ce392c3e926e05f95cda62e4cf911ad4`
- Image: `mesflow-app:71.0.0.207`, digest `sha256:3f3ee909a24122b261dc5e0b182947450df1c2c7cc1c7e68349b5fda093dbbd2`
- ZIP: `MESFlow_71.0.0.207.deploy.zip`, sha256 `7773431f717288f48d9512ba2cd544b48bd1b4e3a2c22fa1ae79a1ba5bcb1860`
- `scripts/release-local-qa.sh`: **PASS** (version-verify, preflight, build, full `docker-test.sh` incl. Playwright, isolated-sandbox deploy-local, smoke, status — all PASS; evidence at `artifacts/qa/71.0.0.207/release-local/release-local-qa.json`, submitted to Deploy Agent's release-gate API — `PROMOTION.json.local.status = "success"`)
- **Local / `dev.mesflow.net`** (same instance, port 8080 — see §7.4): real deploy job (Deploy Agent 127.0.0.1:8090), `success`. Live: `/api/system/ready` → `{"ok":true,"status":"ready","version":"71.0.0.207","migration_head":"0043_super_admin_role"}` on both `http://127.0.0.1:8080` and `https://dev.mesflow.net`.
- **`mesflow.net` / `deploy.mesflow.net` / `ssh-test.mesflow.net`** (§6 — one host): real promotion via `scripts/promote-test.sh` (same immutable ZIP, `--no-build`), deploy job `success`. Confirmed independently over SSH and over HTTPS: `docker ps` on the host → `mesflow-app:71.0.0.207 (healthy)`; `curl https://mesflow.net/api/system/ready` → `{"ok":true,"status":"ready","version":"71.0.0.207","migration_head":"0043_super_admin_role"}`. `PROMOTION.json.production_test.status = "PASS"`.

### 7.2 qa-center release 1.32.1
- Image: `mesflow-qa-center:1.32.1`, digest `sha256:09c91fbd0387539926ad14240495b36e1a1facbefcb8d3f41465975d61a089fb`
- Build: `QA RELEASE PASS`, `Tests: PASS`
- Local: real deploy job via Deploy Agent's QA release manager, `success`. Live: `http://127.0.0.1:8095/api/version` → `{"ok":true,"version":"1.32.1"}`
- `mesflow.net`-host: real promotion via the QA release manager's promote-test API (chunked upload, 657MB, `--no-build`), job `SUCCESS`: `"TEST_PASS: QA 1.32.1 verified..."`. Confirmed via SSH: `docker ps` → `mesflow-qa-center:1.32.1 (healthy)`; `curl 127.0.0.1:8095/api/version` on the host → `{"ok":true,"version":"1.32.1"}`.

### 7.3 deploy-agent (V1, the control plane itself)
- Local instance: recreated/rebuilt to its own newly-merged
  `2.24.49-docker-runtime` as a side effect of resolving the local
  admin-credential gap — now running the fully-tested merge from §3.
  Healthy at 127.0.0.1:8090.
- The `mesflow.net`-host Deploy Agent is still `2.24.37` — **not**
  upgraded/redeployed, deliberately: its own `PROJECT.yaml` flags
  redeploying the Agent itself as needing separate confirmation, and this
  task's scope was the applications it deploys, not itself.

### 7.4 Local topology consolidation (`dev.mesflow.net`)
Per explicit user request ("thống nhất cho dev.mesflow.net trỏ vào 8080
luôn đi, tắt server 8199"):
- `~/.cloudflared/kiosk-local-test-config.yml`: `dev.mesflow.net`'s
  ingress rule changed from `http://localhost:8199` to
  `http://localhost:8080`; `systemctl --user restart
  cloudflared-kiosk-local-test.service` applied it.
- `docker compose -f compose.local-test.yml --env-file .env.local-test
  down` — stopped and removed `mesflow-local-test-app` +
  `mesflow-local-test-db` (port 8199).
- **Side effect, confirmed and accepted by the user**: the same tunnel
  config's other hostname, `kiosk-v2-local-test.mesflow.net` (used by
  `esp-kiosk/`/`mesflow-kiosk-runtime-v2/` real-hardware testing per
  §2), now returns `502` — it shared the same `:8199` backend and was
  not given a replacement. If ESP32 kiosk hardware testing resumes, that
  backend needs to be decided on again (its own dedicated stack? point it
  at `:8080` too? see whoever owns that firmware work first, given both
  those repos currently have real uncommitted changes).
- Verified: `curl https://dev.mesflow.net/api/system/ready` and
  `curl http://127.0.0.1:8080/api/system/ready` return identical
  `71.0.0.207` payloads (literally the same running container now).

### 7.5 Admin credentials reset to a single known password
Per explicit user request ("reset password về Admin@123456 hết"),
reset on every host this session had write access to, using each
system's own official reset path (`python -m mesflow.cli reset-admin`
for the app; the Deploy Agent's own `MESFLOW_AGENT_ADMIN_PASSWORD`
env-driven `ensure_config()` bootstrap/reset for the Agent) — never a
raw DB/hash edit. All verified by an actual login call (not just "command
returned success"):

| Host | Component | Verified |
|---|---|---|
| Local (127.0.0.1:8090) | Deploy Agent | ✅ `admin`/`Admin@123456` logs in |
| Local (127.0.0.1:8080) / `dev.mesflow.net` | MESFlow app | ✅ `POST /api/auth/login` → `200 ok:true` |
| `deploy.mesflow.net` | Deploy Agent | ✅ `admin`/`Admin@123456` logs in |
| `mesflow.net` | MESFlow app | ✅ `POST /api/auth/login` → `200 ok:true` |

`qa-center` has no separate admin-login credential of its own to reset
(confirmed — no `ADMIN_PASSWORD`-style config in its compose/source).

## 8. Blockers / follow-ups for a human

1. **`docs/DEV_PRODTEST_ENVIRONMENTS.md` is now materially wrong** (§6) —
   needs a rewrite by someone who knows the real current DNS/Cloudflare
   intent for `mesflow.net`/`dev.mesflow.net`/`prod.mesflow.net`. Not
   attempted here; this session only has direct-observation-level
   certainty, not the "why."
2. **`kiosk-v2-local-test.mesflow.net` has no backend anymore** (§7.4) —
   whoever resumes ESP32 kiosk v2 hardware testing needs a decision on
   where that backend lives now.
3. `prod.mesflow.net` (port 8299, `mesflow-prodtest-app`/`-db`) was never
   touched this session — still whatever version it was before. Not in
   scope of anything explicitly asked; flagging only because §6 means its
   role relative to `mesflow.net` is no longer obviously "the same tier."
4. `qa-center/artifacts.rootlocked-<timestamp>/` (local workspace, not a
   server) — a root-owned leftover directory moved aside to unblock a
   git pull; reclaim with `sudo rm -rf` when convenient (not urgent).
5. `bump-version.sh --if-released`'s `is_frozen()` check silently
   no-ops instead of bumping when run from inside a nested agent
   worktree (path resolves relative to the worktree, not the canonical
   repo) — worked around with an explicit target version both times this
   session; worth a dedicated fix given the workspace's own mandatory
   worktree policy makes this a recurring trap.
6. `mesflow-web/` (React V2 UI): real and passing its own gates, but
   genuinely pre-F15 (no nginx/production wiring exists yet, by that
   project's own architecture doc) — not deployed anywhere. Wiring it in
   is a real, separate, non-trivial task, not attempted here.
7. ESP kiosk firmware (`esp-kiosk/`, `mesflow-kiosk-runtime-v2/`): both
   have real uncommitted work in progress, left untouched. Branch
   consolidation and V1/old archival for these still needs a dedicated
   pass once that work is committed or confirmed safe to disturb.

## 9. Final state snapshot (2026-09-02)

| Target | mesflow-app | qa-center | deploy-agent | Admin login |
|---|---|---|---|---|
| Local (`127.0.0.1:8080`) == `dev.mesflow.net` | 71.0.0.207 ✅ | — | 2.24.49 (127.0.0.1:8090) ✅ | `admin`/`Admin@123456` |
| `mesflow.net` == `deploy.mesflow.net` == `ssh-test.mesflow.net` | 71.0.0.207 ✅ | 1.32.1 ✅ | 2.24.37 (untouched) | `admin`/`Admin@123456` |
| `prod.mesflow.net` (port 8299) | untouched this session | untouched | n/a | untouched |
| `kiosk-v2-local-test.mesflow.net` | n/a (backend removed) | — | — | — |

Real production (if `mesflow.net` is ever repointed at a genuinely
separate, untouchable box in the future) was never identified as existing
separately from the host above during this session — see §6 for why that
matters.
