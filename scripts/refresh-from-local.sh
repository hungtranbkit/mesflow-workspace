#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/workspace.sources"

EX=(
  --exclude '.git/'
  --exclude '.env'
  --exclude '.env.*'
  --exclude '.venv/'
  --exclude 'node_modules/'
  --exclude '__pycache__/'
  --exclude 'runtime/'
  --exclude 'data/'
  --exclude 'logs/'
  --exclude 'test-results/'
  --exclude 'playwright-report/'
  --exclude 'certs/'
  --exclude '*.pem'
  --exclude '*.key'
  --exclude '*.db'
  --exclude '*.sqlite'
)

sync_one(){
  local src="$1" dst="$2"
  [[ -n "$src" && -d "$src" ]] || return 0
  echo "Sync $src -> $dst"
  rsync -a --delete "${EX[@]}" "$src/" "$dst/"
}

sync_one "$MESFLOW_SRC" "$ROOT/mesflow"
sync_one "$DEPLOY_AGENT_SRC" "$ROOT/deploy-agent"
sync_one "$QA_CENTER_SRC" "$ROOT/qa-center"
sync_one "$ESP_KIOSK_SRC" "$ROOT/esp-kiosk"
sync_one "$SERVER_AGENT_SRC" "$ROOT/server-agent"

echo "Done. Production runtime was not modified."
