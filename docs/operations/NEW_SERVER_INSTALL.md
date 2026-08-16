# New Server Install

For a fresh Production Test or Production host. DEV bootstrap is a
different flow (workspace + build enabled) and is not covered here.

## Prerequisites

- Docker + Docker Compose plugin installed.
- `/opt/mesflow/.env` already present (created out-of-band by a human —
  the installer refuses to create or copy it, since it holds secrets).
- No conflicting listener on the Agent port (default 8090).

## Install the Deploy Agent

```
sudo bash install.sh
```

from the extracted `mesflow-deploy-agent` installer package
(`deploy-agent/installer/install.sh` in the workspace; packaged by
`deploy-agent/package_installer.sh`).

### Workspace/source resolution — read this if you see path errors

The installer and the Agent process itself never assume `/root/workspace/mesflow`.
Resolution order:

1. `MESFLOW_WORKSPACE_ROOT=/path` — explicit override, always wins.
2. The real user behind `sudo`, via `$SUDO_USER` → `/home/$SUDO_USER/workspace/mesflow`.
3. The controlling terminal's login owner (`logname`).
4. Last resort: `$HOME` (which is `/root` when running as root) — a warning
   is printed so this is never silently wrong.

Production Test and Production installs normally don't need workspace
source at all (`MESFLOW_BUILD_ENABLED=false`, receive-only), so this mostly
matters for DEV bootstraps and for the Agent's optional local build path.

### Existing Agent container

If a container named `mesflow-deploy-agent` already exists, the installer:

1. detects it and records its running image **id** (not tag — `docker
   compose up --force-recreate` identifies "the container for this service"
   by Compose project/service labels, not by container name, so renaming the
   container beforehand does **not** protect it from being torn down by the
   recreate; only the image id and the external data bind mount are reliably
   preserved),
2. builds and starts the new container under the same name (persistent data
   lives in `/var/lib/mesflow-deploy-agent`, outside the container, so
   nothing is lost when the old container is replaced),
3. polls `/agent/health` for up to ~30s,
4. on success: done, and prints the previous image id for manual rollback
   if a problem is found later,
5. on failure: automatically rolls back — redeploys the previous image id
   with `--no-build` on the same data dir.

Nothing here touches nginx, the firewall, systemd, or PostgreSQL — this
installer is intentionally local-only.

## After install

1. Set `SERVER_ROLE` and `MESFLOW_BUILD_ENABLED` appropriately for the host
   role (`compose.production-test.override.yml` already sets
   `PRODUCTION_TEST` / `false`; Production should use the same pattern with
   `PRODUCTION`).
2. Verify `/agent/health`.
3. Confirm the Agent shows `receive only` in its UI for Production Test /
   Production (build controls should be disabled).
4. Do not promote anything to this host until it reports healthy and the
   correct role.

## Legacy (non-Docker) installer

`deploy-agent/install_agent.sh` (systemd + venv, no container) also now
resolves `SUDO_USER`/`MESFLOW_WORKSPACE_ROOT` the same way and writes it to
`/etc/mesflow-deploy-agent.env`. Prefer the Docker installer above for new
hosts; the legacy path exists for compatibility with older installs.
