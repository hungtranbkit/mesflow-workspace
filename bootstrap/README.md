# MESFlow Bootstrap / Recovery Console

A minimal, independent host/systemd service for a brand-new Ubuntu server.
It prepares the minimum environment (OpenSSH, Docker Engine + Compose plugin,
a handful of directories) and exposes a small authenticated web UI that can
install and recover the Deploy Agent — nothing else.

- Default web port: **8098**
- Deploy Agent stays on: **8090**
- Runs independently of Docker/MESFlow/Deploy Agent: it must stay reachable
  even if all three are down.

## Install

```bash
sudo ./install.sh
```

Then open `http://<server-ip>:8098/`, read the setup token
(`sudo cat /var/lib/mesflow-bootstrap/SETUP_TOKEN.txt`), and complete the
initial admin setup at `/setup`.

## Layout

```
/opt/mesflow-bootstrap/        # source + venv (from this bootstrap/ dir)
  app.py
  templates/
  static/
  .venv/

/var/lib/mesflow-bootstrap/    # persistent runtime data
  uploads/                     # staged installer packages (deleted after use)
  logs/
    bootstrap.log
    audit.log
  state.json                   # secret key, admin username/password hash
  SETUP_TOKEN.txt              # deleted once initial setup completes
```

## Pages

Overview · Install Deploy Agent · Docker · Services · Logs · Commands.

When the Deploy Agent is healthy, Overview leads with a "Deploy Agent
Healthy → Open Deploy Agent" panel — Bootstrap becomes a minimal recovery
console rather than a second control plane.

## Deploy Agent install/update contract

Bootstrap accepts the same immutable installer package a human would run
over SSH: the ZIP produced by `deploy-agent/package_installer.sh`
(`install.sh` + `payload/mesflow-deploy-agent/{agent.py,VERSION.txt,docker/...}`).
It validates structure and optional SHA256, reads `VERSION.txt`, refuses a
downgrade unless explicitly allowed, runs the package's own `install.sh`
(which does the actual build/rollback), then independently polls
`http://127.0.0.1:8090/agent/health` and reports PASS/FAILED. Deploy Agent's
own build/rollback/compose logic is never duplicated here.

`/var/lib/mesflow-deploy-agent` is never created-empty-over or deleted by
this service.

## Deploy Agent update / rollback (consolidated from `deploy-agent/updater/`)

Bootstrap now owns Deploy Agent lifecycle end to end: Install (`/install-agent`),
Update (`/agent/update`), Rollback (Overview → Advanced), Start/Restart
(Overview / Docker), status/health (Overview), and Logs (`/agent/logs`).

Update/Rollback are not re-implemented here: `install.sh` vendors an
**unmodified** copy of `deploy-agent/updater/updater.py` into
`/opt/mesflow-bootstrap/agent_updater_core.py`, and `app.py` loads it,
overriding only its target-dir/compose-files/env-file config to point at
this host's real Deploy Agent. That file's own tests
(`deploy-agent/tests/test_updater.py`) cover the artifact-verification/
update/rollback state machine; `bootstrap/tests/test_agent_lifecycle.py`
covers only Bootstrap's wiring around it.

Machine-facing endpoints `GET /updater/health`, `GET /updater/status`,
`POST /updater/update` are wire-compatible with the old `deploy-agent/updater/`
:8099 service (same path, same `Authorization: Bearer <token>` header, same
raw-ZIP body) — bearer token in `state.json`'s `agent_updater_token`, settable
via `MESFLOW_AGENT_UPDATER_TOKEN` at install time to migrate the exact
existing DEV-configured token. This means the DEV → target push-update flow
(`deploy-agent/agent.py`'s `_push_agent_update`) can cut over from :8099 to
:8098 by changing only the configured URL's port — no code change, no new
secret.

**`deploy-agent/updater/` (port 8099) is not retired.** It keeps running
during migration; only removed after the gate in
`reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md` passes on real hosts. See
`bootstrap/AGENTS.md`.

## Safe commands

`uptime`, `free -h`, `df -h`, `ip addr`, `ss -ltnp`, `systemctl --failed`,
`docker ps`, `docker ps -a`, `docker images`, `docker compose ls`. Every run
is timeout-bounded, output-bounded, and written to the audit log.

## Docker/service actions

Only the `mesflow-deploy-agent` container/unit can be started, restarted or
stopped, and only with explicit confirmation. No prune, no volume deletion,
no arbitrary container control.
