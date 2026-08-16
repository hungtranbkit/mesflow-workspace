#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v codex >/dev/null 2>&1 || {
  echo "[ERROR] Codex CLI chưa có trong PATH."
  exit 1
}

echo "Workspace: $ROOT"
echo "Projects: mesflow, deploy-agent, qa-center, esp-kiosk, server-agent"
echo "Rules: $ROOT/AGENTS.md"
echo "Production mutation requires explicit HUMAN APPROVAL."
echo

exec codex "$@"
