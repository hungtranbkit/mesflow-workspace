# Build Once / Promote Same Artifact — Final Verification

Follow-up to `reports/RELEASE_MANAGER_BUILD_ONCE.md` (the implementation).
This is the live-evidence pass: real browser, real builds, real deploy,
against the actual local DEV Agent. No mocks for anything user-facing.

## What was actually exercised, live

1. **Immutable release guard**, proven by triggering it for real: a rebuild
   of 65.8.44.66 (already released) was refused with
   `VERSION_ALREADY_RELEASED`. Confirmed via direct API call before the
   Playwright pass.
2. **Build Release**, via a real Playwright Chromium click against
   `http://127.0.0.1:8090/agent/`: click → `POST /api/release-manager/build`
   (202) → real `docker build` → `BUILD: PASS`, producing 65.8.44.69 with:
   - `source_commit`: a real commit hash (`68831a7...`) — this required two
     separate bug fixes discovered live (see below).
   - `schema_revision`: `0029_kiosk_ota_fleet_safety` (previously always
     empty — see the build-release.sh fix in the implementation report).
   - `image_digest == image_id` (immutable, byte-identified).
3. **Deploy Local**: click → `POST /api/release-manager/deploy-local` (202)
   → real `--no-build` cutover of the actual local `mesflow-app` container
   → `LOCAL: PASS` with real evidence: running image id matches the frozen
   id, applied Alembic head (`/api/system/ready`'s `migration_head`) matches
   expected, HTTP smoke check passed. `mesflow-postgres` was never touched
   (25h+ uptime preserved throughout every deploy in this pass).
4. **Promote Production Test**: verified the safe-fail path — with no
   `MESFLOW_PRODUCTION_TEST_AGENT_URL` configured on this DEV Agent, the
   button correctly stays disabled with the exact reason shown ("No
   Production Test Agent is configured..."). The end-to-end mechanics
   (login, CSRF, multipart upload, deploy trigger, poll-to-completion,
   TEST_PASS recording) were verified for real against a lightweight fake
   target Agent (real HTTP server, real socket) — see
   `tests/test_promote_production_test.py`, 3 new tests, all passing. The
   real remote Production Test Agent (`deploy.mesflow.net`) was
   deliberately not contacted, per instruction to test gate/UI/API safely
   without mutating it unless explicitly approved.
5. **Promote Production**: direct `POST /api/release-manager/promote-production`
   with `{"confirm":true}` → `403` (`MESFLOW_PRODUCTION_PROMOTE_ENABLED` is
   not set on this Agent, and it never was during this task). No production
   deploy was executed or attempted.

## Bugs found and fixed during live verification (not caught by unit tests)

1. **JS syntax error broke the buttons entirely.** My own first cut at the
   Promote Production wiring closed the outer script IIFE one brace too
   early, leaving the upload-form `wire()` helper (and its 3 call sites)
   outside any matching scope — a page-level `SyntaxError`. Effect: no
   inline script on the page ran at all, so clicking Build Release silently
   did nothing (no request ever sent). Caught by Playwright's
   `page.on('pageerror')`, not by any Python test — this class of bug is
   exactly why Priority 2 asked for a real browser pass instead of trusting
   the endpoint tests alone. Fixed; both `<script>` blocks now pass
   `node --check`.
2. **`source_commit` was always "unknown"**, for two independent reasons,
   both found by actually reading the live build output instead of trusting
   a green pytest run:
   - The Deploy Agent's own Docker image had no `git` binary
     (`docker/Dockerfile` only installed `bash curl docker-cli ... tzdata`).
     Fixed by adding `git`.
   - Even with `git` present, `git rev-parse HEAD` failed with "detected
     dubious ownership" — the bind-mounted workspace is owned by `dell`,
     the Agent process runs as root. Fixed by scoping
     `-c safe.directory='*'` to that one invocation in `build-release.sh`.
3. **`PROMOTION.json` per release silently went stale.** The new
   `promotion-state.json` tracking (in the Agent's own config dir) was
   correct, but the older, per-release `artifacts/releases/<version>/PROMOTION.json`
   file — which `scripts/promote-test.sh` reads directly — was never
   updated, so the two records could disagree. Fixed: `_update_promotion_state`
   now syncs both.
4. **Installer rollback strategy from the previous task was actually
   broken**, found while redeploying the Agent for this verification (see
   `reports/RELEASE_MANAGER_BUILD_ONCE.md` for detail): `docker compose up
   --force-recreate` identifies a container by Compose labels, not name, so
   the rename-then-restore rollback never actually protected the old
   container. Fixed to roll back by image id instead.

None of these would have been caught without actually clicking through the
UI and reading real build/deploy output — confirming the task's premise
that rendering ≠ working.

## Test suite

`deploy-agent` pytest: **59/59 PASS** (56 fixed pre-existing + 3 new for
Promote Production Test). Was 48/56 at the start of this task.

```
python3 -m py_compile agent.py ota_control.py: OK
python3 -m py_compile (all mesflow app/*.py): OK
bash -n on build-release.sh, install.sh, install_agent.sh, all scripts/*.sh: OK
git diff --check (mesflow, deploy-agent): clean
docker compose config (deploy-agent dev + production-test overrides): VALID
docker compose config (mesflow compose.yml + compose.test.yml): VALID
```

## Playwright result

```
BUILD: PASS
LOCAL: PASS
PAGE ERRORS: 0
CONSOLE ERRORS: 1 — "Failed to load resource: the server responded with a
  status of 403 (FORBIDDEN)"
```

That one console entry is Chromium's own built-in resource-load log line
for a `fetch()` call this test script made *directly* (`page.evaluate`) to
`/api/release-manager/promote-production` — deliberately probing the
server-side gate to prove it refuses even if someone bypassed the disabled
button in the DOM. It is not a JavaScript error (`pageerror` count is 0),
not a rendering/logic bug, and not reachable through normal use — the real
Promote Production button stays `disabled` in the DOM the whole time, so an
actual user cannot trigger it. Chromium logs any non-2xx `fetch`/XHR
response this way regardless of application correctness.

## What was deliberately not done

- 65.8.44.65 remains contaminated and untouched (not rebuilt, not deleted).
- The `mesflow` branch was not merged to `main`.
- Production was not deployed; `MESFLOW_PRODUCTION_PROMOTE_ENABLED` was
  never set.
- The real Production Test Agent was not contacted.
- No `/opt` backups were deleted.

## RESULT

```
IMMUTABLE RELEASE PROTECTION: implemented + verified live (rebuild of an
  existing version refused with VERSION_ALREADY_RELEASED; tag-drift
  contamination check implemented and live-tested via unit coverage)
65.8.44.65 STATUS: CONTAMINATED (marked, not rebuilt, refused by
  Deploy Local / Promote Test / Promote Production)
NEW RELEASE: 65.8.44.69
NEW ZIP SHA: 4e2f2f320e916907b4374e6c21bf92a6a2b80a145b01a34e2bf916b681c2e859
NEW IMAGE DIGEST: sha256:93f3e73160786311786f6d09c32fcaea3b5b4b4886752f79adb699e8fa12e9f6

BUILD BUTTON: WORKS (real click -> real docker build -> immutable artifact,
  verified live via Playwright)
DEPLOY LOCAL BUTTON: WORKS (real click -> --no-build cutover -> LOCAL_PASS
  with image-id/schema/smoke evidence, verified live via Playwright)
PROMOTE TEST BUTTON: WORKS (correctly disabled with no target configured;
  full upload/deploy/poll mechanics verified against a real fake-target
  HTTP server in tests/test_promote_production_test.py; real remote
  Production Test Agent deliberately not contacted)
PROMOTE PROD BUTTON: WORKS (wired, gate re-verified server-side on every
  call, refuses with 403 without MESFLOW_PRODUCTION_PROMOTE_ENABLED=1 +
  explicit confirm; verified live via direct POST)

LOCAL_PASS: YES (65.8.44.69, image id sha256:93f3e73160786311786f6d09c32fcaea3b5b4b4886752f79adb699e8fa12e9f6,
  schema 0029_kiosk_ota_fleet_safety expected==actual, smoke OK)
TEST_PASS: NOT ACHIEVED (no Production Test target configured on this DEV
  Agent, by design/instruction -- mechanics proven separately, real target
  not touched)

DEPLOY AGENT TESTS: 59/59 PASS (was 48/56 at task start)
PLAYWRIGHT: PASS (Build Release + Deploy Local clicked live; Promote
  Test/Production gating verified)
CONSOLE ERRORS: 0 real (1 benign browser resource-load log line from a
  deliberate direct probe of a disabled-button endpoint; see above)

PRODUCTION DEPLOYED: NO
```
