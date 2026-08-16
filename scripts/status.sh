#!/usr/bin/env bash
# One-shot operational status: workspace / local / test / production versions,
# agent health, latest release identity, and promotion gates. Read-only.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

version_of(){ [[ -f "$1" ]] && tr -d '[:space:]' < "$1" || echo "unknown"; }
curl_json(){ curl -fsS --max-time 3 "$1" 2>/dev/null || true; }
jget(){ python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$1','') if isinstance(d,dict) else '')" 2>/dev/null || true; }

echo "===== MESFlow Status ====="
echo

echo "-- WORKSPACE VERSION --"
printf 'mesflow        %s\n' "$(version_of "$ROOT/mesflow/VERSION.txt")"
printf 'deploy-agent   %s\n' "$(version_of "$ROOT/deploy-agent/VERSION.txt")"
printf 'qa-center      %s\n' "$(version_of "$ROOT/qa-center/current/VERSION.txt")"
echo

echo "-- LOCAL AGENT (127.0.0.1:8090) --"
LOCAL_HEALTH="$(curl_json http://127.0.0.1:8090/agent/health)"
if [[ -n "$LOCAL_HEALTH" ]]; then
  echo "reachable: yes"
  echo "$LOCAL_HEALTH"
else
  echo "reachable: no"
fi
echo

echo "-- LOCAL VERSION (deployed MESFlow at /opt/mesflow) --"
version_of /opt/mesflow/VERSION.txt
echo

echo "-- TEST AGENT --"
echo "not auto-probed by this script (requires configured mesflow-test host/creds);"
echo "see docs/operations/BUILD_AND_PROMOTE.md for the manual verification steps"
echo

echo "-- LATEST RELEASE --"
LATEST_DIR="$(ls -1dt "$ROOT"/artifacts/releases/*/ 2>/dev/null | grep -v TEMPLATE | head -1 || true)"
if [[ -n "$LATEST_DIR" && -f "$LATEST_DIR/release.json" ]]; then
  RJ="$LATEST_DIR/release.json"
  echo "version:      $(python3 -c "import json;print(json.load(open('$RJ')).get('version',''))" 2>/dev/null)"
  echo "image_digest: $(python3 -c "import json;print(json.load(open('$RJ')).get('image_digest',''))" 2>/dev/null)"
  echo "source_commit:$(python3 -c "import json;print(json.load(open('$RJ')).get('source_commit',''))" 2>/dev/null)"
  if [[ -f "$LATEST_DIR/checksums.txt" ]]; then
    echo "package sha256 (checksums.txt):"
    sed 's/^/  /' "$LATEST_DIR/checksums.txt"
  fi
  if [[ -f "$LATEST_DIR/PROMOTION.json" ]]; then
    echo "promotion state:"
    python3 -c "import json;d=json.load(open('$LATEST_DIR/PROMOTION.json'));print('  local:          ',d.get('local',{}).get('status'));print('  production_test:',d.get('production_test',{}).get('status'));print('  production:     ',d.get('production',{}).get('status'))" 2>/dev/null
  fi
else
  echo "no release found under artifacts/releases/"
fi
echo

echo "-- DEPLOYED /opt/mesflow/release.json (currently running) --"
if [[ -f /opt/mesflow/release.json ]]; then
  cat /opt/mesflow/release.json
else
  echo "not readable"
fi
echo
echo

echo "===== end status ====="
