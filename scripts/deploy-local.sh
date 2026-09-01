#!/usr/bin/env bash
# Deploy the latest already-built release through the LOCAL Deploy Agent's
# image-release path. Never rebuilds; deploys the exact frozen artifact
# scripts/build-release.sh produced (`--no-build`).
#
# Requires the local Agent (127.0.0.1:8090 by default) and admin credentials.
#
# Env:
#   AGENT_URL       default http://127.0.0.1:8090/agent
#   AGENT_USER      default admin
#   AGENT_PASSWORD  required (no default — never hardcode a password here)
set -Eeuo pipefail
AGENT_URL="${AGENT_URL:-http://127.0.0.1:8090/agent}"
AGENT_USER="${AGENT_USER:-admin}"
: "${AGENT_PASSWORD:?Set AGENT_PASSWORD to the local Agent admin password}"

JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT

echo "Logging in to $AGENT_URL ..."
LOGIN_PAGE="$(curl -fsS -c "$JAR" "$AGENT_URL/login")"
# The login form itself carries no CSRF field (only authenticated pages
# do) -- `|| true` so `set -o pipefail` doesn't treat "no match" as fatal
# and silently abort before the actual login POST below.
CSRF="$(printf '%s' "$LOGIN_PAGE" | grep -oP 'name="csrf" value="\K[^"]+' | head -1 || true)"
curl -fsS -b "$JAR" -c "$JAR" -o /dev/null \
  --data-urlencode "username=$AGENT_USER" \
  --data-urlencode "password=$AGENT_PASSWORD" \
  --data-urlencode "csrf=$CSRF" \
  "$AGENT_URL/login"

PAGE="$(curl -fsS -b "$JAR" "$AGENT_URL/")"
CSRF2="$(printf '%s' "$PAGE" | grep -oP 'name="csrf" value="\K[^"]+' | head -1)"
[[ -n "$CSRF2" ]] || { echo "Login failed (no session/csrf obtained)" >&2; exit 1; }

echo "Triggering Deploy Local (no-build, exact frozen artifact) ..."
curl -fsS -b "$JAR" -X POST \
  -H "X-CSRF-Token: $CSRF2" -H "X-Requested-With: XMLHttpRequest" \
  "$AGENT_URL/api/release-manager/deploy-local"
echo
echo "Check status: curl -s $AGENT_URL/api/release-manager (with the same session)"
echo "Or open $AGENT_URL/ in a browser to watch LOCAL_PASS."
