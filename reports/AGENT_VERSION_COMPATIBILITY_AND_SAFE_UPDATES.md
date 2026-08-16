# Deploy Agent Version Compatibility + Safe Remote Updates

Implements and live-verifies capability-based Agent version compatibility
checking and a safe, no-SSH remote Agent update mechanism, per the
DEV (controller+builder) / PRODUCTION_TEST+PRODUCTION (receive/deploy/
status executor) architecture. Deploy Agent bumped to **2.19.0**.

## 1-2. Capability reporting + Target Agents table

`/health` and `/api/status` now report `api_protocol_version` (2) and
`capabilities` (`image_release_receive`, `digest_verify`, `remote_deploy`,
`deploy_status`, `health_status`, `agent_self_update`). `_agent_compatibility()`
classifies a target as `COMPATIBLE` / `UPDATE_AVAILABLE` / `INCOMPATIBLE` /
`OFFLINE` / `NOT_CONFIGURED` — **never** solely from a version-string
mismatch. A legacy Agent that predates capability reporting entirely (no
`capabilities` field at all — exactly what deploy.mesflow.net was before
this task) is `UPDATE_AVAILABLE`, not blocked, because it has already
been proven to work (see the prior session's TEST_PASS). Only a target
that explicitly reports capabilities and is missing a required one is
`INCOMPATIBLE`, with the exact missing capability named (matches the
task's example wording — verified by test).

New "Target Agents" table in the Release Manager UI (LOCAL / PRODUCTION
TEST / PRODUCTION), live-verified:

```
LOCAL:            2.19.0-docker-runtime · DEV · protocol 2 · COMPATIBLE
PRODUCTION TEST:  2.16.10-docker-runtime · latest 2.19.0-docker-runtime
                  · UPDATE_AVAILABLE (before the update below)
PRODUCTION:       NOT_CONFIGURED
```

## 10. Version compatibility gate before promotion

`_run_promote_test()` now checks the target's role/build-flag/capabilities
*before* uploading anything, refusing with `TARGET_AGENT_INCOMPATIBLE`
(naming the missing capability), `TARGET_AGENT_WRONG_ROLE`, or
`TARGET_AGENT_BUILD_ENABLED`. Covered by 9 new tests including the exact
scenarios requested: same-version compatible, older-but-capable allowed,
missing-capability blocked, wrong-role blocked, build-enabled-target
blocked.

## 3. Agent update artifact (build once on DEV)

`scripts/build-agent-release.sh` — same immutable-once guard as
`mesflow/scripts/build-release.sh` (refuses to rebuild an already-released
Agent version or retag an existing image id) — produces
`artifacts/deploy-agent/releases/<version>/AGENT_UPDATE_<version>.zip`
(image tar + `agent-release.json` manifest + `checksums.txt`). Agent
source is never copied to a target; only this artifact is.

**Real bug found and fixed while using this for the first time**: modern
Docker BuildKit embeds a build attestation in the image manifest by
default, so two separate `docker build` invocations of *byte-identical*
source (100% layer cache hits) produced two *different* image ids. The
immutable-once guard correctly caught this as `IMAGE_TAG_CONTAMINATED` —
but the underlying non-determinism would have made the guard unusable in
practice. Fixed by adding `--provenance=false --sbom=false` to the build
command; verified reproducible afterward (confirmed matching image id
using the same source across the actual build that produced the deployed
artifact).

## 4-9. Host-side updater (no SSH for normal updates)

`updater/updater.py`: a small, dependency-free (stdlib only) service,
entirely independent of the `mesflow-deploy-agent` container it manages.
Verifies checksums + image id, `docker load`s the new image, runs
`docker compose ... up -d --no-build --force-recreate mesflow-deploy-agent`
(scoped to that one service only — enforced by test assertion on every
command it issues), polls `/agent/health` for the expected version+role,
and automatically rolls back to the previously recorded image if health
never comes up. `updater/install-updater.sh` is the one SSH step (first
bootstrap only) and detects the target's current compose layout without
forcing a live restructuring.

`POST /api/release-manager/update-agent` on the DEV Agent pushes the
artifact to a target's updater over plain HTTP with a bearer token — no
SSH. Production requires `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` on this
Agent **and** an explicit `{"confirm": true}` on every call, matching the
existing Promote Production policy exactly.

## 12. Persistence

The updater only ever changes `AGENT_IMAGE` in an env file and recreates
one container; the data bind mount is untouched by container recreation.
Verified live (see below) and covered by `tests/test_updater.py`.

## 13. Live verification — real, on the real TEST host

**Infrastructure constraint hit and worked around**: `install-updater.sh`
needs root (systemd unit under `/etc/systemd/system/`, a fresh directory
under `/opt/`). SSH access to `mesflow-test` exists, but **no sudo
password / passwordless sudo is available** for the `codex` user — this
is a real, current limitation (see RESULT below), not something I
bypassed. To still deliver real, live evidence of the update *mechanism*
without root, I ran `updater.py` as a plain background process under
`codex`'s home directory (not `/opt`, not systemd — explicitly a
temporary bridge, not the final installation), pointed at the real
`/opt/mesflow-deploy-agent` target dir (which `codex` already owns).
Reaching its `127.0.0.1`-bound port from DEV (a different machine)
required a short-lived SSH tunnel purely as network transport for this
verification session — the update itself still went over plain HTTP with
bearer-token auth, not SSH; the tunnel was closed immediately after.

**Real update executed and verified**, via the actual
`POST /api/release-manager/update-agent` endpoint on the running DEV
Agent (not a hand-rolled script):

```
Before: mesflow-deploy-agent:2.16.10-docker-runtime (no capability reporting)
After:  mesflow-deploy-agent:2.19.0-docker-runtime
Image:  sha256:e75cc6a4... -> sha256:d79c9b3872d73edc7c429bd657a49eb13fd9445c9de8af2d6a71f18e717ca6ad
        (matches the artifact built by build-agent-release.sh exactly)
Elapsed: ~70s (docker load of a 193MB image + compose recreate + health poll)
```

Verified independently via `ssh mesflow-test docker ps` (read-only
diagnostic, not part of the update path):

```
mesflow-deploy-agent   mesflow-deploy-agent:2.19.0   Up 24 seconds (healthy)
mesflow-app            mesflow-app:65.8.44.69        Up About an hour (healthy)   <- untouched
mesflow-postgres       postgres:17-alpine             Up 45 hours (healthy)        <- untouched
mesflow-nginx          nginx:1.28-alpine               Up 3 days (healthy)          <- untouched
```

Data preservation verified by inspecting the actual persistent files
(`docker exec mesflow-deploy-agent ls -la /data/...`): `config/agent.json`
(admin password hash) dated **before** the update — proving it was not
regenerated; `data/state.json` (job history), `data/releases/`,
`data/mes_backups/` (16 entries), `data/qa_releases/`,
`data/esp_tutorial_uploads/`, `data/deploy_transaction.json` all present
with their pre-update timestamps. Confirmed functionally too: logged in
to `https://deploy.mesflow.net/agent` afterward with the **same**
pre-existing password — config was preserved, not reset.

## 14. Production

Not touched. `MESFLOW_PRODUCTION_AGENT_URL` was never set on the DEV
Agent; the Production row in the Target Agents table correctly shows
`NOT_CONFIGURED`.

## NEED_USER

**Root/sudo access on `mesflow-test`** is required to complete the
*permanent* installation (`/opt/mesflow-agent-updater/` +
`mesflow-agent-updater.service` via `install-updater.sh`, as specified).
Without it, the updater currently on that host is a temporary,
non-persistent bridge (a background process under `/home/codex/`, no
systemd, will not survive a reboot or process crash without manual
restart). The update *mechanism* is fully proven live; only the
*permanent, spec-compliant installation location and process supervision*
is blocked on this access. Please provide either a working sudo password
for the `codex` user on `mesflow-test`, or run
`sudo bash updater/install-updater.sh` there directly.

## Tests

```
deploy-agent pytest: 87/87 PASS (was 63/63 at the start of this task; 24
  new: 9 compatibility/gate tests, 8 updater artifact/update/rollback
  tests, 4 Target Agents/UI-render checks folded into existing files,
  3 pre-existing version-sync tests re-passing after the version bump)
python3 -m py_compile agent.py, updater/updater.py: OK
bash -n on build-agent-release.sh, install-updater.sh: OK
docker compose config -q: dev / production / production-test all VALID
Jinja template parse + node --check on both <script> blocks: OK
Real Flask test-client render of / (authenticated, with realistic Target
  Agents data): 200, table renders correctly
```

## RESULT

```
DEV AGENT VERSION: 2.19.0-docker-runtime
TEST AGENT VERSION BEFORE: 2.16.10-docker-runtime
TEST AGENT VERSION AFTER:  2.19.0-docker-runtime
PROD AGENT VERSION: not configured / no access

API PROTOCOL: 2
TEST COMPATIBILITY: COMPATIBLE (post-update; UPDATE_AVAILABLE before, never blocked)

AGENT UPDATE MODE: HTTP + bearer token, via POST /api/release-manager/update-agent
  -> target's updater /updater/update (real, executed live on the real TEST host)
SSH REQUIRED FOR NORMAL UPDATE: NO (SSH was used only for the one-time
  updater bootstrap on this host, per policy; the update itself used a
  short-lived local tunnel purely as this session's network path to a
  127.0.0.1-bound port, not as the update mechanism)

TEST AGENT HEALTH: healthy (verified via /agent/health and the live UI)
TEST BUILD ENABLED: false (verified before and after)
DATA PRESERVED: YES (config/state/releases/backups/qa/ESP-tutorial data
  all confirmed present with pre-update timestamps; login still works
  with the pre-existing password)
ROLLBACK VERIFIED: YES -- via tests/test_updater.py (real subprocess-call
  assertions: failed health check triggers restoration of the previous
  AGENT_IMAGE, verified rollback's own health re-check, verified the
  no-previous-image edge case reports ROLLBACK_FAILED rather than
  silently doing nothing). Not deliberately triggered against the live
  TEST host (judged not worth the risk to a real, shared host for this
  pass -- the state machine is proven by direct test, and the live pass
  went to SUCCESS on the first real attempt).

MESFLOW TOUCHED: NO (mesflow-app container uptime unchanged throughout)
POSTGRES TOUCHED: NO (mesflow-postgres container uptime unchanged throughout)

PRODUCTION TOUCHED: NO
```
