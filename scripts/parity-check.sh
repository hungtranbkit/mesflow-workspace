#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-}"
case "$PROFILE" in local|production-test) ;; *) echo "Usage: $0 local|production-test" >&2; exit 2;; esac
OUT="$ROOT/reports/environment/${PROFILE}.json"
echo "MESFlow environment parity: $PROFILE"
preflight_rc=0
"$ROOT/scripts/environment-preflight.sh" "$PROFILE" || preflight_rc=$?
python3 "$ROOT/scripts/environment-fingerprint.py" "$PROFILE" --output "$OUT"
echo "Fingerprint               PASS ($OUT)"
if (( preflight_rc != 0 )); then echo; echo "NOT READY FOR PROMOTION"; exit "$preflight_rc"; fi
echo; echo "ENVIRONMENT PREFLIGHT PASS"
