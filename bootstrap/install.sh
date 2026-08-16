#!/usr/bin/env bash
# MESFlow Bootstrap / Recovery Console installer.
#
# Prepares the MINIMUM environment on a brand-new Ubuntu server and
# installs mesflow-bootstrap as its own systemd service. Deliberately does
# NOT install MESFlow, QA Center or the Deploy Agent itself -- that is done
# afterward from the Bootstrap web UI (Install Deploy Agent page).
#
# Usage: sudo ./install.sh
#
# Idempotent: re-running preserves /var/lib/mesflow-bootstrap (admin
# account, state, logs) and only refreshes the code under
# /opt/mesflow-bootstrap and the systemd unit.
set -Eeuo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }
note() { echo "-- $*"; }

[[ "$(id -u)" -eq 0 ]] || die "Run as root: sudo ./install.sh"

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_HOME="${MESFLOW_BOOTSTRAP_HOME:-/opt/mesflow-bootstrap}"
DATA_DIR="${MESFLOW_BOOTSTRAP_DATA_DIR:-/var/lib/mesflow-bootstrap}"
BIND_HOST="${MESFLOW_BOOTSTRAP_HOST:-0.0.0.0}"
PORT="${MESFLOW_BOOTSTRAP_PORT:-8098}"
SERVICE_USER="root"   # needs docker/systemctl control; never exposes a shell

echo "=== MESFlow Bootstrap / Recovery Console installer ==="

# --- 1. detect supported Ubuntu ---------------------------------------------
if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" == "ubuntu" ]]; then
    note "Detected Ubuntu ${VERSION_ID:-unknown} (${VERSION_CODENAME:-unknown})"
  else
    echo "WARNING: this is not Ubuntu (ID=${ID:-unknown}). Continuing, but only Ubuntu is supported/tested." >&2
  fi
else
  echo "WARNING: /etc/os-release not found; cannot verify OS." >&2
fi

# --- 2. network/IP -----------------------------------------------------------
IP_ADDR="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -n "$IP_ADDR" ]] || IP_ADDR="127.0.0.1"
note "Primary IP: $IP_ADDR"

# --- 3. verify/install OpenSSH ------------------------------------------------
if command -v sshd >/dev/null 2>&1 || [[ -x /usr/sbin/sshd ]]; then
  note "OpenSSH server already installed."
else
  note "OpenSSH server not found; installing openssh-server."
  apt-get update -qq
  apt-get install -y -qq openssh-server
fi
if systemctl is-enabled ssh >/dev/null 2>&1; then
  systemctl enable --now ssh >/dev/null 2>&1 || true
elif systemctl is-enabled sshd >/dev/null 2>&1; then
  systemctl enable --now sshd >/dev/null 2>&1 || true
fi
SSH_STATE="$(systemctl is-active ssh 2>/dev/null || systemctl is-active sshd 2>/dev/null || echo unknown)"
note "SSH service state: $SSH_STATE"

# --- 4. verify/install Docker Engine + Compose --------------------------------
if command -v docker >/dev/null 2>&1; then
  note "Docker already installed ($(docker --version 2>/dev/null || echo present))."
else
  note "Docker not found; installing Docker Engine + Compose plugin from get.docker.com."
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true
if docker compose version >/dev/null 2>&1; then
  note "Docker Compose plugin available."
else
  echo "WARNING: 'docker compose' plugin not available; Deploy Agent install will fail until it is." >&2
fi
# Shared edge network the Deploy Agent's compose files expect to already
# exist (external: true) -- creating a bridge network is not a firewall
# change, so this is safe to do automatically.
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker network inspect mesflow-edge >/dev/null 2>&1 || {
    docker network create mesflow-edge >/dev/null && note "Created docker network mesflow-edge."
  }
fi
DOCKER_STATE="$(command -v docker >/dev/null 2>&1 && echo installed || echo missing)"

# --- 5. minimal directories ---------------------------------------------------
install -d -m 0755 "$BOOTSTRAP_HOME" "$BOOTSTRAP_HOME/templates" "$BOOTSTRAP_HOME/static"
install -d -m 0700 "$DATA_DIR" "$DATA_DIR/uploads" "$DATA_DIR/logs"
# Never created/wiped here -- Deploy Agent owns its own persistent state.
install -d -m 0755 /var/lib/mesflow-deploy-agent 2>/dev/null || true

# --- 6. install Bootstrap service (code) --------------------------------------
cp -a "$SRC/app.py" "$BOOTSTRAP_HOME/app.py"
rm -rf "$BOOTSTRAP_HOME/templates" "$BOOTSTRAP_HOME/static"
cp -a "$SRC/templates" "$BOOTSTRAP_HOME/templates"
cp -a "$SRC/static" "$BOOTSTRAP_HOME/static"
[[ -f "$SRC/VERSION.txt" ]] && cp -a "$SRC/VERSION.txt" "$BOOTSTRAP_HOME/VERSION.txt"

# Vendor an UNMODIFIED copy of deploy-agent/updater/updater.py for its
# already-tested artifact-verification/update/rollback logic -- Bootstrap's
# Update/Rollback capability loads this file rather than re-implementing
# it (see reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md). Sourced from
# the sibling deploy-agent/ checkout next to this bootstrap/ directory;
# if that sibling isn't present (Bootstrap installed standalone, without
# the full workspace), Update/Rollback report themselves unavailable at
# runtime instead of failing this install.
DEPLOY_AGENT_UPDATER_SRC="$SRC/../deploy-agent/updater/updater.py"
if [[ -f "$DEPLOY_AGENT_UPDATER_SRC" ]]; then
  cp -a "$DEPLOY_AGENT_UPDATER_SRC" "$BOOTSTRAP_HOME/agent_updater_core.py"
  note "Vendored deploy-agent/updater/updater.py for Update/Rollback."
else
  echo "WARNING: $DEPLOY_AGENT_UPDATER_SRC not found -- Update/Rollback will report" >&2
  echo "         themselves unavailable until this install.sh is re-run from a full" >&2
  echo "         workspace checkout with deploy-agent/ present alongside bootstrap/." >&2
fi

command -v python3 >/dev/null || die "python3 is required"
if ! python3 -m venv --help >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq python3-venv python3-pip
fi
if [[ ! -x "$BOOTSTRAP_HOME/.venv/bin/python" ]]; then
  python3 -m venv "$BOOTSTRAP_HOME/.venv"
fi
"$BOOTSTRAP_HOME/.venv/bin/python" -m pip install --disable-pip-version-check -q \
  -r "$SRC/requirements.txt"

cat > /etc/mesflow-bootstrap.env <<EOF
MESFLOW_BOOTSTRAP_HOME=$BOOTSTRAP_HOME
MESFLOW_BOOTSTRAP_DATA_DIR=$DATA_DIR
MESFLOW_BOOTSTRAP_HOST=$BIND_HOST
MESFLOW_BOOTSTRAP_PORT=$PORT
EOF
chmod 644 /etc/mesflow-bootstrap.env

# Separate, root-only file for secrets only (never 644 like the file above).
# MESFLOW_AGENT_UPDATER_TOKEN is optional: set it in this invocation's
# environment to migrate the EXACT bearer token already configured on DEV
# for the retiring :8099 service (deploy-agent/updater/'s
# MESFLOW_AGENT_UPDATER_TOKEN), e.g.:
#   sudo MESFLOW_AGENT_UPDATER_TOKEN="$(cat /opt/mesflow-agent-updater/.env | grep -oP '(?<=TOKEN=).*')" ./install.sh
# so the eventual cutover changes only DEV's target URL, never a secret. If
# unset, app.py auto-generates and persists one in state.json on first run.
touch /etc/mesflow-bootstrap-secrets.env
chmod 600 /etc/mesflow-bootstrap-secrets.env
if [[ -n "${MESFLOW_AGENT_UPDATER_TOKEN:-}" ]]; then
  printf 'MESFLOW_AGENT_UPDATER_TOKEN=%s\n' "$MESFLOW_AGENT_UPDATER_TOKEN" > /etc/mesflow-bootstrap-secrets.env
  chmod 600 /etc/mesflow-bootstrap-secrets.env
  note "Migrated MESFLOW_AGENT_UPDATER_TOKEN from the installer's environment."
fi

cat > /etc/systemd/system/mesflow-bootstrap.service <<EOF
[Unit]
Description=MESFlow Bootstrap / Recovery Console
# Deliberately does NOT require docker.service or any MESFlow unit --
# Bootstrap must stay reachable even when Docker/MESFlow/Deploy Agent are
# down; that is precisely the case it exists to help recover from.
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BOOTSTRAP_HOME
EnvironmentFile=/etc/mesflow-bootstrap.env
EnvironmentFile=-/etc/mesflow-bootstrap-secrets.env
ExecStart=$BOOTSTRAP_HOME/.venv/bin/python $BOOTSTRAP_HOME/app.py
Restart=always
RestartSec=3
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
EOF

# --- 7. start Bootstrap -------------------------------------------------------
systemctl daemon-reload
systemctl enable mesflow-bootstrap.service >/dev/null
systemctl restart mesflow-bootstrap.service

# --- 8. verify health ----------------------------------------------------------
HEALTHY=0
for _ in $(seq 1 15); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 1
done
[[ "$HEALTHY" -eq 1 ]] || die "mesflow-bootstrap did not become healthy on port $PORT. Check: journalctl -u mesflow-bootstrap -n 100"

# --- 9. print URLs / status ----------------------------------------------------
echo
echo "=== mesflow-bootstrap installed and running ==="
echo "Local:    http://127.0.0.1:${PORT}/"
echo "Network:  http://${IP_ADDR}:${PORT}/"
echo "Health:   http://127.0.0.1:${PORT}/health"
echo "Docker:   $DOCKER_STATE"
echo "SSH:      $SSH_STATE (port 22)"
if [[ -f "$DATA_DIR/SETUP_TOKEN.txt" ]]; then
  echo
  echo "First-run setup token (root-only file, use once at /setup):"
  echo "  sudo cat $DATA_DIR/SETUP_TOKEN.txt"
fi
if [[ -f "$BOOTSTRAP_HOME/agent_updater_core.py" ]]; then
  echo
  echo "Update/Rollback:  enabled (GET/POST http://${IP_ADDR}:${PORT}/updater/{health,status,update})"
  echo "Migration note:   deploy-agent/updater/ (:8099) keeps running -- do NOT retire it until"
  echo "                  Bootstrap's update/rollback has passed real DEV + Production Test tests."
  echo "                  See reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md."
else
  echo
  echo "Update/Rollback:  UNAVAILABLE (deploy-agent/updater/updater.py not found next to bootstrap/)"
fi
echo
echo "Next step: open the URL above, complete initial admin setup, then use"
echo "'Install Deploy Agent' to upload the Deploy Agent installer package."
