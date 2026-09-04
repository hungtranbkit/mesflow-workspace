# Safe Autologin for Fast Internal Testing — 2026-09-04

Task: add a dev/demo/test-only autologin mechanism so a tester or a
Playwright spec can skip typing username/password, without weakening
real production. Full design/usage doc:
`mesflow/docs/AUTOLOGIN.md` (committed alongside the code).

## Root cause / key finding

A real, already-tested, already-e2e-integrated mechanism **already
existed** in the codebase under `MESFLOW_TEST_AUTO_LOGIN` — a
server-side session bootstrap route (`POST /api/auth/test-auto-login`)
already used by dozens of `tests/e2e/*.spec.js` files, already hard-blocked
on `MESFLOW_ENV=production`, already covered by a dedicated
`test_v6584431_production_hardening.py`. It covered most of this task's
requirements out of the box. This task extended it rather than building
a parallel `MESFLOW_AUTOLOGIN_ENABLED` mechanism (the name given in the
task as an example, not found anywhere in the codebase) — introducing a
second flag that does the same thing would have meant every place that
currently enumerates "the auto-login flags that must be 0 in production"
(`scripts/production-preflight.sh`, the hardening test) needed updating
too, or silently gains a gap. This is documented in full in
`docs/AUTOLOGIN.md`'s "Why this reuses an existing mechanism" section.

**Real gap found and fixed**: `compose.yml` hardcodes `MESFLOW_ENV:
production` on every tier that shares it — prodtest and the demo
container included (confirmed directly: `docker exec mesflow-demo-app
printenv` and `docker exec mesflow-prodtest-app printenv` both show
`MESFLOW_ENV=production`). The existing guard (`environment !=
"production"`) therefore never actually allowed auto-login on demo or
prodtest, contradicting the task's explicit requirement to allow it
there. Fixed with a second, explicit, default-off opt-in
(`MESFLOW_TEST_AUTO_LOGIN_ALLOW_PRODUCTION`), mirroring the exact
pattern this codebase already uses elsewhere for the same shape of
problem (`tutorial_data.py`'s `MESFLOW_TUTORIAL_DATA_ALLOW_PRODUCTION`).
Deliberately **not** gated on `SERVER_ROLE` — `core/config.py`'s own
docstring on that field explicitly forbids inferring security-gated
behavior from it (a human-facing label with no validation, kept
separate from `MESFLOW_ENV` on purpose after a past incident).

## Design summary

| Requirement | How it's met |
|---|---|
| 1. Feature flag, default off | `MESFLOW_TEST_AUTO_LOGIN` (already existed, default `0`) |
| 2. DEV/DEMO/TEST/PRODTEST only, real prod force-disabled + logged | `MESFLOW_ENV != production` always allowed; `== production` requires the new `MESFLOW_TEST_AUTO_LOGIN_ALLOW_PRODUCTION` override too. Boot-time **and** per-request `app.logger.warning(...)` either way. `scripts/production-preflight.sh` fails the release if the override is set. |
| 3. Persona from env, no hardcoded secret in frontend | `MESFLOW_TEST_AUTO_LOGIN_USERNAME` (already existed). `login.js` never sends/stores a password — it POSTs to a server route that looks the account up server-side and calls the same `session_policy.start_session()` a real login uses. |
| 4. Quick persona switch, non-production only | New: `persona` query/body param on `/api/auth/test-auto-login`, fixed allowlist `{admin,manager,supervisor,operator,viewer}`, resolved via the existing username-equals-role seed convention (verified against real local DEV/demo DBs). Same guard as the base flag. |
| 5. Real login flow untouched when off; logout works; no logout→autologin loop | `/api/auth/login` untouched. Logout button now redirects to `/login?noauto=1`; that query param suppresses the auto-trigger on any `/login` render, an explicit visible override. |
| 6. Playwright integration without losing real-login coverage | Already existed (dozens of specs call the route directly) — unchanged, regression-tested. Real-login group kept: `tests/e2e/tutorial-video.spec.js` still uses `/api/auth/login` with a real password, asserted by `test_tutorial_uses_password_login`. |
| 7. No secret in HTML/JS, no new public route, no global backend bypass | One existing route, one `session_policy.start_session()` call, fixed persona allowlist. This codebase already tried and removed a broader auto-login-style bypass once (`MESFLOW_INTERNAL_QA_AUTO_LOGIN`, now wired to nothing — see `test_internal_qa_login_contract.py`); this task does not reintroduce that shape. |
| 8. Documentation | `docs/AUTOLOGIN.md` — flags, personas, production guard, anti-loop, Playwright integration, local/demo examples. |
| 9. Regression/auth/RBAC/smoke + live UI verify | See below. |
| 10. Prefer simpler/safer, no scope creep | Reused the existing mechanism instead of a parallel one; declined to rename it (real blast radius, no functional benefit) — documented as a deliberate choice, not an oversight. |

## Files changed

- `app/mesflow/core/config.py` — `test_auto_login_allow_production` field.
- `app/mesflow/web/app.py` — `_AUTOLOGIN_PERSONAS`, `_auto_login_allowed()`, boot-time warning log, `login_page()`'s `?noauto=1` handling, `test_auto_login()`'s guard + persona resolution.
- `app/mesflow/web/static/login.js` — reads `?persona=` from the URL, passes it to the auto-login POST.
- `app/mesflow/web/static/app.js` — logout now redirects to `/login?noauto=1`.
- `compose.yml` — `MESFLOW_TEST_AUTO_LOGIN_ALLOW_PRODUCTION` passthrough (default `0`).
- `compose.projectflow-local.yml` — `MESFLOW_TEST_AUTO_LOGIN`/`_USERNAME` passthrough (this compose file had no way to opt in at all before; needed for this task's own verification).
- `scripts/production-preflight.sh` — real-production release gate now also fails on the new override flag.
- `docs/AUTOLOGIN.md` — new, full design/usage doc.
- `tests/test_autologin_guard_unit.py` — new, DB-free `create_app()` + `test_client()` checks of every guard branch (non-prod on/off, prod with/without override, invalid persona, `noauto`).
- `tests/integration/test_autologin_persona.py` — new, DB-backed: default persona-less call is an exact regression, all 5 personas resolve to the correct role, invalid persona rejected, `noauto` reflected in rendered HTML.
- `tests/test_v6584431_production_hardening.py` — extended with 3 new contract checks (override flag wiring, persona allowlist is the only bootstrap path, logout anti-loop).

## Test evidence

- **New tests**: 6 (unit) + 8 (integration) + 3 (hardening contract) = 17 new assertions, all pass.
- **Targeted regression**: `test_local_8080_login_contract.py`, `test_internal_qa_login_contract.py`, `test_default_admin_password.py`, `test_permission_matrix.py`, `test_super_admin_system_console.py`, `test_employee_productivity*.py` (prior fix) — all pass, run against the isolated `compose.test.yml` stack.
- **Full regression**: `scripts/test/docker-test.sh` — **354 pytest + 88 Playwright specs, all pass**. First run showed 4 flaky specs (retried and passed) under host load from back-to-back docker builds that day; re-verified clean **48/48** with `--repeat-each=3` in isolation — confirmed pre-existing timing flakiness (a `page.goto` double-navigation race unrelated to any file this task touched), not a regression.
- **Live UI verification** (local sandbox, `127.0.0.1:18280`, `MESFLOW_ENV=local`, `71.0.0.221`):
  - `?persona=` unset → admin, 34 permissions, landed on `/app`.
  - `?persona=operator` → operator role, 8 permissions, "Quản trị" nav section correctly absent (screenshot confirms).
  - `?persona=viewer` → viewer role, 11 permissions.
  - `?persona=manager` → 32 permissions; `?persona=supervisor` → 17 permissions.
  - `?persona=root` (invalid) → `400 AUTO_LOGIN_INVALID_PERSONA`, no session created (`/api/auth/me` still `401` after).
  - `/login?noauto=1` → real form rendered, `data-test-auto-login="0"`, no auto-trigger (screenshot confirms).

## Commits (branch `agent/claude/autologin`, merged to `main`, fast-forward, pushed)

- `713613f` — `feat(auth): safe autologin for fast internal testing`
- `15fc39e` — `chore: bump version to 71.0.0.221 for autologin feature`
- `c27fe91` — `chore: pass MESFLOW_TEST_AUTO_LOGIN through to the local sandbox`

Build + full `release-local-qa.sh` gate: `QA_STATUS=PASS` for `71.0.0.221`
(evidence: `.worktrees/artifacts/qa/71.0.0.221/release-local/release-local-qa.json`
— note this landed under the workspace's shared `.worktrees/artifacts/`
tree, not the top-level `artifacts/`, since `release-local-qa.sh` ran
from a worktree; the digest it recorded is the one actually promoted
below). Since promoted to prodtest and demo — see "Promotion" below.

## Promotion (2026-09-04, same day, user-requested)

**`prod.mesflow.net:8299` (prodtest)**: `71.0.0.220` → `71.0.0.221` via
`scripts/deploy.sh prodtest`. One wrinkle: `release-local-qa.sh`'s build
step (`scripts/projectflow/build.sh`) is local-only and never pushes to
the registry, unlike `scripts/release-build.sh` — so the image
`deploy.sh` needed wasn't there yet. Fixed by pushing the exact
already-QA-verified local image (`docker tag` + `docker push`, no
rebuild) and re-running `deploy.sh` with an explicit `@sha256:...` ref;
the pushed digest matched the QA evidence's recorded digest exactly
(`sha256:2fb566aa...`), confirming it was the same artifact the test
gate passed, not a fresh build. `== DEPLOY PASS ==`, digest-exact,
`migration_changed: 0`. Verified live: `/api/system/version` →
`71.0.0.221`; `/login` still shows `data-test-auto-login="0"` (autologin
correctly stays off there — `MESFLOW_TEST_AUTO_LOGIN` was never set on
prodtest's `.env`, so nothing changed for existing users of that tier).

**`mesflow-demo-app`**: promoted `71.0.0.219` → `71.0.0.221`, then
`MESFLOW_TEST_AUTO_LOGIN=1` + `MESFLOW_TEST_AUTO_LOGIN_ALLOW_PRODUCTION=1`
turned on, per explicit follow-up requests. This container is a
standalone `docker run` (not compose-managed, no bind mounts for
`/data/tutorials`) — a plain recreate would have destroyed the 15
tutorial videos published earlier (they live only in its writable
layer), so each recreate followed: back up `/data/tutorials` to host →
confirm no DB migration needed (`git log` across the full
`71.0.0.219..71.0.0.221` range touches zero migration files; ran the
one-shot migration anyway, no-op as expected) → stop + rename the old
container (kept as `mesflow-demo-app-old-71.0.0.219`, not deleted —
rollback fallback) → `docker run` the new image with identical
env/ports/network/restart-policy plus the two new flags → restore the
tutorial videos.

Verified live on the real container:
- Boot log shows the intended warning: `SECURITY: MESFLOW_TEST_AUTO_LOGIN is ACTIVE on a MESFLOW_ENV=production deployment because MESFLOW_TEST_AUTO_LOGIN_ALLOW_PRODUCTION=1 is explicitly set...`
- `POST /api/auth/test-auto-login` with no persona → admin (unchanged default).
- `?persona=operator/viewer/manager/supervisor` → each resolves to the matching role (demo's DB already had all 5 persona-named seed accounts).
- `?persona=root` (invalid) → `400 AUTO_LOGIN_INVALID_PERSONA`.
- `/login?noauto=1` → `data-test-auto-login="0"`, real form, unaffected.
- `/api/tutorials` → still 15/15 items after the recreate; `/api/system/ready` → `ok:true`, `71.0.0.221`.

**Not promoted**: `/opt/mesflow` (the `mesflow-app` container, this
host's "prod test" tier per the prior task's investigation) still runs
`71.0.0.220` — not requested this round, left as-is.

## How to use (see `docs/AUTOLOGIN.md` for the full version)

Local/non-production:
```
MESFLOW_TEST_AUTO_LOGIN=1
MESFLOW_TEST_AUTO_LOGIN_USERNAME=admin
```
Open `/login?persona=operator` (or any of admin/manager/supervisor/viewer)
to quick-switch. `/login?noauto=1` always shows the real form.

Demo/prodtest (`MESFLOW_ENV=production` there too):
```
MESFLOW_TEST_AUTO_LOGIN=1
MESFLOW_TEST_AUTO_LOGIN_ALLOW_PRODUCTION=1
```
Real production must never set the override.

## Status of the prior (production-sync) task — not lost

Left exactly where the last session left it: `/opt/mesflow` carries the
correct 15-chapter tutorial set (backed up, verified), the
`docs/DEPLOY_ARCHITECTURE_A.md` root-cause correction is committed, and
the KPI fix (`71.0.0.220`) is live on `prod.mesflow.net:8299`. Real
public `mesflow.net` still needs the tunnel connector restarted on the
user's end before that work (and now this autologin feature, once
promoted) can reach it — no session state was lost switching to this
task; both are independently committed on `main`.
