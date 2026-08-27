#!/usr/bin/env python3
"""CLI: locate a project's just-built release artifact on disk.

Usage (workspace/discover mode):
    scripts/ci/locate-artifact <project-code>

Usage (local/single-project mode, e.g. a child repo's own release CI):
    scripts/ci/locate-artifact <project-code> --local --root .

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
from workspace import WORKSPACE_ROOT, discover, load_local_project, project_by_code


def locate(project_code: str, root: Path = WORKSPACE_ROOT, local: bool = False) -> Path:
    if local:
        record = load_local_project(root, expected_code=project_code)
        project_root = root
    else:
        records = discover(root)
        record = project_by_code(records, project_code)
        project_root = (root / record.root) if record else None

    if record is None or record.status != "MANAGED":
        raise SystemExit(f"NOT_MANAGED_OR_UNKNOWN_PROJECT: {project_code}")

    contract = record.contract or {}
    version_block = contract.get("version") or {}
    if "file" not in version_block:
        raise SystemExit(
            "NON_PLAIN_VERSION_SCHEME: this project's version is not a plain "
            "file (e.g. firmware source_define) -- locate its artifact manually."
        )

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
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else (Path(".").resolve() if args.local else WORKSPACE_ROOT)
    print(locate(args.project, root=root, local=args.local))
    return 0


if __name__ == "__main__":
    sys.exit(main())
