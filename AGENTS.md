# MESFlow Multi-Project Workspace Rules

This workspace contains related MESFlow projects. Treat them as one system, but do not blur project boundaries.

## Permanent rules (workspace/deployment restructure)

See `docs/operations/SOURCE_OF_TRUTH.md`, `BUILD_AND_PROMOTE.md`,
`SERVER_LAYOUT.md`, `NEW_SERVER_INSTALL.md` for the full detail behind
each rule.

- **RULE 1 — Workspace is source-of-truth.** `/home/dell/workspace/mesflow`
  is the single editable source for MESFlow, Deploy Agent, QA Center and
  ESP Kiosk. `/opt` is deployed/runtime config only; `/var/lib` is
  persistent runtime data.
- **RULE 2 — Never develop directly under `/opt`.** If a fix was made in
  `/opt` under time pressure, treat it as an incident: diff it back against
  workspace, classify the change, and reconcile the real code change into
  workspace before trusting it long-term.
- **RULE 3 — Never reconcile `/opt` wholesale into workspace.** Only port
  specific, understood `REAL_CODE_CHANGE` diffs. Never blindly rsync or
  copy an entire `/opt` tree over the workspace.
- **RULE 4 — Build once on DEV.** Images are built only on the DEV host
  (`SERVER_ROLE=DEV`, `MESFLOW_BUILD_ENABLED=true`), from workspace source.
- **RULE 5 — Promote the same ZIP SHA and image digest.** A promotion never
  changes the artifact's bytes. Compare by digest/sha256, not by tag or
  version string alone — tags can be moved by a later rebuild under the
  same version, which is itself a bug to fix, not something to tolerate.
  Enforced in code: `mesflow/scripts/build-release.sh` refuses to build a
  version whose `artifacts/releases/<version>/` already exists, and refuses
  to retag `mesflow-app:<version>` onto different bytes; the Deploy Agent's
  `_release_contamination()` independently detects tag drift live and
  refuses to promote a contaminated release. A version may be built only
  once — 65.8.44.65 was contaminated exactly this way before the guard
  existed; it is marked `CONTAMINATED.json` and permanently retired, not
  rebuilt.
- **RULE 6 — Production Test and Production never rebuild.** They deploy
  `--no-build` from the frozen artifact only. Neither host should need
  MESFlow source, a build toolchain, Node, Arduino CLI, or a frontend
  source tree.
- **RULE 7 — Production mutation requires explicit human approval.** Every
  time, no exceptions, regardless of how many times LOCAL_PASS/TEST_PASS
  have already succeeded.
- **RULE 8 — Runtime/data/artifacts do not belong in the source
  repository.** No `runtime/`, `docker/runtime/`, database dumps, image
  `.tar` files, release ZIPs, `node_modules/`, `.venv/`, `__pycache__/`,
  `.pytest_cache/`, Playwright output, or large logs in `mesflow/`,
  `deploy-agent/`, `qa-center/`, or `esp-kiosk/` — enforced via each
  project's `.gitignore`.

## Projects

- `mesflow/` — MESFlow core backend/PostgreSQL application (Flask/Jinja
  Classic UI still lives here too, until retired per the migration plan).
- `mesflow-web/` — React/TypeScript frontend (Vite), developed in parallel
  with Classic UI against the same `/api/*` backend/database. Owns page
  layout/navigation/forms/tables/drawers/state; never accesses PostgreSQL
  directly and never reimplements backend business/RBAC/validation logic.
  See `reports/FRONTEND_SEPARATION_AUDIT.md`,
  `docs/architecture/FRONTEND_BACKEND_SEPARATION.md`.
- `deploy-agent/` — Deploy Agent used to upload, validate, deploy, verify and roll back MESFlow/QA releases.
- `qa-center/` — independent QA Center / realistic soak / regression runner.
- `esp-kiosk/` — ESP32-S3 kiosk firmware and device UI.
- `server-agent/` — optional server monitor / SSH / Docker / service health agent.
- `bootstrap/` — MESFlow Bootstrap / Recovery Console: small, independent
  host/systemd service (port 8098) for a brand-new Ubuntu server; prepares
  the minimum environment (OpenSSH, Docker) and installs/recovers the Deploy
  Agent only. See `bootstrap/AGENTS.md`, `reports/SERVER_BOOTSTRAP_RECOVERY.md`.
- `docs/` — architecture, operations, UI and test documentation.
- `artifacts/` — generated release ZIPs only; never production runtime data.
- `reports/` — review/test reports.
- `test-data/` — local-only fixtures/demo data.

## Global safety

Ubuntu/Linux is the primary development/test environment.

Never mutate production without explicit HUMAN APPROVAL.

The following always require HUMAN APPROVAL:
- production deploy
- production restart
- nginx cutover/reload affecting production
- PostgreSQL lifecycle changes
- production database migration
- systemd mutation
- firewall/network mutation
- reboot
- destructive Docker commands
- deleting real data

Never:
- copy production `.env`/secrets into the workspace
- commit passwords/tokens/certificates
- run `docker compose down -v`
- remove production Docker volumes
- DROP/TRUNCATE production tables
- force-delete production data
- claim PASS without evidence

## Project boundary rule

Before modifying code, identify which project owns the behavior.

Examples:
- business logic/API/database/auth/RBAC -> `mesflow/`
- React page layout/navigation/forms/drawers/frontend state (New UI) -> `mesflow-web/`
- Classic UI templates/static JS (until retired per migration plan) -> `mesflow/`
- upload/deploy/rollback/gateway installer -> `deploy-agent/`
- soak/regression/test orchestration -> `qa-center/`
- ESP screen/scanner/keypad/offline firmware -> `esp-kiosk/`
- host SSH/service/Docker monitoring -> `server-agent/`
- fresh-server prep + Deploy Agent install/recovery console -> `bootstrap/`

Do not fix a MESFlow bug by hiding it in QA or Deploy Agent.
Do not fix a firmware bug by weakening server validation.

## Deployed Source Reconciliation Rule

MESFlow code may arrive from multiple development flows, including ChatGPT-generated release ZIPs and Codex changes.

Approved releases are deployed through Deploy Agent into `/opt`.

Before any substantial task, do not assume the workspace is newer than deployed source.

Deployed locations:
- MESFlow Core: `/opt/mesflow` (config/runtime only, no app source)
- Deploy Agent: `/opt/mesflow-deploy-agent` (compose/config; persistent data in `/var/lib/mesflow-deploy-agent`)
- QA Center: `/opt/mesflow-qa-center`

Workspace locations:
- `mesflow/`
- `deploy-agent/`
- `qa-center/`

Rules:
- `/opt/...` is the currently deployed snapshot; workspace source is the integration/development source.
- Do not edit `/opt` directly for normal development.
- Reconciliation is read-only against `/opt`.
- Never blindly rsync `/opt` over the workspace.
- Never import `.env`, secrets, runtime data, DB files, certificates, logs, generated videos, node_modules, venvs, caches, or Docker state.
- Before a substantial task run `scripts/reconcile-from-opt.sh <project>` or `all`.
- Review the snapshot/diff before importing anything.
- Preserve workspace-only changes unless intentionally superseded.
- If there is a conflict, STOP and report it.
- Matching versions do not prove matching source.
- After reconciliation, test locally before preparing a release.
- Never production deploy automatically.

Short Codex instruction:
`sync deployed rồi làm tiếp`

Interpret it as:
1. reconcile the relevant project from `/opt`;
2. inspect version + source diff;
3. merge safely into workspace if needed;
4. only then perform the requested task.

## MESFlow Industrial UI Standard

The authoritative UI/UX rule set is:

`docs/ui/MESFLOW_UI_STANDARD.md`

Before any global or per-screen UI work:
- read that standard first
- audit before broad refactors
- do not copy Material/Carbon/Ant/Fluent literally
- use those systems only as references
- preserve MESFlow's own industrial/production identity

## MESFlow UI rules

Primary desktop target: 1920x1080 Full HD.

- Responsive for smaller screens.
- No horizontal overflow or overlapping text.
- Avoid very wide tables when master/detail is clearer.
- Long lists should have their own scrolling region.
- Keep useful context sticky while scrolling.
- Distinguish rows/cards/sections with hierarchy, borders, spacing and background.
- Do not make all progress bars/cards look identical.
- Time progress and product progress must be visually distinguishable.
- Use Vietnamese user-facing language wherever practical.
- Avoid developer enums/internal English terminology in normal user UI.
- Avoid unnecessary emoji.
- Do not change business logic only for visual convenience.
- Help/Tutorial should remain at the end of navigation.

## Session exception workflow

Treat Session Exceptions as an actionable queue:

1. Nhận xử lý.
2. Open the exact affected Session.
3. Review evidence.
4. Correct the real Session only when justified.
5. Save/recalculate.
6. Return to exception queue.
7. Hoàn tất or Bỏ qua with reason.

The page must clearly show:
- lỗi gì
- Session nào
- nhân viên/công đoạn nào
- cần làm gì tiếp theo

Do not make bulk-resolve the primary workflow.
Do not invent quantities/times/stations/evidence.

## MESFlow database / Alembic

- Avoid schema changes unless necessary.
- If needed, create Alembic migration with correct `down_revision`.
- Verify `alembic heads`.
- Preserve data.
- Do not rewrite user-customized production configuration.
- Default-normalization migrations must target recognizable untouched defaults only.
- Never run production migration without HUMAN APPROVAL.

## MESFlow version rules

Every modified deployable MESFlow ZIP must use a new version.

Synchronize where applicable:
- `VERSION.txt`
- Python `__version__`
- `release.json`
- Docker image tag in `compose.yml`

Do not package modified code under an old version.

## Deploy Agent rules

Deploy Agent must:
- validate ZIP structure/version
- validate compose before mutation
- build before cutover
- preserve persistent secrets/config
- verify deployed `/health` and `/version`
- roll back if expected version does not become healthy
- log each stage clearly
- never silently expose Agent/QA ports to Internet

Expected topology:
- Deploy Agent host access: usually `127.0.0.1:8090`
- public access through nginx/gateway
- Docker network `mesflow-edge` where configured

Upload UI must have a visible fallback action; never rely on only one fragile JavaScript auto-submit path.

## QA Center rules

QA Center is independent from MESFlow production code.

Prefer internal Docker URL:
`http://mesflow-app:8080`

QA must:
- use real auth unless the test explicitly targets auth bypass behavior
- preserve multi-day run state where designed
- pause/retry appropriately if MESFlow is temporarily unavailable
- never claim PASS without evidence
- keep test fixtures clearly identifiable and cleanable

## ESP Kiosk rules

Typical hardware:
- ESP32-S3
- ILI9341 2.8-inch display
- GM65 UART scanner
- 3x4 keypad through PCF8574 I2C
- I2C reference pins often SDA=16, SCL=15
- scanner UART configuration must be verified from the active firmware/hardware

Kiosk business flow:
- scan employee
- scan operation to start
- on finish: good quantity -> defect quantity -> optionally repairable defect
- not every finish has repairable defect
- shared kiosk returns to ready after starting a server Session
- offline mode may queue transactions and sync later

Arduino CLI / flashing rules:
- Ubuntu/Linux is the primary firmware build/flash environment.
- Codex may install/configure Arduino CLI, ESP32 core, required libraries, detect ports and compile.
- Never copy a single `.ino` out of a multi-file firmware project and build it separately.
- Before flashing, identify the exact connected board and serial port.
- Do not guess the partition scheme or board options.
- Do not erase flash unless explicitly requested.
- If multiple serial ports exist, do not choose one silently.
- Compile before every upload.
- Prefer an explicit project FQBN stored in `.mesflow-arduino.env`.
- `flash.sh` must require an explicit port argument.
- After upload, inspect the serial boot log and confirm the firmware/application version when possible.
- Firmware size/partition limits must be reported when compile output shows them.

## Build/test evidence

A UI change is not complete just because syntax/build passes.

When applicable verify:
- Python/JS syntax
- focused regression
- API behavior
- browser render
- browser console errors
- overflow/responsive behavior
- primary interaction flow

Migration work also requires:
- revision chain
- Alembic head
- local upgrade test
- data preservation
- schema/application health

Firmware work also requires:
- compile
- flash target/partition awareness
- size constraints
- pin mapping consistency

## Reporting

For every task state:
- project changed
- files changed
- behavior changed
- tests/evidence
- migration yes/no
- production action required yes/no
- known risks/not verified

## Image promotion wording

`deploy production test` means promote the exact artifact that passed LOCAL through
the Production Test Deploy Agent. It must use the frozen ZIP SHA and image digest;
never rebuild source on the test server.

`deploy production` means promote the exact artifact that passed Production Test
through the Production Deploy Agent. It requires explicit human approval, must
verify the frozen ZIP SHA, image digest and schema gate, and must never rebuild.

## Test server SSH

Test/staging server alias:

`mesflow-test`

Allowed:
- SSH into mesflow-test for diagnostics.
- Read Docker/service/application logs.
- Inspect Docker containers, networks, health and compose state.
- Inspect Deploy Agent state.
- Deploy to TEST through Deploy Agent when explicitly requested.
- Modify TEST-only files when required to diagnose/fix a confirmed issue.

Do not:
- Access production unless the task explicitly says production.
- Modify production data.
- Delete Docker volumes.
- Run destructive Docker commands.
- Run database DROP/TRUNCATE.
- Change firewall, nginx, systemd, database lifecycle or reboot without human approval.

Prefer:
1. Diagnose read-only.
2. Fix source locally.
3. Build/version a new release.
4. Deploy through Deploy Agent.
5. Verify health/version/logs.
6. Roll back if verification fails.

DEV LOCAL
= máy Ubuntu hiện tại
= Deploy Agent local
= dùng để build + deploy + smoke test trước

PRODUCTION TEST
= server test gần giống production
= KHÔNG phải production thật
= deploy bắt buộc qua Deploy Agent của server test
= dùng CHÍNH ZIP đã PASS ở DEV LOCAL
= không build lại source trên server test

PRODUCTION
= mesflow.net thật
= chỉ deploy khi HUMAN APPROVAL riêng
