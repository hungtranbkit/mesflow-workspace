#!/usr/bin/env python3
"""CLI: enforce the same-artifact rule (docs/CI_CD_STANDARD.md section 4).

Usage:
    scripts/ci/same-artifact-check <test-manifest.json> <production-manifest.json>

Exits 0 and prints PRODUCTION_ALLOWED only if both manifests' project and
sha256 match exactly. Otherwise exits 1 and prints PRODUCTION_BLOCKED with
the reason -- this is never a warning, it is a hard gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def check(test_manifest: dict, prod_manifest: dict) -> tuple[bool, str]:
    if test_manifest.get("project") != prod_manifest.get("project"):
        return False, (
            f"project mismatch: test={test_manifest.get('project')} "
            f"production={prod_manifest.get('project')}"
        )
    test_sha = test_manifest.get("sha256")
    prod_sha = prod_manifest.get("sha256")
    if not test_sha or not prod_sha:
        return False, "missing sha256 in one or both manifests"
    if test_sha != prod_sha:
        return False, f"sha256 mismatch: test={test_sha} production={prod_sha}"
    return True, "sha256 matches"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test_manifest")
    parser.add_argument("production_manifest")
    args = parser.parse_args(argv)

    test_manifest = json.loads(Path(args.test_manifest).read_text(encoding="utf-8"))
    prod_manifest = json.loads(Path(args.production_manifest).read_text(encoding="utf-8"))

    ok, reason = check(test_manifest, prod_manifest)
    if ok:
        print(f"PRODUCTION_ALLOWED: {reason}")
        return 0
    print(f"PRODUCTION_BLOCKED: {reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
