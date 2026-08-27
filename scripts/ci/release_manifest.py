#!/usr/bin/env python3
"""CLI: compute an immutable release manifest for one project's artifact.

Usage (workspace/discover mode):
    scripts/ci/release-manifest <project-code> <artifact-path> [--out FILE]

Usage (local/single-project mode, e.g. a child repo's own release CI):
    scripts/ci/release-manifest <project-code> <artifact-path> --local --root .

Prints (and optionally writes) a manifest matching
docs/CI_CD_STANDARD.md section 12:

    {
      "project": "...",
      "version": "...",
      "git_sha": "...",
      "artifact": "...",
      "sha256": "...",
      "built_at": "...",
      "builder": "...",
      "dirty": false,
      "release_type": "RELEASE" | "NON_RELEASE"
    }

This is a workspace-level convenience -- it does not build anything and
does not replace a project's own build script. `version` is read from
whatever `PROJECT.yaml`'s `version:` block declares (a plain file, or a
firmware `source_define` regex) so it never becomes a second source of
truth for version. `git_sha` is always the PROJECT's own repository HEAD
(never the outer workspace repo's SHA when the project is an independent
nested repo -- see docs/CI_CD_STANDARD.md section 17).

Dirty-tree policy (docs/CI_CD_STANDARD.md section 18): by default this
refuses to build a manifest from a project tree with uncommitted changes
(`DIRTY_TREE_BLOCKED`) -- an official release must come from clean,
committed source at an exact commit. Pass --allow-dirty for a local/dev
build only; the manifest is then marked `"dirty": true,
"release_type": "NON_RELEASE"` so it can never be mistaken for an
official release artifact.
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

from workspace import WORKSPACE_ROOT, load_local_project, project_by_code, discover


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


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _git_sha(project_root: Path, workspace_root: Path) -> str:
    # Prefer the project's own repo HEAD if it is an independent git repo;
    # fall back to the workspace repo's HEAD otherwise. Never silently
    # returns the wrong repo's SHA -- if project_root IS its own repo (the
    # multi-repo-workspace case), that HEAD is used, full stop.
    try:
        return _run_git(["rev-parse", "HEAD"], project_root).stdout.strip()
    except subprocess.CalledProcessError:
        return _run_git(["rev-parse", "HEAD"], workspace_root).stdout.strip()


def _is_dirty(project_root: Path, workspace_root: Path) -> bool:
    # Same repo-boundary preference as _git_sha: check the project's own
    # repo if it is one, otherwise the workspace repo.
    for cwd in (project_root, workspace_root):
        try:
            out = _run_git(["status", "--porcelain"], cwd)
            return bool(out.stdout.strip())
        except subprocess.CalledProcessError:
            continue
    raise SystemExit("GIT_STATUS_UNAVAILABLE: neither project nor workspace root is a git repository")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    project_code: str,
    artifact_path: Path,
    builder: str = "local",
    root: Path = WORKSPACE_ROOT,
    local: bool = False,
    allow_dirty: bool = False,
) -> dict:
    if local:
        record = load_local_project(root, expected_code=project_code)
        project_root = root
    else:
        records = discover(root)
        record = project_by_code(records, project_code)
        project_root = (root / record.root) if record else None

    if record is None or record.status != "MANAGED":
        raise SystemExit(f"NOT_MANAGED_OR_UNKNOWN_PROJECT: {project_code}")
    if not artifact_path.exists():
        raise SystemExit(f"ARTIFACT_NOT_FOUND: {artifact_path}")

    dirty = _is_dirty(project_root, root)
    if dirty and not allow_dirty:
        raise SystemExit(
            f"DIRTY_TREE_BLOCKED: {project_root} has uncommitted changes. "
            "An official release manifest must be built from a clean, "
            "committed source tree at an exact commit (docs/CI_CD_STANDARD.md "
            "section 18). Pass --allow-dirty for a local/dev, NON_RELEASE build."
        )

    return {
        "project": record.code,
        "version": _read_version(record, project_root),
        "git_sha": _git_sha(project_root, root),
        "artifact": artifact_path.name,
        "sha256": sha256_of(artifact_path),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "builder": builder,
        "dirty": dirty,
        "release_type": "NON_RELEASE" if dirty else "RELEASE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("artifact_path")
    parser.add_argument("--builder", default=os.environ.get("CI_BUILDER", "local"))
    parser.add_argument("--out", help="write manifest JSON to this file too")
    parser.add_argument("--local", action="store_true", help="single-project mode, see module docstring")
    parser.add_argument("--root", default=None, help="(--local only) checked-out project root, default '.'")
    parser.add_argument(
        "--allow-dirty", action="store_true",
        help="allow building a manifest from an uncommitted/dirty tree "
             "(marks it dirty=true, release_type=NON_RELEASE) instead of "
             "blocking -- for local/dev builds only, never an official release",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else (Path(".").resolve() if args.local else WORKSPACE_ROOT)
    manifest = build_manifest(
        args.project, Path(args.artifact_path).resolve(), args.builder,
        root=root, local=args.local, allow_dirty=args.allow_dirty,
    )
    text = json.dumps(manifest, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
