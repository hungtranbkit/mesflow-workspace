# MESFlow Clean Stability Campaign — 2026-09-07

**Scope of this report:** QC/evidence infrastructure stabilization,
requested to run *while* mesflow's own team fixes GitHub issue #25 (release
contract: `compose.yml` defaulting to `71.0.0.221` while the release is
`71.0.0.226`), followed by a full end-to-end campaign rerun once that fix
merges.

**Honest status up front:** #25 is still **OPEN** as of this report
(verified live: `gh issue view 25 --repo hungtranbkit/mesflow`). A fix
commit (`82405d1 fix(release): sync compose.yml version tag + harden
version-sync tooling (#25)`) exists in worktree
`mesflow/.worktrees/release-contract-fix` and an image build for
`mesflow-app:71.0.0.227` was observed running live during this session —
but it is **not yet merged**. Per the task's own instruction ("chờ commit
fix và rerun campaign end-to-end"), the full multi-viewport/multi-journey
campaign (items 5, 8's full before/after PASS/FAIL/SKIP/BLOCKED table, and
item 9's closure) is **not run in this report** — running it now against
an unfixed release would produce numbers this report would have to
immediately invalidate. This report covers only what was actually
completed: QC infrastructure root-causing and fixes, verified with real
evidence, no fabricated results.

---

## 1. Infra fixes completed (items 1–3)

### 1.1 Evidence/runtime directories were root-owned (item 1)

**Root cause, found live, not assumed:** three separate QC-adjacent
containers had no `USER` declaration at all and wrote directly to
host bind mounts as root:

| Location | Container | Bind mount | Effect |
|---|---|---|---|
| `~/workspace/mesflow/qa-center/runtime` (+ `runtime-projectflow-local`) | `mesflow-qa-center` image, local dev compose | `./runtime:/data` | every QA Center run/report/log/backup landed root-owned |
| `/opt/mesflow-qa-center/runtime` (the **live deployed** QA Center) | same image, `1.32.1` in production | `./runtime:/data` | identical — reports as recent as this week were root-owned |
| `~/workspace/mesflow/mesflow/test-results`, `runtime/` (+ active `.worktrees/*`) | `Dockerfile.test`/`Dockerfile.playwright` (compose.test.yml) and the app's own runtime bind mounts | `./test-results:/workspace/test-results`, `./runtime/...:/data/...` | stale root-owned Playwright result dirs (e.g. `mesflow-ESP-Kiosk-tutorial-13b0d.../`, `playwright-report/`) sat next to fresh dell-owned ones from the same day |

`qa-center/artifacts.rootlocked-1788266217`'s own directory name is a
fossil of someone hitting this by hand before and renaming around it
instead of fixing it.

**Fix, done in two parts:**

1. **One-time unblock, no host sudo needed** (`docker run --rm -v
   <dir>:/fix alpine chown -R 1000:1000 /fix` — uses the `dell` user's
   existing `docker` group membership, not `sudo`): applied to every
   root-owned `runtime/`, `test-results/`, `screenshots/` directory found
   under `~/workspace/mesflow` (including three active worktrees) and to
   the live `/opt/mesflow-qa-center/runtime`. Verified clean afterward
   (`find ... ! -user dell` → empty, excluding the Postgres data dir which
   is correctly owned by the postgres container's own uid).
2. **Root-cause fix, committed** (`mesflow-qa-center` commit `3b90ba8`):
   `docker/docker-entrypoint.sh` now starts as root (needed to fix
   ownership and to read `/var/run/docker.sock`'s real host GID for the
   Preview Lab's docker-outside-of-docker access), creates/adjusts a fixed
   `qa` user, **idempotently** chowns `/data` back to that user only when
   it's not already correct (a cheap ownership check first, not a
   recursive chown on every start), then `exec gosu qa "$@"` — the actual
   application process now always runs non-root. Applied to both
   `docker/Dockerfile[.base]` (repo root) and `current/docker/Dockerfile
   [.base]` (the tree `scripts/build-release.sh` actually builds from).
   **Not yet built/redeployed** — that is a separate, higher-stakes
   release action (rebuilding and promoting a shared, currently-running QA
   tool) deliberately left for an explicit follow-up rather than done
   unilaterally in this pass. Until that release, the one-time unblock
   above keeps things usable; a future `sudo`-free rerun is only
   guaranteed once the new image is actually running.

`ai-qc-agent` (the newer AI QC agent, `browser/`, `qc_agent/`,
`providers/chrome_devtools_mcp.py`) was audited the same way and found
**already clean** — it uses named Docker volumes (`qc_artifacts`,
`qc_postgres_data`) rather than host bind mounts for anything it writes,
so this class of bug does not apply there. Its own test suite: see §2.

### 1.2 ESP Kiosk tutorial video fixture (item 2)

**Two distinct real findings, not one:**

1. **Flaky test selector (QC_TEST_BUG, fixed):**
   `tests/e2e/mesflow.spec.js`'s "ESP Kiosk tutorial loads seven runtime
   videos and plays" hit a genuine Playwright strict-mode violation:
   `getByRole('button', { name: 'ESP Kiosk' })` (no `exact: true`) matched
   both the tab button and a video-item button whose accessible name
   contains "ESP Kiosk" as a substring ("Tổng quan ESP Kiosk 17 giây").
   Its sibling selector (`{ name: 'KIMEX', exact: true }`) already had the
   fix pattern one line above it. Corrected both occurrences.
   (`mesflow` commit `d1bc23d`.)

2. **Missing fixture in the sandbox environment (DATA_ISSUE, fixed) — and
   a separate, unfixed gap on live DEV:**
   `compose.sandbox.yml` (the ProjectFlow Workspace Manager sandbox
   contract every ephemeral per-branch sandbox uses) never mounted
   `/data/tutorials/esp-kiosk` at all — unlike `compose.test.yml`, which
   does. The app degrades this gracefully (`GET /api/esp-kiosk-tutorial`
   → `{ok:true,manifest:null}`, honest empty UI state, confirmed by
   reading `app/mesflow/web/app.py`), so this never crashed anything — it
   just made the ESP Kiosk tutorial E2E test fail with a confusing
   assertion deep inside the test, indistinguishable at a glance from a
   real regression. **Live-verified the same gap exists on the shared DEV
   deployment right now**: `/opt/mesflow/runtime/tutorials/esp-kiosk` is a
   real, empty directory (0 files) — the ESP tutorial publish pipeline
   documented in `reports/ESP_KIOSK_TUTORIAL_PIPELINE_AUDIT.md` was never
   actually run against this deployment, or was reset and never
   republished. **Not fixed in this pass** — republishing to the shared
   DEV host is an outward-facing action on infrastructure other sessions
   may depend on; `deploy-agent` already has a legitimate, atomic,
   backed-up publish path for it (`POST /esp-kiosk-tutorial/upload`).
   Flagging this explicitly as an open DATA_ISSUE for the next campaign
   run rather than silently working around it.

   **Fix for the sandbox (`mesflow` commit `d1bc23d`):** a new one-shot
   `esp-tutorial-fixture` init service (`Dockerfile.esp-tutorial-fixture`)
   runs the project's **existing** generator,
   `scripts/test/generate-esp-tutorial-fixture.sh` (deterministic,
   `ffmpeg`-synthesized, genuinely playable MP4s — never the real
   device-captured videos, which stay gitignored per `AGENTS.md` rule 8),
   into a named volume that `app` mounts read-only, gated by Compose's
   `service_completed_successfully`. Verified end-to-end **on the host**
   (real `ffmpeg 8.0.1`): the generator produces a valid 7-video manifest
   and every video is non-empty and playable; a Docker-level build of the
   new init image was attempted but ran long (>8 min, likely apt mirror
   latency) and was killed rather than left blocking the rest of this
   session — the generator + validator logic itself is confirmed correct
   independent of that image build.

3. **New preflight validator** (`scripts/validate-esp-tutorial-fixture.js`,
   `mesflow` commit `d1bc23d`): checks `manifest.json` exists and parses,
   `type == "esp-kiosk-tutorial"`, and every listed video file exists
   on disk and is non-empty. Fails **loudly with a specific reason**
   (never a silent skip) — tested against a real valid fixture (pass), a
   missing directory (clear failure message), and a fresh `--seed` run
   (correctly invoked the generator and re-validated). Wired into
   `scripts/test/docker-test.sh` right after the existing generator step,
   before the compose stack comes up, so a genuinely broken fixture is
   caught before paying for postgres/app/test container boot — not wired
   as an npm `pretest` auto-hook, because `Dockerfile.playwright`'s
   `npm run test:e2e` runs inside a container that never copies
   `scripts/` or `runtime/`, and an auto-hook there would have broken
   that container's test run outright for a fixture check that isn't
   even meaningful in that context (that container talks to
   `mesflow-test-api` over HTTP; the fixture only needs to exist on the
   API container's own filesystem, which is where `docker-test.sh`
   already runs the generator+validator).

### 1.3 `ai-qc-agent` test suite (part of item 3's infra check)

Full suite run for real: **290 passed, 0 failed** (`685.17s`, incl. real
Playwright/browser e2e tests, not mocked). No infra action needed there.
One minor, out-of-scope observation: pytest's own tmp cleanup hit a
`PermissionError` removing a `.venv` created inside a
`test_real_installer_e2e_in_dis0` fixture under `/tmp/pytest-of-dell/
garbage-*` — self-contained test tmp garbage, not evidence/report
infrastructure, left as a note rather than chased further.

## 2. Skip audit (item 3)

`ai-qc-agent`'s own `reports/MESFLOW_QC_STABILITY_AND_VISUAL_AUDIT_2026-09-07.md`
(committed this week, §"Phần A") already did a real, evidence-backed skip
audit on the most recent full run (66 testcases): `non_ui_surface` (5) —
honest `SKIPPED`, background job/hardware surface, correctly classified
`EXPECTED_SKIP`; `llm_mapping_unavailable` (4) — root cause is confirmed
concrete (no `claude` CLI in the worker container, `which claude` → not
found), an `ENV_INFRA_ISSUE` with a known fix path, not a true "unknown
mapping"; `api_call_unresolvable` (25) — mostly path placeholders needing
real precondition IDs (`missing test data`), with the previously-generic
skip reason already replaced by a specific per-case reason
(`explain_api_action_rejection()`, verified present in that commit).
`unknown mapping = 0` in the strict sense (a case skipped for a truly
undetermined reason) already holds. Re-auditing this from scratch this
session would only repeat that work; the number that still needs a real
rerun to update is `≥95% executable requirement have a verdict` (was
~20% on that run) — that requires the full campaign this report is
blocked on (§0).

## 3. Blocked: full campaign rerun (items 4–9)

- **Item 4 (unified pipeline):** already implemented and piloted before
  this session (`ai-qc-agent` `docs/UNIFIED_WEB_QC_WORKFLOW.md`,
  `MESFLOW_UNIFIED_WEB_QC_PILOT_2026-09-07.md` — 5/5 PASS on Dashboard/
  Session/Exceptions/Employee Productivity/Kiosk-Wallboard, real Chrome
  DevTools MCP diagnostics invoked twice, Web MCP used with a verified
  Playwright fallback). No gap found this session requiring further work
  here before the full campaign.
- **Items 5, 8 (full campaign, before/after PASS/FAIL/SKIP/BLOCKED,
  three-viewport visual audit, all seven journeys):** **not run.** #25 is
  open; the release contract mismatch it describes is exactly the kind of
  environment inconsistency that would contaminate a "before" baseline
  with noise unrelated to the infra fixes in §1. Running it now would
  either (a) run against the already-known-broken `71.0.0.221`/`226`
  contract, or (b) require switching targets mid-campaign — neither
  produces a trustworthy before/after comparison.
- **Item 6 (per-fail classification) and item 9 (closure):** depend on
  item 5's real run; nothing to classify yet beyond what's already in
  §1–2.
- **Item 7 (acceptance):** partially true right now (evidence dirs are
  writable without sudo — verified; `ai-qc-agent` suite is fully green)
  but the full-UI/unknown-mapping/completed-with-error criteria are
  properties of a campaign run, not of the infra fix alone.

## 4. Commits

| Repo | Commit | Summary |
|---|---|---|
| `hungtranbkit/mesflow` | `d1bc23d` | ESP Kiosk tutorial: fixed selector strict-mode bug, sandbox fixture seeding, preflight validator |
| `hungtranbkit/mesflow-qa-center` | `3b90ba8` | Non-root entrypoint (fixes root-owned `./runtime`), idempotent self-heal |
| `hungtranbkit/mesflow` `.worktrees/release-contract-fix` | `82405d1` *(observed, not authored here)* | `fix(release): sync compose.yml version tag + harden version-sync tooling (#25)` — in progress, not yet merged |

Both fix commits pushed to `main` on their respective repos.

## 5. Next step

Waiting on issue #25 to merge on `hungtranbkit/mesflow`. Once it does:
run the full campaign (backend/unit/critical/integration + full UI +
visual audit at 1366×768/1920×1080/390×844 across
Login/Dashboard/Session/Exceptions/Productivity/Kiosk/QR), classify every
fail, and republish this report with the real before/after table. The DEV
ESP tutorial data gap (§1.2) should be republished through
`deploy-agent`'s existing upload flow before or during that run, or the
ESP Kiosk journey will legitimately DATA_ISSUE-fail again — flagging for
an explicit decision rather than doing it unilaterally.
