#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-}"

usage(){
  cat <<USAGE
Usage:
  $0 mesflow
  $0 deploy-agent
  $0 qa-center
  $0 all

READ-ONLY against /opt.
Creates a sanitized snapshot + diff report.
Does NOT overwrite the workspace.
USAGE
}

[[ -n "$ACTION" ]] || { usage; exit 2; }

project_info(){
  case "$1" in
    mesflow)      printf '%s|%s\n' "/opt/mesflow" "$ROOT/mesflow" ;;
    deploy-agent) printf '%s|%s\n' "/opt/mesflow-deploy-agent" "$ROOT/deploy-agent" ;;
    qa-center)    printf '%s|%s\n' "/opt/mesflow-qa-center" "$ROOT/qa-center" ;;
    *) return 1 ;;
  esac
}

EXCLUDES=(
  --exclude '.git/'
  --exclude '.env'
  --exclude '.env.*'
  --exclude '.venv/'
  --exclude 'venv/'
  --exclude 'node_modules/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '*.pyo'
  --exclude 'runtime/'
  --exclude 'data/'
  --exclude 'logs/'
  --exclude 'log/'
  --exclude 'test-results/'
  --exclude 'playwright-report/'
  --exclude 'tutorial-output/'
  --exclude 'mesflow-user-guide/'
  --exclude '.pytest_cache/'
  --exclude '.mypy_cache/'
  --exclude '.ruff_cache/'
  --exclude '.cache/'
  --exclude 'certs/'
  --exclude '*.pem'
  --exclude '*.key'
  --exclude '*.crt'
  --exclude '*.p12'
  --exclude '*.pfx'
  --exclude '*.db'
  --exclude '*.sqlite'
  --exclude '*.sqlite3'
)

version_of(){
  local dir="$1"
  if [[ -f "$dir/VERSION.txt" ]]; then
    tr -d '\r\n ' < "$dir/VERSION.txt"
  elif [[ -f "$dir/VERSION" ]]; then
    tr -d '\r\n ' < "$dir/VERSION"
  else
    printf '%s' "unknown"
  fi
}

sync_one(){
  local project="$1"
  local info src dst deployed_ver workspace_ver stamp snap report diff_file rc status

  info="$(project_info "$project")" || { echo "[ERROR] Unknown project: $project" >&2; exit 2; }
  src="${info%%|*}"
  dst="${info##*|}"

  echo
  echo "===== RECONCILE: $project ====="
  echo "DEPLOYED:  $src"
  echo "WORKSPACE: $dst"

  [[ -d "$src" ]] || { echo "[WARN] Deployed path not found: $src"; return 0; }
  [[ -d "$dst" ]] || { echo "[WARN] Workspace path not found: $dst"; return 0; }

  deployed_ver="$(version_of "$src")"
  workspace_ver="$(version_of "$dst")"
  stamp="$(date +%Y%m%d_%H%M%S)"
  snap="$ROOT/tmp/reconcile/$project/$stamp/deployed"
  report="$ROOT/reports/RECONCILE_${project//-/_}_${stamp}.md"
  diff_file="$ROOT/tmp/reconcile/$project/$stamp/diff.txt"

  mkdir -p "$snap" "$(dirname "$report")" "$(dirname "$diff_file")"

  echo "Deployed version:  $deployed_ver"
  echo "Workspace version: $workspace_ver"
  echo "Creating sanitized snapshot..."

  rsync -a "${EXCLUDES[@]}" "$src/" "$snap/"

  set +e
  diff -ruN \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='runtime' \
    --exclude='data' \
    --exclude='logs' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='test-results' \
    --exclude='playwright-report' \
    "$dst" "$snap" > "$diff_file"
  rc=$?
  set -e

  case "$rc" in
    0) status="MATCH" ;;
    1) status="DIFF" ;;
    *) status="ERROR" ;;
  esac

  {
    echo "# Deployed Source Reconciliation"
    echo
    echo "- Project: \`$project\`"
    echo "- Deployed path: \`$src\`"
    echo "- Workspace path: \`$dst\`"
    echo "- Deployed version: \`$deployed_ver\`"
    echo "- Workspace version: \`$workspace_ver\`"
    echo "- Status: **$status**"
    echo "- Snapshot: \`$snap\`"
    echo "- Diff: \`$diff_file\`"
    echo
    if [[ "$status" == "MATCH" ]]; then
      echo "No source difference detected after safety exclusions."
    elif [[ "$status" == "DIFF" ]]; then
      echo "Source differences exist. Review the diff before importing anything."
      echo
      echo "Do NOT overwrite the workspace blindly."
    else
      echo "The diff command failed. Inspect the environment."
    fi
  } > "$report"

  echo "Status:   $status"
  echo "Snapshot: $snap"
  echo "Diff:     $diff_file"
  echo "Report:   $report"

  if [[ "$status" == "DIFF" ]]; then
    echo
    echo "===== DIFF SUMMARY ====="
    grep -E '^diff |^Only in ' "$diff_file" | head -80 || true
    echo
    echo "[ACTION REQUIRED] Review/reconcile before new development."
  elif [[ "$status" == "MATCH" ]]; then
    echo "[OK] Workspace matches deployed source after exclusions."
  else
    return 1
  fi
}

case "$ACTION" in
  all)
    sync_one mesflow
    sync_one deploy-agent
    sync_one qa-center
    ;;
  mesflow|deploy-agent|qa-center)
    sync_one "$ACTION"
    ;;
  *)
    usage
    exit 2
    ;;
esac

echo
echo "Reconciliation check complete."
echo "No /opt files were modified."
