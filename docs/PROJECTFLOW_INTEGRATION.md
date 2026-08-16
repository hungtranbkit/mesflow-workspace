# ProjectFlow integration

How ProjectFlow discovers, builds, deploys, tests and monitors MESFlow
without any MESFlow-specific hard-coded commands. See
`reports/PROJECTFLOW_STANDARDIZATION_ASSESSMENT.md` for the evidence this is
based on, and `reports/PROJECTFLOW_EXECUTION_STANDARD.md` for the executed
local validation run.

## Workspace structure

```
WORKSPACE.yaml                 root product manifest, lists all 4 projects
mesflow/PROJECT.yaml            MESFlow App        (WEB_APP)
deploy-agent/PROJECT.yaml       Deploy Agent       (SERVICE)
qa-center/PROJECT.yaml          QA Center          (SERVICE)
esp-kiosk/PROJECT.yaml          ESP32 Firmware     (FIRMWARE)
```

`server-agent/` has no manifest: it contains only an `AGENTS.md` rules file,
no source/build/test/deploy evidence. No `ai-loop`/`ai-reviewer` directory
exists in this repository. Both are correctly absent from `WORKSPACE.yaml`
per the evidence-only rule.

Each project keeps its own git repository and its own version file
(`VERSION.txt` / `VERSION`, or for firmware a `#define FW_VERSION` in
`esp/mesflow_app.cpp`). Build outputs for every project live under the
shared `artifacts/` directory **outside** every project's own source root
(`mesflow/AGENTS.md` Rule 8) — `PROJECT.yaml`'s `artifacts.directory` and
`artifacts.metadata` point there with a relative `../artifacts/...` path.

## How ProjectFlow discovers projects

1. Read `WORKSPACE.yaml` at the repository root → list of `{code, root,
   manifest}`.
2. For each entry, read `<root>/PROJECT.yaml` → `commands.*` gives the exact
   script to run for each logical action (preflight/build/test/smoke/
   local_deploy/local_stop/local_status/logs), always relative to
   `commands.<action>.working_directory`. ProjectFlow never constructs a
   docker/compose/pytest command itself.
3. `version.file` (or, for firmware, `version.source_define`) gives the
   current version without ProjectFlow parsing release notes or git tags.
4. `artifacts.metadata` gives a fixed-path JSON file with the identity of
   the most recent build (see below).

## Build action

`mesflow/scripts/projectflow/build.sh` is a thin wrapper: it calls the real,
pre-existing, immutable-once release builder
(`mesflow/scripts/build-release.sh`, same engine as the workspace-root
`scripts/build-release.sh` convenience wrapper) and then writes
`artifacts/latest/mesflow-app.json` — a ProjectFlow-shaped pointer to the
release the real engine just produced under
`artifacts/releases/<version>/`. It does not build a second time and does
not duplicate the Build Once / immutable-release-guard logic (a version can
only be built once; rebuilding a version that changed the Docker tag is
refused — see `docs/operations/BUILD_AND_PROMOTE.md`).

Deploy Agent and QA Center follow the identical pattern with their own
existing builders (`deploy-agent/scripts/build-agent-release.sh`,
`qa-center/scripts/build-release.sh`) — `PROJECT.yaml`'s `build` command
points straight at them; no ProjectFlow-specific wrapper was needed there.

## Local deploy action — and why it is a new isolated sandbox

**Critical finding from the scan** (full detail in
`reports/PROJECTFLOW_STANDARDIZATION_ASSESSMENT.md` §5): at
standardization time, this host was already running the real,
named deployment-target containers for all three server-side projects —
`mesflow-app`/`mesflow-postgres` (port 8080), `mesflow-qa-center` (port
8095) and `mesflow-deploy-agent` (port 8090) — plus an `mesflow-nginx`
container publicly bound on 80/443 with `server_name mesflow.net`. The
existing, documented "DEV LOCAL" path (`scripts/deploy-local.sh` at the
workspace root) drives that same live Deploy Agent.

Rather than gamble on whether this specific host's "DEV LOCAL" role is
safely separate from whatever is answering for `mesflow.net`, MESFlow App's
`local_deploy` action was implemented as a **structurally separate
sandbox**:

- `mesflow/compose.projectflow-local.yml` — standalone (not an override of
  `compose.yml`), compose project `mesflow-projectflow-local`, containers
  `mesflow-projectflow-local-{app,postgres}`, no `build:` block (can only run
  an already-built image — never rebuilds at deploy time), no external
  `mesflow-edge` network, own bind-mount directory
  `runtime-projectflow-local/` (gitignored), own port
  (`MESFLOW_LOCAL_PORT`, default `18280`).
- `mesflow/scripts/projectflow/{deploy-local,smoke,status-local,logs-local,
  stop-local}.sh` operate only on that compose project — they cannot name,
  address, or accidentally match the real containers.

This preserves the existing Build Once / Promote Same Artifact architecture
unmodified (nothing in `scripts/build-release.sh`, `scripts/deploy-local.sh`,
`scripts/promote-test.sh`, or the Deploy Agent itself was changed) while
giving ProjectFlow a deploy target it can run repeatedly and safely on any
host, regardless of that host's real-world role.

Deploy Agent's and QA Center's own `local_deploy` were left **disabled**
(`deployment.local.enabled: false`) in their `PROJECT.yaml` for the same
reason — their deployment-target composes also matched live containers
observed on this host. Building an equivalently isolated sandbox for them is
listed under Known limitations below.

## Test action

`mesflow/scripts/projectflow/test.sh` wraps the pre-existing, already fully
isolated `mesflow/scripts/test/docker-test.sh` (its own compose project
`mesflow-test`, its own Postgres on `tmpfs`, no host ports, self-cleaning
`trap ... down -v --remove-orphans`). Deploy Agent's `test` command wraps
`deploy-agent/scripts/test-baseline.sh` (its own `mktemp -d` sandbox).

## Health check / smoke

`service.healthcheck` in `mesflow/PROJECT.yaml` points at the sandbox's own
`/api/system/ready`. `smoke.sh` goes further than "container is running": it
checks `/api/system/health`, `/api/system/ready` (asserts the JSON `ready`/
`ok`/`status` field), `/api/system/version`, and that `/login` actually
renders.

## Artifact metadata

`artifacts/latest/<project>.json` (one file per project, to avoid the four
projects colliding on a single `artifacts/latest.json`): version, git
commit, image, image digest, schema revision, and the release ZIP path —
written by each project's `build` action immediately after its real
builder succeeds.

## Production guardrails

- `WORKSPACE.yaml`'s `production_policy` and every `PROJECT.yaml`'s
  `deployment.production` block declare
  `approval_required: true` / `projectflow_direct_execution: false`.
- Nothing this task added can reach the workspace-root `scripts/promote-test.sh`
  or the Deploy Agent's `promote-production` endpoint (which itself returns
  `501` — wiring only, see `docs/operations/BUILD_AND_PROMOTE.md`).
- The isolated sandbox's Postgres, secrets and admin credentials are
  hardcoded, obviously-local placeholder values (`mesflow-projectflow-local-*`)
  never sourced from any real `.env`.

## Known limitations / not standardized in this pass

- Deploy Agent and QA Center `local_deploy` are declared but disabled — an
  isolated sandbox for each (mirroring `compose.projectflow-local.yml`) is a
  follow-up, not executed in this pass because it doubles the scope for
  services that were secondary to MESFlow App's own validation.
- ESP32 firmware `build`/`test`/`package` are wired to existing scripts but
  were not executed in this pass (requires `arduino-cli` + a connected
  board for a real flash cycle; `flash_local` is explicitly out of scope for
  a headless worker).
- `server-agent/` remains without a `PROJECT.yaml` (no lifecycle evidence).
- A pre-existing test-infra defect was found and fixed while validating
  `test.sh` for real: `mesflow/Dockerfile.test` was missing
  `COPY gateway ./gateway`, so `tests/test_agent_nginx_contract_v6584412.py`
  failed to even collect. See `reports/PROJECTFLOW_EXECUTION_STANDARD.md`
  for the fix and the remaining (pre-existing, unrelated) test debt this
  uncovered.
