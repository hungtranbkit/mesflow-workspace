#!/usr/bin/env python3
"""CLI: locate a project's just-built release artifact on disk.

Usage:
    scripts/ci/locate-artifact <project-code>

Prints the absolute path to the single `*.deploy.zip` under
`<artifacts.directory>/<version>/` for that project, per its own
PROJECT.yaml `version:`/`artifacts:` blocks. Exits non-zero with a clear
message if the version scheme is not a plain file (e.g. firmware
`source_define`), the artifacts directory does not exist, or there is not
exactly one matching artifact.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from release_manifest import _read_version
from workspace import WORKSPACE_ROOT, discover, project_by_code


def locate(project_code: str, root: Path = WORKSPACE_ROOT) -> Path:
    records = discover(root)
    record = project_by_code(records, project_code)
    if record is None or record.status != "MANAGED":
        raise SystemExit(f"NOT_MANAGED_OR_UNKNOWN_PROJECT: {project_code}")

    contract = record.contract or {}
    version_block = contract.get("version") or {}
    if "file" not in version_block:
        raise SystemExit(
            "NON_PLAIN_VERSION_SCHEME: this project's version is not a plain "
            "file (e.g. firmware source_define) -- locate its artifact manually."
        )

    project_root = root / record.root
    version = _read_version(record, project_root)
    artifacts_block = contract.get("artifacts") or {}
    artifacts_dir = (project_root / artifacts_block.get("directory", ".")).resolve()
    version_dir = artifacts_dir / version
    if not version_dir.is_dir():
        raise SystemExit(f"ARTIFACT_DIR_NOT_FOUND: {version_dir}")

    matches = sorted(version_dir.glob("*.deploy.zip"))
    if not matches:
        raise SystemExit(f"NO_ARTIFACT_FOUND: no *.deploy.zip under {version_dir}")
    if len(matches) > 1:
        raise SystemExit(f"AMBIGUOUS_ARTIFACT: multiple *.deploy.zip under {version_dir}: {matches}")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    args = parser.parse_args(argv)
    print(locate(args.project))
    return 0


if __name__ == "__main__":
    sys.exit(main())
