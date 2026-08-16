# Server Bootstrap / Recovery Console

New project: `bootstrap/`. Small, independent host/systemd service for a
brand-new Ubuntu server: `install.sh` prepares the minimum environment
(OpenSSH, Docker Engine + Compose, base directories) and starts a web console
that can install/recover the Deploy Agent, and nothing else.

## Architecture decision recorded up front

`deploy-agent/updater/updater.py` (`mesflow-agent-updater.service`) already
exists, already defaults to port **8099**, already runs independently of the
Deploy Agent container, and is already wired into the live DEV→target
push-update flow (`agent.py`'s `MESFLOW_PRODUCTION_TEST_AGENT_UPDATER_URL` /
`MESFLOW_PRODUCTION_AGENT_UPDATER_URL`, `deploy-agent/docker/compose.linux.yml`).
Binding the new console to 0.0.0.0:8099 would collide with it. Per the user's
explicit choice, Bootstrap uses a **different default port (8098)** and the
two services are left untouched and independent — see `bootstrap/AGENTS.md`.

Deploy Agent install/update logic itself is not re-implemented: the "Install
Deploy Agent" upload flow validates and then runs the real, existing
installer package produced by `deploy-agent/package_installer.sh`
(`install.sh` + `payload/mesflow-deploy-agent/`), the same artifact
documented in `docs/operations/NEW_SERVER_INSTALL.md`. Bootstrap only adds:
web upload UI, structure/checksum validation, a downgrade guard, an audit
log, and its own independent health poll/report.

```
BOOTSTRAP VERSION:     1.0.0
INSTALL COMMAND:       sudo bootstrap/install.sh   (installs to /opt/mesflow-bootstrap,
                        data at /var/lib/mesflow-bootstrap, systemd unit mesflow-bootstrap.service)
WEB URL:                http://<server-ip>:8098/   (default bind 0.0.0.0:8098; Deploy Agent stays on 8090)
SSH STATUS:              install.sh verifies/installs openssh-server if missing, enables+starts
                          `ssh`/`sshd`, and reports state/port on Overview + Services pages via
                          `systemctl is-active` + `ss -ltnp` (never a custom SSH server, never
                          stores passwords/keys)

DOCKER INSTALL:          install.sh installs Docker Engine + Compose plugin via get.docker.com
                          when `docker` is absent; idempotent (skips if already installed);
                          also creates the `mesflow-edge` bridge network if missing (required by
                          deploy-agent/docker/compose.linux.yml's `external: true` network) --
                          not a firewall change, so done without extra confirmation
DOCKER STATUS:            Overview/Docker pages report installed/running/version + compose
                          plugin availability via `docker version`/`docker info`/`docker compose
                          version`, all with short timeouts, all degrading to "unknown"/false
                          instead of raising when Docker is absent or the daemon is down

DEPLOY AGENT INSTALL:     Install Deploy Agent page accepts the real installer ZIP
                          (deploy-agent/package_installer.sh output: install.sh +
                          payload/mesflow-deploy-agent/{agent.py,VERSION.txt,docker/...}).
                          Validates ZIP structure, optional caller-supplied SHA256, reads
                          VERSION.txt, stages to a temp dir under
                          /var/lib/mesflow-bootstrap/uploads (cleaned up after use), then runs
                          the package's own install.sh (which does the actual
                          build/compose-up/rollback -- not duplicated in Bootstrap), then
                          independently polls http://127.0.0.1:8090/agent/health for up to 60s
                          and reports PASS/FAILED with the installer's captured output.
                          /var/lib/mesflow-deploy-agent is never created-empty-over or deleted.
DEPLOY AGENT UPDATE:      Same upload flow; refuses a version below the currently installed
                          VERSION.txt unless the operator explicitly checks "allow downgrade".
                          Comparison is numeric-tuple based on VERSION.txt, not string/tag.
DEPLOY AGENT RECOVERY:    Overview always shows one clear next action: Install (absent) / Start
                          (stopped) / View logs + Restart + Reinstall (unhealthy). Stopped/start
                          actions only ever touch the mesflow-deploy-agent container or, for the
                          legacy host/systemd install, the mesflow-deploy-agent.service unit --
                          MESFlow/PostgreSQL/QA Center are never touched by any Bootstrap action.

SAFE COMMANDS:            Fixed allowlist only (uptime, free -h, df -h, ip addr, ss -ltnp,
                          systemctl --failed, docker ps[-a], docker images, docker compose ls).
                          Each run: subprocess timeout 8s, output capped at 20000 chars, and one
                          audit.log line per run (actor, command key, rc). No arbitrary shell.
SERVICE ACTIONS:          Only the mesflow-deploy-agent container/unit can be
                          started/restarted/stopped, gated by a required `confirm=yes` field
                          (JS confirm() + server-side check) and CSRF. No docker system prune,
                          no volume deletion, no force-remove of arbitrary containers -- the
                          action allowlist (ACTIONABLE_CONTAINERS) is a single fixed set, not
                          exposed as a free-text field anywhere in the UI.

SYSTEMD:                  mesflow-bootstrap.service, After=network-online.target only --
                          deliberately does NOT require docker.service or any MESFlow unit, so
                          it starts and stays up even when Docker/MESFlow/Deploy Agent are down.
BOOT AUTO START:          `systemctl enable mesflow-bootstrap.service` in install.sh; reboot ->
                          systemd -> Bootstrap reachable -> Docker -> Deploy Agent
                          recoverable/installable -> remaining stack managed by Deploy Agent
                          (matches the required boot chain; not verified with a real reboot in
                          this session -- see TESTS).

SECURITY:                 First run generates a random setup token
                          (/var/lib/mesflow-bootstrap/SETUP_TOKEN.txt, chmod 600, root-only,
                          deleted once /setup completes); printed once to the systemd
                          journal/stdout, never to the app log or UI. Session auth via
                          werkzeug password hashing + Flask session (httponly, SameSite=Lax,
                          idle timeout default 30 min, configurable). Per-session CSRF token
                          checked on every mutating POST (setup, login, install, docker/service
                          actions, safe commands). state.json (secret key, admin password hash)
                          is chmod 600 in /var/lib/mesflow-bootstrap.
AUDIT:                    /var/lib/mesflow-bootstrap/logs/audit.log -- one JSON line per login
                          attempt, setup, upload, install result, safe command, and
                          docker/service action, with actor, remote addr, action, bounded
                          detail, ok/fail. Viewable (read-only, last 300 lines) on the Logs page.

TESTS:                    See below -- executed vs not executed, honestly separated.
PRODUCTION TOUCHED: NO
```

## Tests

Executed in this session, against an isolated `MESFLOW_BOOTSTRAP_HOME` /
`MESFLOW_BOOTSTRAP_DATA_DIR` / `MESFLOW_AGENT_HOME` in the scratchpad (never
pointed at this dev machine's real `/opt`, `/var/lib`, or any real
`mesflow-deploy-agent` container/service — per the "shared Docker daemon"
lesson, no mutating command was run against a real container):

| Test | Result |
|---|---|
| `python3 -m py_compile app.py` | PASS |
| `bash -n install.sh` | PASS |
| App boots with Docker/Deploy Agent absent from its configured paths (`/health` returns 200, `ok:true`) | PASS — confirms Bootstrap survives Docker/Deploy Agent/MESFlow being unavailable |
| First run generates `SETUP_TOKEN.txt` (chmod 600) and prints it once to stdout | PASS |
| `/setup` GET renders; POST with correct token+CSRF creates admin, deletes token file, redirects to `/login` | PASS |
| `/login` POST with correct credentials creates a session and redirects to `/overview` | PASS |
| `/overview` renders host facts (hostname/IP/OS/CPU/RAM/disk/uptime) and correctly shows "Deploy Agent Not Installed" recovery panel when the configured Deploy Agent path doesn't exist | PASS |
| `/commands` POST with a valid CSRF token runs the allowlisted `uptime` command and logs it to `audit.log` | PASS |
| `/commands` POST with an invalid CSRF token is rejected (flash error, command not executed, no audit entry) | PASS |
| `/docker` (view-only `docker ps`/`ps -a`/`images`/`compose ls` against the real local Docker daemon, read-only) renders | PASS |
| `/logout` clears the session; subsequent `/overview` request redirects (302) to `/login` | PASS |
| `install_agent.py` package validator: bad ZIP / structure mismatch / SHA256 mismatch | code-path only, not exercised with a real installer package/ZIP fixture in this session |

Not executed in this session (need a disposable Ubuntu host or explicit
human approval — Global safety rule requires approval for systemd
mutation/package installs, so `install.sh` itself was reviewed and
syntax-checked but not run for real):

- fresh install on a brand-new Ubuntu host
- idempotent reinstall (`sudo ./install.sh` run twice)
- Docker missing at install time
- sshd stopped/started via the Services page
- Deploy Agent absent → Install Deploy Agent (real installer ZIP)
- Deploy Agent stopped → Start Deploy Agent
- Deploy Agent unhealthy → View logs / Restart / Reinstall
- Deploy Agent update with a real newer installer package
- checksum mismatch rejection with a real mismatched SHA256
- reboot → `mesflow-bootstrap.service` auto-starts

Recommend running these against a disposable VM/container before relying on
this in a real recovery scenario; flag if you'd like that scheduled next.

## Files

- `bootstrap/app.py` — Flask app (stdlib + Flask + waitress only)
- `bootstrap/templates/*.html`, `bootstrap/static/style.css`
- `bootstrap/install.sh`
- `bootstrap/requirements.txt`, `bootstrap/VERSION.txt`, `bootstrap/.gitignore`
- `bootstrap/README.md`, `bootstrap/AGENTS.md`
- `AGENTS.md` — registered `bootstrap/` in the workspace Projects list and
  project-boundary examples

## Not done (explicitly out of scope per the task)

Release manager, OTA, QA Center management, Production promotion, a web root
shell, arbitrary command execution, and any Production deploy.
