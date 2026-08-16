#!/usr/bin/env bash
# Read-only audit across workspace / /opt / /var/lib / Docker.
# Never mutates anything. Prints a summary; also refreshes the JSON
# fingerprints scripts/compare-environments.py already produces.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

section(){ printf '\n===== %s =====\n' "$1"; }
version_of(){ [[ -f "$1" ]] && tr -d '[:space:]' < "$1" || echo "unknown"; }

section "Workspace source versions"
for p in mesflow deploy-agent qa-center esp-kiosk; do
  printf '%-14s %s\n' "$p" "$(version_of "$ROOT/$p/VERSION.txt")"
done

section "Workspace git status"
for p in mesflow deploy-agent qa-center esp-kiosk; do
  if git -C "$ROOT/$p" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    dirty="$(git -C "$ROOT/$p" status --porcelain | wc -l | tr -d ' ')"
    printf '%-14s branch=%s commit=%s dirty_files=%s\n' "$p" \
      "$(git -C "$ROOT/$p" rev-parse --abbrev-ref HEAD)" \
      "$(git -C "$ROOT/$p" rev-parse --short HEAD)" "$dirty"
  else
    printf '%-14s NOT A GIT REPOSITORY\n' "$p"
  fi
done

section "Deployed /opt versions"
printf 'mesflow        %s\n' "$(version_of /opt/mesflow/VERSION.txt)"
printf 'deploy-agent   %s\n' "$(version_of /opt/mesflow-deploy-agent/VERSION.txt)"
printf 'qa-center      current=%s previous=%s\n' \
  "$(version_of /opt/mesflow-qa-center/current/VERSION.txt)" \
  "$(version_of /opt/mesflow-qa-center/previous/VERSION.txt)"

section "Deploy Agent /opt vs workspace source drift"
for p in mesflow deploy-agent qa-center; do
  case "$p" in
    mesflow) opt=/opt/mesflow ;;
    deploy-agent) opt=/opt/mesflow-deploy-agent ;;
    qa-center) opt=/opt/mesflow-qa-center ;;
  esac
  [[ -d "$opt" ]] || { echo "$p: $opt missing"; continue; }
  n="$( (diff -rq "$ROOT/$p" "$opt" \
        -x runtime -x __pycache__ -x .pytest_cache -x .git -x node_modules \
        -x .env -x '.env.*' -x docker/runtime -x current -x previous 2>/dev/null || true) | wc -l)"
  echo "$p: $n differing paths vs $opt (run scripts/reconcile-from-opt.sh $p for detail)"
done

section "Running MESFlow-ecosystem containers"
docker ps -a --filter "name=mesflow" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo "docker unavailable"

section "docker compose projects"
docker compose ls 2>/dev/null | grep -iE 'mesflow|NAME' || true

section "Persistent runtime data"
for d in /opt/mesflow/runtime /var/lib/mesflow-deploy-agent /opt/mesflow-qa-center/runtime; do
  if [[ -d "$d" ]]; then
    printf '%-40s exists (owner=%s)\n' "$d" "$(stat -c '%U' "$d" 2>/dev/null || echo '?')"
  else
    printf '%-40s MISSING/NO ACCESS\n' "$d"
  fi
done

section "Host tools"
python3 --version 2>/dev/null || true
docker --version 2>/dev/null || true
docker compose version 2>/dev/null || true
