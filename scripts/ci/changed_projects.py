#!/usr/bin/env python3
"""CLI: changed-project detection.

Usage:
    scripts/ci/changed-projects --base <ref> --head <ref>
    scripts/ci/changed-projects --dirty          # uncommitted working tree
    echo path/one path/two | scripts/ci/changed-projects --stdin

Maps a set of changed file paths (relative to the workspace root) to
affected project codes, applying (in order):

1. direct match: path is under a managed project's root
2. shared-path expansion: path is under a WORKSPACE.yaml `shared:` path,
   or is one of the root contract files themselves (AGENTS.md,
   WORKSPACE.yaml, or anything under scripts/ci/) -> every managed
   project is affected
3. dependency expansion: a project depending on a directly-affected
   project is also affected

See docs/CI_CD_STANDARD.md section 7 for the normative rule.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from workspace import (
    MANAGED,
    WORKSPACE_ROOT,
    dependents_of,
    discover,
    load_registry,
)

# Paths (relative to workspace root) that count as a shared-contract
# change regardless of what WORKSPACE.yaml's `shared:` block says.
ALWAYS_SHARED_PREFIXES = ("scripts/ci/", "AGENTS.md", "WORKSPACE.yaml")


def _shared_prefixes(registry: dict) -> list[str]:
    prefixes = list(ALWAYS_SHARED_PREFIXES)
    for value in (registry or {}).get("shared", {}).values():
        prefixes.append(str(value).rstrip("/") + "/")
    return prefixes


def _git_diff_names(base: str, head: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=WORKSPACE_ROOT, capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _git_dirty_names() -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=WORKSPACE_ROOT, capture_output=True, text=True, check=True,
    )
    names = []
    for line in out.stdout.splitlines():
        # porcelain format: "XY path" or "XY orig -> new" for renames
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        names.append(path)
    return names


def affected_projects(changed_paths: list[str]) -> dict:
    records = discover()
    managed = [r for r in records if r.status == MANAGED]
    unmanaged = [r for r in records if r.status != MANAGED]
    registry = load_registry()
    shared_prefixes = _shared_prefixes(registry)

    direct: set[str] = set()
    shared_hit = False
    reasons: dict[str, set[str]] = {}
    warnings: list[str] = []

    def mark(code: str, reason: str):
        reasons.setdefault(code, set()).add(reason)

    def under_root(path: str, root: str) -> bool:
        root_prefix = root.rstrip("/") + "/"
        return path == root or path.startswith(root_prefix)

    for path in changed_paths:
        matched_direct = False
        for r in managed:
            if under_root(path, r.root):
                direct.add(r.code)
                mark(r.code, f"direct:{path}")
                matched_direct = True
        if matched_direct:
            continue
        for prefix in shared_prefixes:
            if path == prefix.rstrip("/") or path.startswith(prefix):
                shared_hit = True
                break
        else:
            # Not under any managed project's root and not a shared path --
            # check whether it belongs to a project this workspace knows
            # about but cannot gate CI on (UNMANAGED/INVALID_CONTRACT/
            # UNREGISTERED_CONTRACT). This must never be silent: a real
            # change with no CI gate to run against it is a finding, not
            # nothing (docs/CI_CD_STANDARD.md section 13/15).
            for r in unmanaged:
                if under_root(path, r.root):
                    warnings.append(
                        f"{path}: belongs to project '{r.code}' (status={r.status}) -- "
                        "no managed CI gate runs for it"
                    )
                    break

    affected = set(direct)
    if shared_hit:
        for r in managed:
            affected.add(r.code)
            mark(r.code, "shared-path-expansion")

    # Dependency expansion: iterate to a fixed point (conservative --
    # cheap given the small project count in V1).
    changed_now = set(affected)
    while changed_now:
        next_round: set[str] = set()
        for code in list(changed_now):
            for dependent in dependents_of(records, registry, code):
                if dependent not in affected:
                    affected.add(dependent)
                    mark(dependent, f"dependency-of:{code}")
                    next_round.add(dependent)
        changed_now = next_round

    return {
        "changed_paths": changed_paths,
        "affected_projects": sorted(affected),
        "shared_path_expansion": shared_hit,
        "reasons": {k: sorted(v) for k, v in reasons.items()},
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--base", help="base git ref (use with --head)")
    group.add_argument("--dirty", action="store_true", help="uncommitted working tree changes")
    group.add_argument("--stdin", action="store_true", help="read changed paths from stdin, one per line")
    parser.add_argument("--head", default="HEAD", help="head git ref (default HEAD)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.base:
        paths = _git_diff_names(args.base, args.head)
    elif args.dirty:
        paths = _git_dirty_names()
    else:
        paths = [line.strip() for line in sys.stdin if line.strip()]

    result = affected_projects(paths)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"changed paths: {len(result['changed_paths'])}")
        print(f"shared-path expansion triggered: {result['shared_path_expansion']}")
        print("affected projects:")
        for code in result["affected_projects"]:
            reasons = ", ".join(result["reasons"].get(code, []))
            print(f"  - {code}  ({reasons})")
        if result["warnings"]:
            print("WARNING -- changes with no managed CI gate:")
            for w in result["warnings"]:
                print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
