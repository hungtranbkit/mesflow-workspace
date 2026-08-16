#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MES="$ROOT/mesflow"
echo "===== MESFlow UI Audit Preflight ====="
echo "Workspace: $ROOT"
echo "Project:   $MES"
[[ -d "$MES" ]] || { echo "[ERROR] mesflow project missing"; exit 1; }
[[ -f "$ROOT/docs/ui/MESFLOW_UI_STANDARD.md" ]] || { echo "[ERROR] UI standard missing"; exit 1; }
echo "===== Major frontend files ====="
find "$MES" -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' \) ! -path '*/node_modules/*' ! -path '*/runtime/*' | sort | head -200
echo "===== Likely page render functions ====="
grep -RniE 'render[A-Z]|data-page=|openPage\(|menu=\[' "$MES/app" --include='*.js' --include='*.html' 2>/dev/null | head -200 || true
echo "===== CSS size ====="
find "$MES" -type f -name '*.css' ! -path '*/node_modules/*' -print0 | xargs -0 wc -l 2>/dev/null | tail -20 || true
echo "===== Existing UI reports ====="
find "$ROOT/reports" -maxdepth 1 -type f -iname '*UI*' -print 2>/dev/null || true
echo "Preflight complete. No code changed."
