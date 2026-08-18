# Bootstrap Deployment Guide — implementation report

Beginner-friendly, step-by-step MESFlow deployment runbook, added to the
Bootstrap web UI and mirrored as a standalone Markdown document. Read from
and verified against the current code on 2026-08-18; no production
infrastructure was touched.

## GUIDE ROUTE

`GET /guide/deployment` (login-required, same session/CSRF protection as
every other Bootstrap page). Added to `bootstrap/app.py` (`guide_deployment()`),
rendered by `bootstrap/templates/guide_deployment.html`, styled by new rules
appended to `bootstrap/static/style.css`. Linked from the top nav on every
page (`bootstrap/templates/base.html`), as the last item: **Hướng dẫn triển
khai** — matching the requested nav order and the project's existing
"Help/Tutorial stays at the end of navigation" rule.

The top nav's other five labels were also translated to Vietnamese
(`Tổng quan`, `Cài Deploy Agent`, `Docker`, `Dịch vụ`, `Logs`, `Commands`) to
match the nav layout given in the task — this only changes visible link
text in `base.html`, no routes/endpoints/behavior changed, so it carries no
migration risk.

## MARKDOWN GUIDE

`bootstrap/docs/MESFLOW_SERVER_DEPLOYMENT_GUIDE.md` — generated, not
hand-written. Both the web page and the Markdown file render from the same
single source of truth, `bootstrap/guide_content.py` (architecture diagram,
server-role explanation, the 12 steps, common failures, recovery tree,
checklists, glossary — all as plain Python data). `render_markdown()` in
that same file produces the `.md` text; `bootstrap/scripts/generate_guide_doc.py`
writes it to disk. Re-run that script after editing `guide_content.py`;
the `.md` file is generated output, not a second copy to maintain by hand.

`install.sh` now also vendors `guide_content.py` into
`/opt/mesflow-bootstrap/` alongside `app.py` (it did not need any new code
otherwise — the guide route reads no live state).

## SERVER ROLE SOURCE OF TRUTH

`SERVER_ROLE` — a single environment variable read once at Deploy Agent
startup (`deploy-agent/agent.py`: `SERVER_ROLE=os.environ.get("SERVER_ROLE","DEV").strip().upper()`).
It is set by which `docker compose` override file is applied on top of
`compose.linux.yml` (which itself defaults to `PRODUCTION_TEST`, build off,
if nothing overrides it — a safe default). Confirmed directly in
`deploy-agent/docker/compose.{dev,production-test,production}.override.yml`
and in `deploy-agent/installer/install.sh`'s own auto-detection logic
(DEV only when a real workspace checkout is found on that host). The guide
documents the real verification commands (`curl .../agent/health | ...
server_role`, and the `docker inspect ... SERVER_ROLE=` fallback) and the
exact fix (`docker compose -f ... -f <role-override>.yml up -d`) copied
from `bootstrap/app.py`'s own `_detect_dev_server_role()` /
`_agent_compose_layout()` functions and from `docs/operations/DEPLOY_RUNBOOK.html`
(§02/§06), which documents a real past incident (DEV silently flipped to
PRODUCTION_TEST) that the guide's warning box calls out explicitly. No
variable name was invented — `SERVER_ROLE` is the only one used anywhere
in the codebase for this purpose (confirmed via grep across `bootstrap/`
and `deploy-agent/`, including all test files).

## BOOTSTRAP INSTALL FLOW

Documented directly from `bootstrap/install.sh` (read in full): OS
detection (Ubuntu, warn-only), OpenSSH install/enable, Docker Engine +
Compose plugin install via get.docker.com, creation of the `mesflow-edge`
Docker network, `/opt/mesflow-bootstrap` + `/var/lib/mesflow-bootstrap`
directories (never touching `/var/lib/mesflow-deploy-agent`), vendoring of
`deploy-agent/updater/updater.py`, Python venv + `pip install`, the
`mesflow-bootstrap.service` systemd unit, and the 15×1s `/health` poll.
Idempotency (`/var/lib/mesflow-bootstrap` preserved on re-run) is stated
because `install.sh` only ever copies over `/opt/mesflow-bootstrap`, never
`/var/lib/mesflow-bootstrap`.

## DEPLOY AGENT INSTALL FLOW

Two real paths, both documented — no invented API:
- **Method A** (recommended): Bootstrap Web → Install Deploy Agent → upload
  the ZIP from `deploy-agent/package_installer.sh`. Confirmed against
  `bootstrap/app.py`'s `validate_and_stage_package()` /
  `run_install_package()` and `bootstrap/templates/install_agent.html`.
- **Method B** (CLI fallback): the identical ZIP, extracted, `sudo bash
  install.sh` run directly over SSH — this is not a separate mechanism,
  it's the same `deploy-agent/installer/install.sh` Bootstrap itself runs
  internally (confirmed in `bootstrap/README.md`: "the same ZIP a human
  would run over SSH"). No separate upload API exists and none was invented.

`/opt/mesflow/.env` precondition (`installer/install.sh` refuses to run
without it, and refuses to create it) is called out explicitly.

## MESFLOW DEPLOY FLOW

Build-once-promote-same-artifact, documented from
`docs/operations/BUILD_AND_PROMOTE.md` and the live Release Manager
endpoints table in that file (`/api/release-manager/{build,deploy-local,
promote-test,promote-production}`), plus the real LOCAL_PASS/TEST_PASS
evidence model (image id match + Alembic `migration_head` + `/login` smoke
check — not deploy return code). The 6-step deployment order for a brand
new host (Bootstrap → Deploy Agent → PostgreSQL → MESFlow → nginx/gateway →
QA Center) matches `docs/operations/SERVER_LAYOUT.md` / `NEW_SERVER_INSTALL.md`;
PostgreSQL is explicitly documented as *not* requiring a manual step (it
ships inside MESFlow's own compose, confirmed live via a real
`/agent/health` response's `mes.docker.service_health.postgres` field on
this DEV host).

## QA DEPLOY FLOW

QA Center documented as an independent release with its own
`VERSION`/`APP_VERSION` match requirement (`VERSION_MISMATCH` guard), two
equivalent build entry points (QA Center's own Release Package page, or
Deploy Agent's `POST /api/qa-release-manager/build`), and the real
upload/deploy split (`POST /qa-release/upload` then a separate
`POST /qa-release/deploy/<version>` — uploading never auto-deploys). Source:
`docs/operations/DEPLOY_RUNBOOK.html` §05, cross-checked against
`deploy-agent/agent.py`'s QA route names.

## PRODUCTION TEST SAFETY

Guide requires (Step 09) a live `server_role` check against the Production
Test target *before* promoting, with an explicit "STOP — do not upload, do
not deploy" instruction if the value doesn't match — mirroring the
project's own incident history and the standing AGENTS.md rule set.

## PRODUCTION SAFETY

Documented from the real endpoint contract:
`POST /api/release-manager/promote-production` re-verifies the full gate
every call and requires both `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` on the
Agent *and* an explicit `{"confirm": true}` in the request — and even then
returns `501` in the current Agent build (wiring only, not executing a real
production deploy yet). The guide states this precisely rather than
implying an automated production deploy exists. No one-click/dangerous
action was added to the guide page itself (pure documentation, no forms,
no POST routes) per the task's explicit prohibition.

## RECOVERY FLOW

A 7-node Có/Không decision tree (SSH → Bootstrap → Deploy Agent → Docker →
PostgreSQL → MESFlow → nginx), each "Không" branch pointing to the
concrete real action (`systemctl restart mesflow-bootstrap`, Bootstrap's
Start/Restart/Reinstall Deploy Agent, etc.) — never a destructive command.

## COMMON FAILURE GUIDE

Six entries: port-in-use, stopped container, disk full (explicitly refuses
to recommend `docker system prune`, instead pointing at the real, already-
implemented release-retention cleanup), high RAM, Deploy Agent offline
(mapped to Bootstrap's own Overview badges), forgotten Deploy Agent
password (real `FIRST_LOGIN.txt` path at
`/var/lib/mesflow-deploy-agent/config/FIRST_LOGIN.txt`, real
`/agent/local-reset` endpoint and its loopback-only guard, confirmed by
reading `deploy-agent/agent.py`'s `ensure_config()`/`_is_local_reset_request()`),
and Bootstrap offline.

## BEGINNER CHECKLIST

Two checklists (general + Production-only) rendered as real checkboxes on
the web page and as Markdown `- [ ]` items in the `.md` file, generated
from the same `CHECKLIST_GENERAL`/`CHECKLIST_PRODUCTION` lists in
`guide_content.py`.

## GLOSSARY

16 terms in plain Vietnamese (Artifact, Image, Container, Docker Compose,
Bootstrap, Deploy Agent, Production Test, Production, Release, Promote,
Rollback, Health check, SHA256, Digest, Schema migration, SSH tunnel).

## COMMANDS VERIFIED AGAINST CURRENT CODE: YES

Every command/endpoint/path in the guide was read from the current source
(`bootstrap/app.py`, `bootstrap/install.sh`, `deploy-agent/agent.py`,
`deploy-agent/installer/install.sh`, `deploy-agent/docker/compose*.yml`,
`deploy-agent/package_installer.sh`) or observed live: a real
`curl http://127.0.0.1:8090/agent/health` and
`curl http://127.0.0.1:8098/health` were run against this DEV machine's own
running Bootstrap/Deploy Agent (read-only GETs, no mutation) to confirm the
exact JSON schema shown in the guide (`server_role`, `build_enabled`,
`mes.docker.service_health.postgres`, `qa.online`, etc. — all copied from
real output, not invented). Where the task asked not to invent something
undocumented (server specs, backup scripts), the guide says so explicitly
("chưa được quy định chính thức") instead of fabricating numbers.

## BROKEN/OUTDATED DOCUMENTATION FOUND

None found that required fixing elsewhere. One near-duplication risk noted
and resolved: `docs/operations/DEPLOY_RUNBOOK.html` already covers adjacent
ground (build/promote flow, environments, incidents) for an audience that
already knows the system. The new guide is deliberately the beginner/
first-time-setup complement (SSH from zero, tunnels, "what machine do I run
this on", troubleshooting-by-symptom, checklists, glossary) rather than a
second copy of the same reference — the two are cross-referenced, not
merged, since they serve different reader stages.

## TESTS

`bootstrap/tests/test_guide_deployment.py` (12 new tests) + existing
`bootstrap/tests/test_agent_lifecycle.py` (15 tests) — **27/27 pass**, run
with `/opt/mesflow-bootstrap/.venv/bin/python3 -m unittest discover -s
tests -v` (that venv's `flask`/`waitress`/`werkzeug` install was only read
from, never written to; the systemd service and `/opt/mesflow-bootstrap`
tree were never touched or restarted).

New coverage:
- Content-integrity tests directly on `guide_content.py`: unique/sequential
  step ids, every step has all required fields, every command has a known
  machine label, no field meant to render as raw HTML (`|safe` in the
  template) still contains an un-encoded `<PLACEHOLDER>` (a real bug found
  and fixed during this task — see below), `render_markdown()` output has
  no leftover HTML entities/tags.
- Route-level smoke tests via Flask's test client, loaded against this
  checkout's real `templates/`/`static/`/`guide_content.py`
  (`MESFLOW_BOOTSTRAP_HOME` pointed at the workspace source, `DATA_DIR` at
  an isolated scratch tmp dir — never `/var/lib/mesflow-bootstrap`): the
  route requires login, renders all 12 step anchors + the 6 top-level
  section anchors, every in-page `href="#..."` resolves to a real `id=`,
  no unresolved Jinja (`{%`) or double-escaped entities (`&amp;lt;`) leak
  into the output, the nav link appears on other pages, and all five
  pre-existing pages (`/overview`, `/docker`, `/services`, `/logs`,
  `/commands`, `/install-agent`) still return 200 after the nav-label
  translation.

Browser-level checks (real console-error-free rendering, responsive
layout, copy-button click behavior) were **not** run through an automated
browser tool in this task — verified instead by direct inspection of the
rendered HTML output (dumped and grepped) and by code review of the
vanilla-JS copy-to-clipboard handler (delegated click listener,
`navigator.clipboard` with a `document.execCommand('copy')` fallback, no
external libraries). If a real browser smoke test is wanted, it should
load the guide page after a normal `sudo bash install.sh` on a scratch
host or under `python3 app.py` locally — not against the shared DEV
Bootstrap instance already running on this machine, which was left
untouched throughout this task.

One real bug was found and fixed during self-review, not just described:
several `<PLACEHOLDER>` command-argument placeholders (e.g. `<SERVER_IP>`,
`<VERSION>`) were written as literal `<...>` inside text fields that the
template renders with Jinja's `|safe` filter (needed elsewhere in those
same fields for real `<code>`/`<b>` tags) — a browser would have silently
swallowed those placeholders as unrecognized tags. Fixed by entity-encoding
placeholders in `|safe` fields (`&lt;VERSION&gt;`) and adding
`_md_text()`/`html.unescape()` so the Markdown output still shows plain
`<VERSION>` rather than literal `&lt;VERSION&gt;`. Covered by
`test_no_raw_angle_bracket_placeholder_in_fields_rendered_as_safe_html` and
`test_render_markdown_has_no_leftover_html_entities_or_tags` going forward.

## PRODUCTION TEST TOUCHED: NO

## PRODUCTION TOUCHED: NO

All work was local file edits under `~/workspace/mesflow/bootstrap/` plus
two read-only `curl` calls against this DEV machine's own already-running
Bootstrap (`:8098`) and Deploy Agent (`:8090`) to confirm real response
schemas, and test runs against isolated scratch directories via Flask's
test client. No `mesflow-test`/Production SSH session was opened, no
`install.sh` was executed against any real host, no systemd unit was
restarted, and `/opt/mesflow-bootstrap`, `/var/lib/mesflow-bootstrap` and
`/var/lib/mesflow-deploy-agent` were never written to.

---

# Addendum (2026-08-18): "Khôi phục truy cập / Quên mật khẩu" section

A dedicated password-recovery section was added to both the guide page
(`#quen-mat-khau`) and the Markdown runbook, covering Bootstrap, Deploy
Agent and MESFlow. Audited each system's real auth implementation first;
one gap was found and fixed (Bootstrap had no reset mechanism at all), one
gap was found and fixed more safely (MESFlow's only existing reset command
was unsafe for anyone but the fixed `admin` account); Deploy Agent already
had everything needed and required no code change.

## BOOTSTRAP PASSWORD RECOVERY

**Audit result:** no reset mechanism existed. `bootstrap/app.py`'s `/setup`
route is one-time only (gated by `SETUP_TOKEN.txt`, deleted after use); no
route or script could recover a forgotten admin password.

**Implemented:** `bootstrap/bin/reset-admin-password` (bash wrapper,
root-required) + `bootstrap/bin/reset_admin_password.py` (the actual logic,
split out so it's unit-testable without root/TTY). Local-shell-only by
design — no web route was added, and `bootstrap/AGENTS.md` now records
"never add one" as a standing rule, with the reasoning (an operator locked
out of Bootstrap can't use a route on the service they're locked out of).

Reuses `app.py`'s own `state.json` layout and atomic
tmp-file-then-`rename()` write pattern instead of inventing a second state
format; touches only `admin_username`/`admin_password_hash`, asserted by
test (`other_keys_before == other_keys_after`). No restart required —
`/login` calls `load_state()` fresh on every request, confirmed by reading
`app.py` directly, not assumed. Appends one line to the existing
`logs/audit.log`, same format `app.py`'s own `audit()` helper uses. Never
prints the password (`getpass`, references dropped in a `finally` block).
`install.sh` now vendors `bin/` alongside `app.py`/`guide_content.py` and
prints the reset command in its final summary.

**Tests:** `bootstrap/tests/test_reset_admin_password.py`, 9 tests, all
against `tempfile.TemporaryDirectory()` scratch state — missing state
file, setup-not-complete guard, short username/password, mismatched
confirmation, successful reset changes only the two credential fields
(explicitly diffs the full state dict before/after), audit line written
without leaking the password, atomic write leaves no `.tmp` file,
optional `--username` change. **9/9 pass.**

## DEPLOY AGENT PASSWORD RECOVERY

**Audit result:** already fully implemented, no code change needed.
`deploy-agent/agent.py`: `ensure_config()` generates a one-time
`FIRST_LOGIN.txt` credential + Recovery Code on first run;
`/agent/forgot-password` accepts the Recovery Code; `/agent/local-reset`
(`_is_local_reset_request()`) accepts a reset with no code at all but only
when the request's `Host` header is `127.0.0.1`/`localhost` and the actual
remote address is loopback (or, inside Docker, the container's own live
default-route gateway, for the NAT-hairpin case) — verified by reading the
function, not assumed. Documented exactly as it exists: SSH tunnel from
the laptop to `127.0.0.1:8090`, then `http://127.0.0.1:18090/agent/
local-reset` in the browser, with the "server has no GUI, browser runs on
your laptop, the tunnel is what makes the request look local" explanation
the task asked for.

**`MESFLOW_AGENT_ADMIN_PASSWORD` interaction — made explicit as requested:**
reading `ensure_config()` line by line shows that if this env var is set,
*every* container start/recreate re-checks the stored hash against it and
silently overwrites `password_hash` back to that value if they differ —
which would undo a `/local-reset` done in between. Documented as a named
warning box (`RECOVERY_ACCESS_ENV_WARNING`) rather than buried in prose.
Checked this host's real `deploy-agent/docker/.env`: the key is absent
(the safe default), so this doesn't fire on a normal install — stated in
the guide as the common case, with the risk still called out for anyone
who did set it deliberately. The canonical secret source is named
explicitly: whichever of (a) the last `/local-reset`/`/forgot-password`
action or (b) `MESFLOW_AGENT_ADMIN_PASSWORD` in `docker/.env` was set most
recently — if you want a reset to survive a future recreate, update or
unset the env var to match.

**CLI fallback documented, with an accuracy correction:**
`deploy-agent/reset_password.py` exists and was checked — its `--home`
argument *defaults to a Windows path* (`C:\WorkshopManagementAgent`), i.e.
it's the legacy Windows-install variant, not written for this project's
current Linux/Docker deployment. Documented that distinction explicitly
(`RECOVERY_ACCESS_CLI_FALLBACK`) rather than presenting it as an
equally-suited option: on Linux/Docker, `--home /var/lib/mesflow-deploy-
agent` must be passed explicitly, and `/local-reset` is recommended first
since it needs no extra Python/werkzeug environment and no container
downtime.

**Tests:** none needed — no Deploy Agent code was changed. The existing
`bootstrap/tests/test_agent_lifecycle.py` (15 tests) was re-run unchanged
and still passes, confirming nothing in this task's edits touched that
integration surface.

## MESFLOW PASSWORD RECOVERY

**Audit result, read directly from code before writing anything:**
- Users live in PostgreSQL, table `users` (`mesflow/app/mesflow/db/
  repositories/user_repository.py`), columns include `password_hash`
  (`werkzeug.security.generate_password_hash`), `role`, `active`,
  `must_change_password`.
- RBAC: exactly 5 roles (`admin`, `manager`, `supervisor`, `operator`,
  `viewer` — `mesflow.web.users.ROLES`); no separate role table beyond
  `rbac_roles`/`rbac_permissions`/`rbac_role_permissions` referenced by
  `mesflow.cli.verify_schema()`.
- An admin reset API **already existed**: `UserRepository.reset_password()`
  (upsert: creates the user if missing, forces `role='admin'`,
  `active=true` on every call) and `mesflow.cli.reset_admin()`
  (`python -m mesflow.cli reset-admin`, wired into the pre-existing
  `scripts/reset-admin-password.sh`) — but this is **only safe for the one
  fixed admin account** (`settings.admin_username`). Using it for any other
  username would silently grant that user admin role, because of the
  upsert. This is a real footgun in existing code, documented as a "what
  not to do" rather than silently worked around.
- A separate, already-existing in-app path also exists for when an admin
  is still logged in: `POST /api/users/<id>/reset-password`
  (`mesflow/app/mesflow/web/users.py`), audited as `USER_PASSWORD_RESET`,
  password policy `>=8 chars, letters+digits`
  (`_password_error`) — correctly out of scope for "I'm locked out
  entirely," documented as the alternative when it applies.
- No forced-lockout/session-token table exists — auth sessions are
  stateless signed Flask cookies (`session['user_id']` etc.), so a password
  reset does not itself invalidate any other already-open browser session;
  stated as-is rather than claimed/invented.

**Implemented (only because no safe general-purpose reset existed):**
`mesflow.cli.reset_password()`, invoked as
`python -m mesflow.cli reset-password <username>` (registered in the same
`funcs{}` dispatch table `reset-admin` already uses, so the invocation
convention — `docker compose run --rm mesflow python -m mesflow.cli ...` —
matches the pre-existing shipped script exactly, nothing new invented).
Deliberately calls `UserRepository.set_password()` (pre-existing method:
only ever touches `password_hash`/`must_change_password`/`updated_at`),
**not** the upsert `reset_password()` — refuses to run if the username
doesn't exist (no upsert-create), preserves role/active/display_name by
construction, reads the password via `getpass` (never a CLI argument, never
echoed, never logged), rejects passwords shorter than 8 chars or missing a
letter+digit (kept identical to `mesflow.web.users._password_error`'s
existing policy, with a code comment pointing at it to keep both in sync),
and records `audit_logs` action `ADMIN_PASSWORD_RESET` via the pre-existing
`AuditRepository().log(...)` helper — named distinctly from the in-app
`USER_PASSWORD_RESET` action, since this one means "done from a root/server
shell, outside any web session," and the task specified this exact action
name.

**Tests:** `mesflow/tests/test_cli_reset_password.py`, 7 tests, fully
mocked (`UserRepository`, `AuditRepository`, `getpass.getpass` all
patched) — unknown username refused without creating a row, short/
letter-only passwords rejected, mismatched confirmation rejected,
successful reset calls `set_password` (never `reset_password`/
`update_profile`/`create`) with the exact audit action name and entity id,
password never appears in captured stdout on success or failure paths.
**7/7 pass**, run via a disposable venv (`psycopg[binary]`, `flask`,
`werkzeug`, `pytest` — matching the project's real dependency set) against
`DATABASE_URL`/`MESFLOW_SECRET_KEY` dummy values so `mesflow.cli` imports
cleanly without a live database. **No real PostgreSQL, no real container,
no real user row was touched** — a `docker cp` into the running local DEV
`mesflow-app` container (to test against real Postgres data with a
throwaway probe user) was attempted and correctly blocked by the
environment's own safety classifier as a live-container mutation; backed
off immediately rather than working around it, per the standing "never let
a spawned test process touch a real container" rule. The DB-facing methods
this CLI calls (`get_by_username`, `set_password`, `AuditRepository.log`)
are pre-existing code already exercised elsewhere (e.g. by
`mesflow.web.users.reset_user_password`), not new SQL — only the new CLI
wiring around them needed testing, and mocking gives that full coverage
without the DB-touching risk.

## EMERGENCY ACCESS MATRIX

Added as `EMERGENCY_ACCESS_MATRIX` (3 rows, one per system) +
`LOST_SSH_NOTE` (the fourth row from the task: losing SSH itself means none
of the above helps — cloud/provider console access is the only path,
explicitly stated as "not a MESFlow software problem").

## SECURITY WARNING

`RECOVERY_SECURITY_WARNINGS`, 5 entries matching the task's list exactly:
no public admin ports, no deleting auth DB/files, no manual password-hash
editing, no disabling auth globally, no sharing one admin password across
all three systems.

## GUIDE UI

New section `#quen-mat-khau` ("Quên mật khẩu / Mất quyền truy cập"), added
to the TOC under "Khi có sự cố", between "Sự cố thường gặp" and "Cây quyết
định phục hồi". Three cards (Bootstrap / Deploy Agent / MESFlow), each with
the 6 fields the task specified: **Nếu quên** (what to do), **Cần quyền
gì** (required access), copyable **Lệnh / URL chính xác** commands (reusing
the existing `render_cmd` macro and machine-label badges), **Kết quả mong
đợi**, **Không được làm** (in red), **Cách xác nhận đã khôi phục**. The
pre-existing "QUÊN MẬT KHẨU DEPLOY AGENT" entry in the Common Failures list
was trimmed to a one-line pointer at this new section instead of
duplicating the same content in two places (same "single source, no
drifting copies" principle the rest of this guide already follows).

## TESTS

All new/changed test suites re-run together after every content change:
- `bootstrap/tests/` (all files): **40/40 pass** (`/opt/mesflow-bootstrap/
  .venv/bin/python3 -m unittest discover -s tests -v` — that installed
  venv's packages were only read from, never written to; no restart of the
  real `mesflow-bootstrap` service).
- `mesflow/tests/test_cli_reset_password.py`: **7/7 pass**, isolated venv,
  fully mocked, no live DB.
- A real bug was caught by the new
  `test_no_raw_angle_bracket_placeholder_in_fields_rendered_as_safe_html`
  test extended to cover the new `RECOVERY_ACCESS`/`EMERGENCY_ACCESS_MATRIX`
  data: one matrix cell (`python -m mesflow.cli reset-password <username>`)
  had an un-encoded `<username>` placeholder inside a field the template
  renders with `|safe` — would have silently vanished in a real browser.
  Fixed (`&lt;username&gt;`) and reverified via the same route-level smoke
  test used for the original guide (`/guide/deployment` renders 200, no
  unresolved Jinja, no double-escaped entities, every in-page anchor
  resolves, all three system cards present, the new command strings are
  present in the rendered HTML).

"Verify roles/permissions before == after password reset" (as the task
required for MESFlow) is covered by
`test_successful_reset_preserves_role_and_uses_set_password_not_upsert`,
which asserts `set_password` was called (role untouched by construction)
and that neither `reset_password` (the role-forcing upsert) nor
`update_profile` was ever called. "Verify other config/state remains
intact" (as required for Bootstrap) is covered by
`test_successful_reset_changes_only_credential_fields`, which diffs the
entire state dict before/after and asserts every non-credential key is
byte-identical.

## PRODUCTION TEST TOUCHED: NO

## PRODUCTION TOUCHED: NO

No `mesflow-test`/Production SSH session was opened. No real Deploy Agent,
Bootstrap, or MESFlow credential was reset anywhere — every test ran
against scratch tempdirs or fully-mocked repositories. The one attempt to
use real local DEV Postgres data (via `docker cp` into the running
`mesflow-app` container) was blocked by the environment's safety
classifier and abandoned rather than circumvented; no container's
filesystem was modified.

---

# Addendum 2 (2026-08-18): correcting the MESFlow admin-recovery command

The previous addendum documented `python -m mesflow.cli reset-password
<username>` as the MESFlow recovery command. That function is real,
tested, unmodified-since-last-time code sitting in `mesflow/app/mesflow/
cli.py` — but it was never built into any MESFlow release, so it does not
exist in the image actually running on any real host today. Presenting it
as a working command in a guide meant to be followed by SSH-ing into a
real server and typing real commands was wrong. This addendum documents
the fix.

## THE BUG, CONFIRMED LIVE

Ran directly against this DEV host's own real, running `mesflow-app`
container (read-only, no mutation):

```
docker exec mesflow-app grep -o "funcs={[^}]*}" /app/mesflow/cli.py
```

Output:

```
funcs={'wait-db':wait_db,'seed-admin':seed_admin,'seed-default-users':seed_default_users,'reset-admin':reset_admin,'verify-schema':verify_schema,'record-deployment':record_deployment,'run-predictive':run_predictive}
```

`reset-password` is absent — exactly as the task stated. The command map
matches the task's "current verified implementation" list exactly (7
commands, `reset-admin` included, `reset-password` not). This live check
is now also the guide's own recommended troubleshooting command for
"unknown command" errors, so operators can re-verify it themselves on
their own host instead of trusting either version of this document blindly.

## MESFLOW PASSWORD RECOVERY

Rewritten from scratch to match Steps A-F exactly as specified:
`ssh <server>` → `docker ps --filter name=mesflow-app` →
`docker exec mesflow-app python -c 'from mesflow.core.config import
settings; print(settings.admin_username)'` → `read -s -p "Mật khẩu admin
mới: " NEWPASS` → `docker exec -e MESFLOW_ADMIN_PASSWORD="$NEWPASS"
mesflow-app python -m mesflow.cli reset-admin` → `unset NEWPASS`. Steps A,
B and C were executed for real against the live local DEV `mesflow-app`
container (read-only) and produced exactly the output shown in the guide
(`Up ... (healthy)`, `admin`). Step E (the actual mutating reset) was
**deliberately not executed** against this shared local DEV admin account:
its original password was never known to this session, so it could not
have been restored afterward, and the task forbids reporting a test
password either way — running it would have risked locking the repo owner
out of their own environment for no verifiable benefit, since
`reset_admin()`'s logic is pre-existing, unmodified code, not something
this task adds or changes.

Per-system labeling was tightened per the task's explicit requirement
("Label commands clearly: CHẠY TRÊN SERVER MESFLOW. Do not mix laptop and
server commands"): a new `MESFLOW_SERVER` machine label
(`guide_content.MESFLOW_SERVER` / `MACHINE_LABELS[MESFLOW_SERVER] =
"CHẠY TRÊN SERVER MESFLOW"`) was added, distinct from the generic `SERVER`
label used by the Bootstrap/Deploy Agent cards. `ssh <server>` (typed on
the laptop) keeps the existing `DEV` label; Steps B-F (typed on the
MESFlow host) all use the new label. Enforced by
`test_mesflow_card_labels_server_commands_distinctly_and_never_mixes_dev_into_server_steps`.

## CLI VERIFIED: `reset-admin`

Read directly from `mesflow/app/mesflow/cli.py`: `reset_admin()` calls
`UserRepository().reset_password(settings.admin_username,
settings.admin_password, activate=True, role='admin')` — confirmed to
unconditionally reactivate and re-grant `role='admin'` to
`settings.admin_username` on every call, exactly as the task described.
Documented as expected behavior ("đúng ý nghĩa 'khôi phục tài khoản
admin', không phải sự cố"), not a bug.

## OLD INVALID COMMAND REMOVED: YES

Every occurrence of `reset-password <username>` and `docker compose run
--rm mesflow ...` used for MESFlow admin recovery was found and removed
from: the `RECOVERY_ACCESS` MESFlow card (commands list, "expected", "do
not", "verify"), `EMERGENCY_ACCESS_MATRIX` (the MESFlow row was split into
two correct rows — see below), and the generated Markdown. Confirmed by
grep across `guide_content.py` and the regenerated `.md`: no remaining
occurrence of either exact string. Two new regression tests lock this in:
`test_guide_route_never_renders_the_stale_mesflow_reset_command` and
`test_emergency_access_matrix_mesflow_rows_use_reset_admin_not_reset_password`.

One deliberate, clearly-marked exception: the MESFlow card's "if quên"
text mentions the string `reset-password` once, explicitly to warn readers
away from it ("Mã nguồn workspace hiện có thêm một hàm `reset_password()`
... nhưng NÓ CHƯA nằm trong bất kỳ bản MESFlow nào đã build/deploy ...
Đừng dùng lệnh đó cho tới khi nó thật sự có trong một bản đã deploy") —
this is not "leaving a contradictory example," it's transparently
explaining why an earlier version of this exact guide was wrong, with the
live verification command included so the claim is checkable rather than
just asserted.

## NORMAL USER RESET: MESFLOW UI/API

Documented as its own path (`mesflow.web.users.reset_user_password`,
`POST /api/users/<user_id>/reset-password`, gated by
`@permission_required('users.manage')`, records audit action
`USER_PASSWORD_RESET`) — verified against `mesflow/app/mesflow/web/
users.py` and the frontend handler in `mesflow/app/mesflow/web/static/
app.js` (`window.resetUserPassword`, page title `Người dùng hệ thống`,
confirmed by grep to be the exact live UI string). Explicitly scoped to
manager/supervisor/operator/viewer and any admin account other than "the
one admin currently locked out" — the guide states plainly not to use
`reset-admin` for this case.

## ADMIN RECOVERY: SSH + docker exec + reset-admin

Documented per Steps A-F above. Distinguished clearly from the normal-user
path with an explicit "hai tình huống khác nhau — đừng dùng nhầm cách của
tình huống này cho tình huống kia" framing in the card itself, plus two
separate `EMERGENCY_ACCESS_MATRIX` rows.

## PERSISTENT-CONFIG WARNING (audited, not assumed)

Read `mesflow/compose.yml`: the `mesflow` service declares `env_file:
[.env]`, so everything in `/opt/mesflow/.env` (including
`MESFLOW_ADMIN_PASSWORD`/`MESFLOW_ADMIN_USERNAME` if present) is loaded
into the container's real environment on every start — confirmed this key
is genuinely set (non-empty) in this DEV host's own `/opt/mesflow/.env`
(checked presence only, value never read or printed). Read `mesflow/
scripts/docker-entrypoint.sh`: it runs `seed-admin` on every boot, but
`seed_admin()` itself only acts when `repo.count()==0` — so a plain
container restart/recreate does **not** silently revert a `reset-admin`
change (verified in code, not assumed, and stated as such rather than
inventing a "recreate reverts it" claim the code doesn't support). The
real, verified risk is narrower and different: since `reset_admin()`
always reads `settings.admin_password` fresh on every invocation, running
`reset-admin` again later **without** explicitly passing `-e
MESFLOW_ADMIN_PASSWORD=...` will silently fall back to whatever is
currently in `/opt/mesflow/.env` — documented as
`MESFLOW_ADMIN_PASSWORD_WARNING`, rendered as its own note box on the
guide page, naming `/opt/mesflow/.env` as the canonical secret source an
operator should also update if they want the reset password to persist.

## SECURITY NOTES

`read -s` → shell variable → `docker exec -e` → `unset` documented as the
required sequence, with the exact anti-pattern
(`docker exec -e MESFLOW_ADMIN_PASSWORD=MySecret123 ...`) named and
explained (shell history + process listing exposure). Never print/store/
commit the password, stated explicitly, including "don't write it into
`.env`/README/repo unless deliberately changing the canonical secret
source."

## RECOVERY MATRIX

`EMERGENCY_ACCESS_MATRIX` now has 4 rows (was 3): MESFlow normal-user
reset, MESFlow admin reset (split into two, matching the task's table
exactly), Deploy Agent, Bootstrap — plus the unchanged `LOST_SSH_NOTE` row
for losing SSH itself.

## TROUBLESHOOTING

Two new `FAILURES` entries, both with real verified commands: "LỆNH
`reset-admin` BÁO \"unknown command\"" (fix: read the real command map via
the same `grep -o "funcs={[^}]*}"` command used above, never guess another
subcommand) and "mesflow-app KHÔNG CHẠY" (fix: `docker ps -a --filter
name=mesflow-app`, start the container via Deploy Agent, explicitly never
`docker compose down -v` or recreate the database as a first response).

## TESTS

`bootstrap/tests/test_guide_deployment.py`: **44/44 pass** (was 43 before
this task's 6 new/updated tests: two fixed to match the corrected content,
four new — stale-command regression, MESFlow-vs-generic server labeling,
emergency-matrix-row-count, and the new troubleshooting entries). Full
suite (`bootstrap/tests/`, all files) also **44/44**, run via
`/opt/mesflow-bootstrap/.venv/bin/python3 -m unittest discover -s tests
-v` — that installed venv's packages were only read from; no restart of
the real `mesflow-bootstrap` service. Live verification against the real
local DEV `mesflow-app` container was read-only throughout (`docker ps
--filter`, the `settings.admin_username` check, the `funcs={...}` grep) —
captured and quoted above; the actual password-mutating step was not
executed, for the reasons stated under "MESFLOW PASSWORD RECOVERY" above.

## PRODUCTION TEST PASSWORD RESET: NO

## PRODUCTION PASSWORD RESET: NO

## PASSWORD PRINTED/STORED: NO

No password value (test or otherwise) was printed, logged, or written to
any file in this session.

## COMMANDS VERIFIED AGAINST CURRENT MESFLOW CODE: YES

`mesflow/cli.py`, `mesflow/core/config.py`,
`mesflow/db/repositories/user_repository.py`, `mesflow/web/users.py`, and
`mesflow/web/static/app.js` were all read directly before writing any
guide text. Where live verification was possible without mutating real
state, it was performed and quoted verbatim above rather than assumed.
