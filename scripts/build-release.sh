#!/usr/bin/env bash
# Top-level convenience wrapper: build a MESFlow release from the workspace
# source (workspace/mesflow), producing an immutable image + release ZIP
# under artifacts/releases/<version>/. Never touches /opt or any deployed
# environment. See mesflow/scripts/build-release.sh for the real logic.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/mesflow/scripts/build-release.sh" "$@"
