#!/usr/bin/env bash
# Submit release-local-qa.sh's evidence JSON to the local Deploy Agent's
# structured QA callback (POST /api/release-manager/evidence/<version>/runs)
# so PROMOTION.json's local.status flips from AWAITING_QA to success --
# the Agent deliberately never accepts a manual boolean PASS (agent.py's
# own comment on that route), it must be given real checks/counts.
#
# Env:
#   AGENT_URL       default http://127.0.0.1:8090/agent
#   AGENT_USER      default admin
#   AGENT_PASSWORD  required
#   VERSION         required (must match a real artifacts/qa/<version>/release-local/release-local-qa.json)
set -Eeuo pipefail
AGENT_URL="${AGENT_URL:-http://127.0.0.1:8090/agent}"
AGENT_USER="${AGENT_USER:-admin}"
: "${AGENT_PASSWORD:?Set AGENT_PASSWORD to the local Agent admin password}"
: "${VERSION:?Set VERSION, e.g. 71.0.0.208}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QA_JSON="$ROOT/artifacts/qa/$VERSION/release-local/release-local-qa.json"
[[ -f "$QA_JSON" ]] || { echo "No QA evidence at $QA_JSON -- run mesflow/scripts/release-local-qa.sh first" >&2; exit 1; }

JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT
LOGIN_PAGE="$(curl -fsS -c "$JAR" "$AGENT_URL/login")"
CSRF="$(printf '%s' "$LOGIN_PAGE" | grep -oP 'name="csrf" value="\K[^"]+' | head -1 || true)"
CSRF_ARGS=(); [[ -n "$CSRF" ]] && CSRF_ARGS=(--data-urlencode "csrf=$CSRF")
curl -fsS -b "$JAR" -c "$JAR" -o /dev/null \
  --data-urlencode "username=$AGENT_USER" --data-urlencode "password=$AGENT_PASSWORD" \
  "${CSRF_ARGS[@]}" "$AGENT_URL/login"
PAGE="$(curl -fsS -b "$JAR" "$AGENT_URL/")"
CSRF2="$(printf '%s' "$PAGE" | grep -oP 'name="csrf" value="\K[^"]+' | head -1)"
[[ -n "$CSRF2" ]] || { echo "Login failed (no session/csrf obtained)" >&2; exit 1; }

PAYLOAD="$(python3 - "$QA_JSON" <<'PY'
import json,sys,uuid
d=json.load(open(sys.argv[1]))
steps=d.get("steps",{})
checks=[{"name":name,"status":info.get("status","ERROR"),"required":True,"message":info.get("detail","")}
        for name,info in steps.items()]
passed=sum(1 for c in checks if c["status"]=="PASS")
payload={
    "run_id":f"release-local-qa-{d['version']}-{uuid.uuid4().hex[:8]}",
    "environment":"LOCAL",
    "profile":"release-local-qa",
    "status":d.get("overall","ERROR"),
    "artifact_digest":d["artifact"]["image_digest"],
    "started_at":d.get("started_at",""),
    "finished_at":d.get("finished_at",""),
    "checks":checks,
    "total_tests":len(checks),
    "passed_tests":passed,
    "failed_tests":len(checks)-passed,
    "skipped_tests":0,
    "target_url":"http://127.0.0.1:18280",
    "report_path":f"artifacts/qa/{d['version']}/release-local/release-local-qa.json",
    "log_path":f"artifacts/qa/{d['version']}/release-local/logs",
}
print(json.dumps(payload))
PY
)"

echo "Submitting LOCAL QA evidence for $VERSION ..."
curl -fsS -b "$JAR" -X POST \
  -H "X-CSRF-Token: $CSRF2" -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "$AGENT_URL/api/release-manager/evidence/$VERSION/runs"
echo
