# bootstrap

Read and obey the workspace rules first:

`../AGENTS.md`

Project directory:
`bootstrap/`

## What this is

A small, independent host/systemd service (`mesflow-bootstrap`, default port
8098) for a brand-new Ubuntu server: `install.sh` prepares the minimum
environment (OpenSSH, Docker Engine + Compose, base directories) and starts a
web console that can install/recover the Deploy Agent. It must keep working
even when Docker, MESFlow or the Deploy Agent are down.

## Boundaries — read before touching this code

- Do NOT copy Deploy Agent features into Bootstrap (release manager, OTA, QA
  Center management, Production promotion, fleet/predictive/notifications —
  none of that belongs here). See `reports/SERVER_BOOTSTRAP_RECOVERY.md`.
- Bootstrap now owns Deploy Agent lifecycle (install/update/rollback/
  restart/status/logs), consolidated from `deploy-agent/updater/`'s former
  :8099 service — see `reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md`.
  It still never *re-implements* that logic: `install.sh` vendors an
  unmodified copy of `deploy-agent/updater/updater.py` into
  `/opt/mesflow-bootstrap/agent_updater_core.py`, and `app.py` loads it,
  only overriding its config (target dir/compose files/env file) to point
  at this host's real Deploy Agent. Edit the update/rollback state machine
  itself in `deploy-agent/updater/updater.py`, never by forking it inside
  `bootstrap/`.
- The first-install/source-rebuild flow (`/install-agent`, the ZIP from
  `deploy-agent/package_installer.sh`, runs the package's own `install.sh`)
  and the in-place update flow (`/agent/update`, the
  `AGENT_UPDATE_<version>.zip` format, uses the vendored updater core) are
  two different package formats for two different situations — do not merge
  them into one upload form.
- Never delete or wipe `/var/lib/mesflow-deploy-agent`.
- No arbitrary command execution / web shell. Only the fixed allowlist in
  `app.py`'s `SAFE_COMMANDS`.
- **Migration gate — do not remove `deploy-agent/updater/` (:8099) or its
  systemd service.** It stays installed and running until Bootstrap's
  update/rollback has passed real DEV → target and DEV → Production Test
  update tests (not just this repo's mocked unit tests) and a real rollback
  test, per `reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md`'s migration
  gate. Both services may run on the same host at once; they don't share a
  lock or log file. `/updater/health`, `/updater/status`, `/updater/update`
  on Bootstrap (:8098) are wire-compatible with the old :8099 contract
  (same path, same bearer-token header, same body format) specifically so
  the DEV-side cutover is a URL change, not a code change.

Do not modify sibling projects unless the task explicitly requires a
cross-project change.
