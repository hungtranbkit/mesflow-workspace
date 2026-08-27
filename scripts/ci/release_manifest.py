#!/usr/bin/env python3
"""CLI: compute an immutable release manifest for one project's artifact.

Usage:
    scripts/ci/release-manifest <project-code> <artifact-path> [--out FILE]

Prints (and optionally writes) a manifest matching
docs/CI_CD_STANDARD.md section 12:

    {
      "project": "...",
      "version": "...",
      "git_sha": "...",
      "artifact": "...",
      "sha256": "...",
      "built_at": "...",
      "builder": "..."
    }

This is a workspace-level convenience -- it does not build anything and
does not replace a project's own build script. `version` is read from
whatever `PROJECT.yaml`'s `version:` block declares (a plain file, or a
firmware `source_define` regex) so it never becomes a second source of
truth for version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from workspace import WORKSPACE_ROOT, project_by_code, discover


def _read_version(record, project_root: Path) -> str:
    version_block = (record.contract or {}).get("version") or {}

    if "file" in version_block:
        version_file = project_root / version_block["file"]
        return version_file.read_text(encoding="utf-8").strip()

    if "source_define" in version_block:
        spec = version_block["source_define"]
        text = (project_root / spec["file"]).read_text(encoding="utf-8")
        match = re.search(spec["pattern"], text)
        if not match:
            raise ValueError(f"version pattern did not match in {spec['file']}")
        return match.group(1)

    raise ValueError("PROJECT.yaml version: block has neither 'file' nor 'source_define'")


def _git_sha(project_root: Path, workspace_root: Path) -> str:
    # Prefer the project's own repo HEAD if it is an independent git repo;
    # fall back to the workspace repo's HEAD otherwise.
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project_root,
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=workspace_root,
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    project_code: str, artifact_path: Path, builder: str = "local", root: Path = WORKSPACE_ROOT
) -> dict:
    records = discover(root)
    record = project_by_code(records, project_code)
    if record is None or record.status != "MANAGED":
        raise SystemExit(f"NOT_MANAGED_OR_UNKNOWN_PROJECT: {project_code}")
    if not artifact_path.exists():
        raise SystemExit(f"ARTIFACT_NOT_FOUND: {artifact_path}")

    project_root = root / record.root
    return {
        "project": record.code,
        "version": _read_version(record, project_root),
        "git_sha": _git_sha(project_root, root),
        "artifact": artifact_path.name,
        "sha256": sha256_of(artifact_path),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "builder": builder,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("artifact_path")
    parser.add_argument("--builder", default=os.environ.get("CI_BUILDER", "local"))
    parser.add_argument("--out", help="write manifest JSON to this file too")
    args = parser.parse_args(argv)

    manifest = build_manifest(args.project, Path(args.artifact_path).resolve(), args.builder)
    text = json.dumps(manifest, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
