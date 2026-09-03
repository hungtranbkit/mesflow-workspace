#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
ROOT="$(cd "$(dirname "$SCRIPT_SOURCE")/.." && pwd)"
PROFILE="${1:-}"
case "$PROFILE" in local|production-test) ;; *) echo "Usage: $0 local|production-test" >&2; exit 2;; esac
fail=0; warn=0; passed=0
pass(){ echo "PASS  $*"; passed=$((passed+1)); }
warning(){ echo "WARN  $*"; warn=$((warn+1)); }
bad(){ echo "FAIL  $*"; fail=$((fail+1)); }
command -v docker >/dev/null && pass "Docker CLI available" || bad "Docker CLI missing"
docker info >/dev/null 2>&1 && pass "Docker daemon reachable" || bad "Docker daemon unavailable"
docker compose version >/dev/null 2>&1 && pass "Docker Compose available" || bad "Docker Compose missing"
[[ "$(uname -m)" =~ ^(x86_64|amd64)$ ]] && pass "Architecture $(uname -m)" || warning "Architecture $(uname -m) requires compatibility review"
docker network inspect mesflow-edge >/dev/null 2>&1 && pass "Network mesflow-edge exists" || bad "Network mesflow-edge missing"
for d in /opt/mesflow /opt/mesflow/runtime /opt/mesflow/runtime/tutorials /opt/mesflow/runtime/tutorials/esp-kiosk /opt/mesflow/runtime/backups; do
  [[ -d "$d" ]] && pass "Directory $d" || bad "Directory missing: $d"
done
container_keys(){ docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$1" 2>/dev/null | sed 's/=.*//' || true; }
envfile=/opt/mesflow/.env
if [[ -f "$envfile" ]]; then
  mode="$(stat -c %a "$envfile")"; [[ "$mode" == 600 || "$mode" == 640 ]] && pass ".env permissions $mode" || bad ".env permissions $mode (expected 600/640)"
  # Bug found live (2026-09-02): `-f` only needs the parent directory to be
  # searchable, not the file itself readable -- a mode-600 .env owned by a
  # different user (the normal, correct state on a real deploy target)
  # passes `-f` but `sed`/`cat` on it silently returns nothing (2>/dev/null
  # swallows Permission denied), so every key below reported FAIL even
  # though the value was genuinely configured -- a false positive from a
  # permission-model mismatch, not a real missing value. Check readability
  # explicitly; when unreadable, ask the running container instead (it
  # already resolved these from the same .env at create time via
  # env_file:, so this is real evidence, not a guess) rather than reporting
  # "missing" for a file this user was simply never meant to read directly.
  if [[ -r "$envfile" ]]; then
    keys="$(sed -E '/^[[:space:]]*(#|$)/d; s/[[:space:]]*=.*$//' "$envfile" 2>/dev/null || true)"
    for key in POSTGRES_PASSWORD DATABASE_URL MESFLOW_SECRET_KEY MESFLOW_ADMIN_PASSWORD; do
      grep -qx "$key" <<<"$keys" && pass "Required env key $key (from .env)" || bad "Required env key missing from .env: $key"
    done
  else
    app_keys="$(container_keys mesflow-app)"
    for key in POSTGRES_PASSWORD DATABASE_URL MESFLOW_SECRET_KEY MESFLOW_ADMIN_PASSWORD; do
      grep -qx "$key" <<<"$app_keys" && pass "Required env key $key (.env unreadable by this user; verified via mesflow-app's own resolved environment instead)" \
        || bad "Required env key missing: $key (.env unreadable by this user, and not present in mesflow-app's resolved environment either)"
    done
  fi
else bad ".env missing at $envfile"; fi
avail_kb="$(df -Pk / | awk 'NR==2{print $4}')"; [[ "$avail_kb" -ge 10485760 ]] && pass "Disk >= 10 GiB available" || bad "Disk below 10 GiB"
mem_kb="$(awk '/MemTotal/{print $2}' /proc/meminfo)"; [[ "$mem_kb" -ge 4194304 ]] && pass "RAM >= 4 GiB" || bad "RAM below 4 GiB"
for spec in mesflow-app:healthy mesflow-postgres:healthy mesflow-deploy-agent:healthy; do
  c="${spec%%:*}"; expected="${spec##*:}"; actual="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{if .State.Running}}none{{else}}stopped{{end}}{{end}}' "$c" 2>/dev/null || true)"
  [[ "$actual" == "$expected" ]] && pass "$c health=$actual" || bad "$c health=${actual:-missing}, expected=$expected"
done
curl -fsS --max-time 8 http://127.0.0.1:8080/api/system/health >/dev/null && pass "MESFlow health endpoint" || bad "MESFlow health endpoint failed"
curl -fsS --max-time 8 http://127.0.0.1:8080/api/system/version >/dev/null && pass "MESFlow version endpoint" || bad "MESFlow version endpoint failed"
curl -fsS --max-time 8 http://127.0.0.1:8080/api/system/ready >/dev/null && pass "Database/schema readiness" || bad "Database/schema readiness failed"
curl -fsS --max-time 8 http://127.0.0.1:8090/health >/dev/null && pass "Deploy Agent connectivity" || bad "Deploy Agent connectivity failed"
curl -fsS --max-time 8 http://127.0.0.1:8095/api/version >/dev/null && pass "QA Center connectivity" || bad "QA Center connectivity failed"
agent_qa="$(curl -fsS --max-time 8 http://127.0.0.1:8090/health 2>/dev/null | python3 -c 'import json,sys; print("1" if json.load(sys.stdin).get("qa",{}).get("online") else "0")' 2>/dev/null || true)"
[[ "$agent_qa" == 1 ]] && pass "Deploy Agent can reach QA Center" || bad "Deploy Agent cannot reach QA Center"
grep -qx MESFLOW_AGENT_ADMIN_PASSWORD < <(container_keys mesflow-deploy-agent) && pass "Agent secret key is configured" || bad "Agent env key missing: MESFLOW_AGENT_ADMIN_PASSWORD"
qa_container=mesflow-qa-center; docker inspect "$qa_container" >/dev/null 2>&1 || qa_container=mesflow-testcenter
for key in MESFLOW_QA_PROFILE MESFLOW_QA_USERNAME MESFLOW_QA_PASSWORD; do grep -qx "$key" < <(container_keys "$qa_container") && pass "QA env key $key" || bad "QA env key missing: $key"; done
for port in 8080 8090; do
  ss -H -ltn "sport = :$port" 2>/dev/null | grep -q . && pass "Required port $port is listening" || bad "Required port $port is not listening"
done
tz="$(timedatectl show -p Timezone --value 2>/dev/null || true)"; [[ "$tz" == Asia/Ho_Chi_Minh ]] && pass "Host timezone $tz" || warning "Host timezone ${tz:-unknown}; application contract remains Asia/Ho_Chi_Minh"
echo; echo "SUMMARY PASS=$passed WARN=$warn FAIL=$fail"
(( fail == 0 )) || exit 1
