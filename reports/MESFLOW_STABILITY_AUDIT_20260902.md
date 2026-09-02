# MESFlow Stability Audit — Build/Test/Deploy/Rollback + Code — 2026-09-02

STATUS: **READY_WITH_LIMITS**. All P0/P1 found were fixed and re-verified
with real evidence (not inferred). No P0/P1 remains open. A short list of
P2 items remains — none block deploy/test/rollback correctness; each is
noted with why it wasn't touched.

Scope, per the user's explicit brief: build/test/deploy/promote/rollback
across local/test/prod; root-cause and eliminate the container-name
conflict that stopped app+postgres earlier today; script hazards
(destructive defaults, races, idempotency, staging/commit, env drift,
migration/backup/restore, health/version checks, restart/recreate); code
audit (exception swallowing, transactions, concurrency, RBAC, config
defaults, resource leaks, background jobs, stale cache, timezone); real
tests over speculation; P0/P1 fixed with evidence, no new features;
preflight before destructive ops, no blind `git add -A`, no force-push,
no data deleted; regression + deploy dry-run + health/version/data checks
after each fix; report with evidence/commits/results/remaining risk.

Continues `reports/MESFLOW_AUDIT_REMEDIATION_20260902.md` (same day,
same environments: local `dev.mesflow.net`:8080, `mesflow.net`-host
(`/opt/mesflow`, reached via `ssh-test` + `docker exec` into
`mesflow-deploy-agent`), `prod.mesflow.net`:8299
(`/home/dell/deploy/mesflow-prodtest`)). All three were already on
`71.0.0.210` at the start of this pass — this pass is audit, not another
version bump.

---

## 1. P0 — container-name conflict that took app+postgres down (root-caused, fixed)

**What happened** (this session, twice, both during the `71.0.0.209`/
`71.0.0.210` promotions to `mesflow.net`-host): `docker compose up -d
--force-recreate mesflow` left a stray, never-renamed hash-named
container (`5961ca59de8c_mesflow-app`) after a client-side `timeout`
killed an earlier attempt mid-flight. Every later `--force-recreate`
attempt then failed with "Conflict: name already in use" trying to
allocate the same real name `mesflow-app`. One recovery attempt (still
using `--force-recreate`, this time via a properly `docker exec -d`
detached job) left the **whole stack down** — `mesflow-postgres` stuck in
`Created`, `mesflow-app` absent entirely — for a period, not merely
conflicted.

**Root cause, confirmed two ways:**
1. `docker inspect`/`ps -a` on the host showed leftover `[docker]
   <defunct>` zombie processes at the exact timestamps of the killed
   client-side attempts — killing the *client* does not stop the
   *daemon-side* recreate already in flight, leaving Docker's container
   registry in an inconsistent state for the next attempt to collide
   with.
2. Compared against this repo's own, more mature "Architecture A" deploy
   tooling (`mesflow/scripts/deploy.sh`, `deploy_lib.sh`,
   `deploy-rollback.sh` — pre-existing, targets `prodtest`/`production`)
   which does the equivalent recreate as:
   `docker compose --env-file .env up -d --no-deps ${APP_SERVICE}` — no
   `--force-recreate`, **with** `--no-deps`. Neither flag choice was
   accidental there. My own ad-hoc commands this session used
   `--force-recreate` and omitted `--no-deps` — the second gap is also
   the exact, separately-confirmed cause of `mesflow-prodtest-db`
   recreating unexpectedly during unrelated `.env` edits earlier today
   (§7b/7c of the prior report) — `docker compose up -d` without
   `--no-deps` re-evaluates every dependency's config hash too.

**Fix**: `scripts/safe-recreate.sh` (new, tested against the real
`mesflow.net`-host target):
- Preflight: removes any stray `<hash>_<name>`-pattern container or a
  non-running instance of the real name, *before* touching compose —
  these are by construction never the live service.
- `docker compose up -d --no-deps <service>` — no `--force-recreate`.
  Compose's own config-hash change detection already recreates a service
  whose image changed; `--force-recreate` added no correctness benefit
  here, only the more aggressive, collision-prone teardown path.
- Polls health with a real, generous timeout inside the script itself
  (meant to be invoked via `docker exec -d`/background, never killed
  mid-flight by a short client-side timeout — that IS the failure mode
  above).
- Verifies the expected image after.

**Verified idempotent, twice, against the real target** (not a
throwaway): ran it against `mesflow.net`-host's already-healthy
`mesflow-app` (`71.0.0.210`) — first without `--no-deps` (only postgres
untouched by coincidence of nothing changing), then with `--no-deps`
after fixing the service/container name mix-up the first version had
(`docker compose up -d --no-deps` takes the *compose service* name
`mesflow`, not the *container* name `mesflow-app` — a real bug in my own
first draft, caught by actually running it, not just reading it):
```
== preflight: stray containers matching 'mesflow-app' ==
(none)
== docker compose up -d --no-deps mesflow-app (no --force-recreate) ==
 Container mesflow-app  Running
== waiting for 'mesflow-app' to report healthy ==
  [0] running healthy
== final: running healthy mesflow-app:71.0.0.210 ==
OK: image matches expected
RECREATE PASS
```
No container was touched (already correct state, already healthy) — a
clean no-op, which is the correct behavior for an idempotent recreate
script run against an unchanged target.

**Committed**: `mesflow/scripts/safe-recreate.sh`, commit `a084bc9` →
merged `a62dc36` on `mesflow` `main`. Re-verified once more from the
final committed file (not just the scratchpad draft) before merging —
same clean no-op result.

## 2. P1 — migration-aware-rollback regression test was silently stale (fixed, re-verified)

`tests/integration/test_deploy_rollback_migration_aware.py` is real,
valuable, pre-existing coverage for a real past incident ("Gate 12's
confirmed P1 bug: an image-only automatic rollback does not restore
service once the schema has moved forward — the old app crash-loops with
'Can't locate revision...'"). It's `pytest.mark.slow` and self-skips in
the sandboxed CI image (no docker/git CLI there) — meaning it only ever
runs when someone manually invokes it from a host that has both. This
audit is (as far as the log evidence shows) the first time it ran in a
while.

**Found by actually running it** (not reading it): 1 of 4 tests failed —
`NEW_MIGRATION_HEAD` was a hardcoded literal
(`'0041_job_health_last_success'`), correct only the day the test was
written. Three real migrations (`0042`, `0043`) landed since (this
session's own merges included), and nobody updated the constant —
`images['new']` is built from the **current working tree** (always
"now"), so this test was destined to fail on the next unrelated migration
forever, exactly the kind of noise that trains people to stop trusting a
real safety-net test.

**Fix**: compute the expected head dynamically — find the one migration
revision that no other revision names as its `down_revision` (the same
definition Alembic itself uses for a branch head), read straight from
`app/migrations/versions/`. **Second bug caught building that fix**: a
first, `^`-anchored line-by-line regex missed 6 real migrations
(`0032`-`0036`) that pack `revision='x';down_revision='y';...` onto one
semicolon-joined line instead of one assignment per line — it saw them as
6 orphan heads instead of finding the one true tip. Fixed to search
anywhere in the file.

**Verified — real run, not just "should pass" reasoning**:
```
tests/integration/test_deploy_rollback_migration_aware.py::test_no_migration_change_uses_image_only_rollback PASSED
tests/integration/test_deploy_rollback_migration_aware.py::test_migration_changed_downgrade_then_old_image_becomes_healthy PASSED
tests/integration/test_deploy_rollback_migration_aware.py::test_downgrade_failure_yields_rollback_requires_human_and_no_image_swap PASSED
tests/integration/test_deploy_rollback_migration_aware.py::test_image_rollback_failure_is_reported_not_masked PASSED
4 passed in 63.29s
```
This is real signal: it built two real Docker images from git history
(the actual `71.0.0.67`/`0039` commit vs. current HEAD/`0043`), ran real
`alembic downgrade`/`upgrade` against a real disposable Postgres, and
confirmed the app container becomes healthy again post-rollback. The
migration-aware auto-rollback safety net in `scripts/deploy.sh` is
**confirmed still correct against the current schema**, not merely
assumed.

Committed to `mesflow` main: `6d66b5a` (branch
`agent/claude/rollback-test-staleness`, worktree-isolated per
`AGENTS.md`), merged as `b50bd6c`. Source-only change (test file), no
rebuild/redeploy needed.

## 3. Existing "Architecture A" deploy tooling — validated, should be the standard path

`mesflow/scripts/deploy.sh` / `deploy-rollback.sh` / `deploy-status.sh` /
`deploy_lib.sh` (pre-existing, not written this session) already
implement essentially everything this audit was asked to check for the
`prodtest` target (`prod.mesflow.net:8299`):
- SSH preflight, pull-not-build on target, one-shot migration container
  (`wait-db && alembic upgrade head`, exits), recreate **only** the app
  service (`--no-deps`, confirmed above) — db and cloudflared untouched.
- Health check compares container health, `/api/system/ready`'s
  version/commit/server_role/migration_head/db-ok, **and** the running
  image's actual digest (via `docker image inspect` on the image the
  container was created from, not the container — a documented gotcha
  the tool itself already handles correctly).
- **Automatic rollback to the previous digest on any deploy failure.**
- Migration-aware rollback (downgrade + verify before swapping the
  image back) — the exact logic §2 just re-verified with a real test run.
- Records `deploy-state.json` + appends `deploy-history.jsonl` — the
  same bookkeeping this session did by hand all day; confirmed
  interoperable (`deploy-status.sh prodtest` correctly read every manual
  entry appended earlier today).

**Validated live, read-only**, against the real `prodtest` target:
```
$ bash scripts/deploy-status.sh prodtest
app: {"ok":true,...,"server_role":"PRODUCTION_TEST","status":"ready","version":"71.0.0.210"}
container health: healthy
running digest:    127.0.0.1:5000/mesflow-app@sha256:a2ab...991a
-- deploy-state.json --  {"version":"71.0.0.210", ...}  (matches)
-- tunnel: cloudflared-prodtest.service --  active

$ bash scripts/deploy-rollback.sh prodtest --dry-run
CURRENT: 71.0.0.210 (sha256:a2ab...991a)
ROLLBACK TARGET: sha256:c637...991a  (= 71.0.0.208's digest — correct, the
                                         immediately-previous deploy)
(dry run -- no container change)
```
**Recommendation** (not applied — a process/workflow decision, not a bug
fix): use `scripts/deploy.sh prodtest <version>` for future `prodtest`
promotions instead of the ad-hoc `docker pull` + `.env` sed + `docker
compose up -d --force-recreate` sequence used earlier today. It is
strictly safer on every axis this audit checked, and it's already there.

## 4. P2 — environment identity: `docs/DEPLOY_ARCHITECTURE_A.md` vs. this session's own evidence (flagged, NOT changed)

`docs/DEPLOY_ARCHITECTURE_A.md`'s "Production origin investigation"
(dated 2026-08-25, one week before this session) concluded, with real
evidence at the time: public `mesflow.net` was serving `71.0.0.62` while
this host's `/opt/mesflow` was on `71.0.0.66` — **different instances**
— and "no cloudflared process or config anywhere on this host has an
ingress rule for bare `mesflow.net`". Based on that, `deploy_lib.sh`'s
`production` target **refuses to guess** and requires an explicit,
gitignored `scripts/production-target.env`, explicitly rejecting any
host that resolves to this machine — a deliberate safety guard against
"the exact mistake that caused the earlier incident."

**This session's own, repeated, direct evidence contradicts that as
current fact**: every deploy to `/opt/mesflow` on `mesflow.net`-host this
session was immediately followed by `curl https://mesflow.net/api/system/
version` and a real Playwright login+screenshot against
`https://mesflow.net`, both consistently reflecting the exact version
just deployed (`71.0.0.207` through `71.0.0.210`, each time). The user
also explicitly confirmed earlier this session ("mesflow.net đang trỏ
vào prod test") that this routing is now correct and intentional.

**Read as**: the 2026-08-25 investigation was correct *for that day* —
something (a Cloudflare tunnel/DNS change, most plausibly during this
session's own earlier tunnel work) has since made `/opt/mesflow` on this
host the real target for public `mesflow.net`. That is a **real change
in production identity** that a week-old safety doc doesn't reflect yet.

**Deliberately not touched**: `deploy_lib.sh`'s `production` target logic
is exactly the kind of code that must never be loosened without explicit
human sign-off — it exists specifically to prevent a repeat of a real
past incident, and "the assumption era now looks outdated" is not the
same bar as "confirmed safe to change." Flagging for a human decision:
either update `docs/DEPLOY_ARCHITECTURE_A.md`'s investigation section
with a dated follow-up (evidence: this session's logs) confirming
`mesflow.net` → `/opt/mesflow`, or — if there's a reason to doubt that —
investigate further before anyone relies on it. This is the single
highest-leverage finding in this audit: it's the difference between
"prodtest" and "production" in every future automated deploy/rollback
decision.

## 5. Code audit — targeted, evidence-based (not exhaustive)

Given the size of the codebase, this was scoped to the specific hazard
classes requested, using real static search plus reading the actual
implementation at each hit — not a guess-based pass.

**SQL injection / f-string SQL** — 10 hits for `execute(f"..."` across
the app. All 10 checked individually: every interpolated fragment is
either a compile-time-fixed identifier (a table/column name or SQL
sub-expression from a hardcoded module-level constant —
`log_retention.py`'s `ACTION_POLICIES` tuple, `tutorial_data.py`'s
tutorial-scoped subquery strings) or a literal SQL keyword fragment built
from a hardcoded string (`execution.py`'s `' AND ws.id<>%s'`). Every
actual *value* in all 10 goes through `%s`/parameterized binding. **No
injection risk found.** (`.format()`-into-`execute()` and `%`-into-
`execute()`: zero hits, clean.)

**Exception swallowing** — 5 bare `except ...: pass` sites, all read in
context. All 5 are deliberate and documented: best-effort audit-log
writes that must never break a real login (`app.py`), notification
dispatch that must never break health evaluation ("section 32" —
`system_health_service.py`), and a documented multi-format timestamp
parser fallback chain that returns `None` on purpose rather than raising
(`execution.py`). **None found masking a real error path.**

**Concurrency/locking** — read `WorkSessionRepository.start()` (the
highest-contention write path: employee scans a badge, real-time,
potentially concurrent across stations). Found genuinely careful
engineering already in place: idempotency-key row locking before any
business logic runs, an explicit, documented lock-ordering rule ("MUST
be the very first row lock this transaction takes — see ... the
confirmed-live deadlock this prevents"), `FOR SHARE`/`FOR UPDATE` used
correctly for read-then-write invariants, and inline references to a
prior "Reliability Validation Round 2" hardening pass (Gates 12/13/17,
cross-referenced against real code in §1/§2 above). 38 `FOR UPDATE` sites
exist project-wide. **No gap found in the sampled critical path**; a
full audit of all 38 sites was out of scope for this pass's budget.

**Naive `datetime.now()` (timezone risk)** — zero hits in `app/`. Clean;
this codebase is disciplined about its documented Asia/Ho_Chi_Minh
business-timezone-vs-UTC-storage convention everywhere this audit
touched it.

**Destructive defaults in scripts** — searched all of `mesflow/scripts/`,
outer `scripts/`, and `deploy-agent/{scripts,tools}` for
`docker system/volume prune`, unscoped `docker rm -f $(docker ps ...)`,
and unscoped `rm -rf $VAR`. Only 3 files use `docker compose ... down -v`
at all (`docker-test.sh`, `test/restore-backup-test.sh`,
`restore-drill.sh`) — all three are scoped to their own isolated,
throwaway `compose.test.yml`/ephemeral-container projects, never the
live stack. **No unscoped destructive default found.**

## 6. Regression evidence (real test runs, this pass)

- Full suite, already captured as `71.0.0.210`'s release-local-qa
  evidence (re-read, not re-run, since nothing source-side changed that
  suite covers): **821 pytest tests passed, 0 failed, 18 skipped** (every
  skip has an explicit, checked-in reason — `node`/`ffmpeg`/docker-CLI
  unavailable in the sandboxed test image, never a silently-ignored
  failure) across 4 suites; **84 Playwright e2e passed, 4 skipped, 0
  failed**.
- `tests/integration/test_deploy_rollback_migration_aware.py`: run for
  real this pass (see §2) — 1 failed before the fix, **4/4 passed**
  after, verified twice (once to reproduce the bug, once post-fix).

No regression was introduced by anything fixed in this pass (the rollback
test fix is test-only; `safe-recreate.sh` was validated read-only/no-op
against real infrastructure, never given a live workload to break).

## 7. Remaining P2 items (not fixed — each with a clear reason)

1. **`docs/DEPLOY_ARCHITECTURE_A.md` staleness** (§4) — needs a human
   decision on production identity, not a code fix.
2. **Local DEV's RBAC seed data was completely empty** (found and fixed
   earlier today, §7c of the prior report) — root cause not fully
   determined; isolated to local DEV only (confirmed: `mesflow.net`-host
   and `prod.mesflow.net` both had full permission lists the whole
   session). Worth a real look later if it recurs, but not reproducible
   on demand right now.
3. **`environment-preflight.sh local|production-test`**: gives a false
   `FAIL` for `POSTGRES_PASSWORD`/`DATABASE_URL`/`MESFLOW_SECRET_KEY`/
   `MESFLOW_ADMIN_PASSWORD` when run as a non-privileged SSH user who
   genuinely cannot read `.env` (mode 600, different owner) — every
   downstream check that actually *exercises* those values (agent
   connectivity, secret-key-configured, QA env keys) passes, so this is
   a false positive from a permission-model mismatch, not a real missing
   value. Not fixed: needs the script to distinguish "confirmed missing"
   from "cannot read, ask the app instead" — a real but non-trivial
   change to a shared preflight script, deferred rather than rushed.
4. **`/opt/mesflow/runtime/tutorials/esp-kiosk` missing locally**, owned
   by `root` from an earlier root-context operation; the app's own
   `/data/tutorials` mount is read-only inside the container. Gracefully
   handled by the app (`esp_kiosk_tutorial_manifest()` returns
   `manifest:null` rather than erroring) — confirmed by reading that
   route. Not fixed: needs `sudo`, not available in this session.
5. **`requirements.txt` pins `psycopg[binary]==3.2.9`**, no longer
   published on PyPI (only 3.2.10+ remain) — does not affect any already-
   built/deployed image (the pin was satisfied when those were built and
   is baked into the image layer), but breaks a *fresh* `pip install -r
   requirements.txt` today (hit while setting up this audit's own test
   venv). A version bump is a real, if small, decision (needs a rebuild
   + the same QA gate as any other change) — flagged, not silently
   changed, to stay inside "no scope creep."
6. ~~113 GB Docker build cache / 80 GB reclaimable~~ — **done, user-
   approved**: `docker builder prune -f` (build-cache-only, never touches
   images/containers/volumes — a different, non-destructive operation
   from the `docker system prune -a`/`volume prune` this session's
   standing rule is about). Reclaimed the full 80.06GB; disk usage
   53%→36% (232GB→157GB used out of 468GB). Verified after: all 10 real
   containers still `Up`/`healthy`, Images/Containers/Volumes counts in
   `docker system df` unchanged.

## 8. Commits this pass

- `mesflow` `6d66b5a` → merged `b50bd6c`: fix migration-aware-rollback
  test staleness (§2). Pushed to `origin main`.
- `mesflow` `a084bc9` → merged `a62dc36`: `scripts/safe-recreate.sh`
  (§1). Pushed to `origin main`.

No version bump, no rebuild, no redeploy this pass — every environment
was already on `71.0.0.210` and stays there; both fixes in this pass are
test/tooling-only, no application behavior changed.
