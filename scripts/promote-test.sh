#!/usr/bin/env bash
# Promote the SAME artifact that passed LOCAL_PASS to the PRODUCTION_TEST
# Deploy Agent. Never rebuilds source; uploads the exact release bundle
# produced by scripts/build-release.sh and deploys it with --no-build (see
# docs/operations/IMAGE_RELEASE_CONTRACT.md for the server-side guarantee).
#
# This intentionally has NO production-test counterpart for PRODUCTION —
# promoting to real Production always requires a human clicking the gated
# button in the Release Manager UI after LOCAL_PASS + TEST_PASS + matching
# ZIP SHA/digest/schema. There is no promote-production.sh.
#
# Env:
#   RELEASE_DIR       artifacts/releases/<version> to promote (default:
#                      latest by mtime)
#   TARGET_AGENT_URL  e.g. https://deploy.mesflow.net/agent  (required)
#   TARGET_USER       default admin
#   TARGET_PASSWORD   required
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RELEASE_DIR="${RELEASE_DIR:-}"
if [[ -z "$RELEASE_DIR" ]]; then
  RELEASE_DIR="$(ls -1dt "$ROOT"/artifacts/releases/*/ 2>/dev/null | grep -v TEMPLATE | head -1 || true)"
fi
[[ -n "$RELEASE_DIR" && -f "$RELEASE_DIR/release.json" ]] || { echo "No release found (set RELEASE_DIR=artifacts/releases/<version>)" >&2; exit 1; }

: "${TARGET_AGENT_URL:?Set TARGET_AGENT_URL, e.g. https://deploy.mesflow.net/agent}"
TARGET_USER="${TARGET_USER:-admin}"
: "${TARGET_PASSWORD:?Set TARGET_PASSWORD to the target Agent admin password}"

VERSION="$(python3 -c "import json;print(json.load(open('$RELEASE_DIR/release.json'))['version'])")"
DIGEST="$(python3 -c "import json;print(json.load(open('$RELEASE_DIR/release.json')).get('image_digest',''))")"
ZIP="$(ls "$RELEASE_DIR"/*.deploy.zip "$RELEASE_DIR"/*.zip 2>/dev/null | head -1 || true)"
[[ -n "$ZIP" && -f "$ZIP" ]] || { echo "No release ZIP under $RELEASE_DIR" >&2; exit 1; }
ZIP_SHA="$(sha256sum "$ZIP" | awk '{print $1}')"

echo "Promoting release:"
echo "  version:    $VERSION"
echo "  image_digest: $DIGEST"
echo "  zip:        $ZIP"
echo "  zip sha256: $ZIP_SHA"

if [[ -f "$RELEASE_DIR/PROMOTION.json" ]]; then
  LOCAL_STATUS="$(python3 -c "import json;print(json.load(open('$RELEASE_DIR/PROMOTION.json')).get('local',{}).get('status'))")"
  if [[ "$LOCAL_STATUS" != "success" && "$LOCAL_STATUS" != "LOCAL_PASS" ]]; then
    echo "REFUSING: this release's PROMOTION.json does not show LOCAL_PASS (status=$LOCAL_STATUS)." >&2
    echo "Run scripts/deploy-local.sh and verify LOCAL_PASS before promoting to test." >&2
    exit 1
  fi
else
  echo "WARNING: no PROMOTION.json found next to the release; cannot confirm LOCAL_PASS automatically." >&2
  echo "Proceeding only because you invoked this script explicitly." >&2
fi

JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT
echo "Logging in to $TARGET_AGENT_URL ..."
LOGIN_PAGE="$(curl -fsS -c "$JAR" "$TARGET_AGENT_URL/login")"
# The login form itself carries no CSRF field (only authenticated pages
# do) -- `|| true` so `set -o pipefail` doesn't treat "no match" as fatal
# and silently abort before the actual login POST below.
CSRF="$(printf '%s' "$LOGIN_PAGE" | grep -oP 'name="csrf" value="\K[^"]+' | head -1 || true)"
# Sending an explicit but empty `csrf=` field (as opposed to omitting the
# field entirely, what a real browser does when the form has no such
# hidden input) makes some Agent versions reject the login silently -- no
# Set-Cookie, no error body, just a 302 back to /login (confirmed by hand
# against the real Production Test Agent, 2.24.37, while running this
# task -- the newer 2.24.49 tolerates it, but don't rely on that). Only
# include the field when a real token was actually found.
CSRF_ARGS=()
[[ -n "$CSRF" ]] && CSRF_ARGS=(--data-urlencode "csrf=$CSRF")
curl -fsS -b "$JAR" -c "$JAR" -o /dev/null \
  --data-urlencode "username=$TARGET_USER" \
  --data-urlencode "password=$TARGET_PASSWORD" \
  "${CSRF_ARGS[@]}" \
  "$TARGET_AGENT_URL/login"
PAGE="$(curl -fsS -b "$JAR" "$TARGET_AGENT_URL/")"
CSRF2="$(printf '%s' "$PAGE" | grep -oP 'name="csrf" value="\K[^"]+' | head -1)"
[[ -n "$CSRF2" ]] || { echo "Login to target Agent failed (no session/csrf obtained)" >&2; exit 1; }

echo "Uploading $ZIP (unchanged bytes, sha256=$ZIP_SHA) ..."
curl -fsS -b "$JAR" -X POST \
  -H "X-CSRF-Token: $CSRF2" \
  -F "csrf=$CSRF2" -F "release_zip=@${ZIP}" \
  "$TARGET_AGENT_URL/upload"

echo "Deploying $VERSION on target (server enforces --no-build for image releases; see IMAGE_RELEASE_CONTRACT.md) ..."
curl -fsS -b "$JAR" -X POST \
  -H "X-CSRF-Token: $CSRF2" \
  -F "csrf=$CSRF2" \
  "$TARGET_AGENT_URL/deploy/$VERSION"

echo
echo "Now verify manually before calling this TEST_PASS:"
echo "  - target /health and /version report $VERSION"
echo "  - target release.json image_digest == $DIGEST"
echo "  - schema: expected == actual"
echo "  - browser smoke test on the target"
echo "Production promotion is a separate, human-approved action — this script does not do it."
