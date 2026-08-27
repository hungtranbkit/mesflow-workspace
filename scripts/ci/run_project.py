#!/usr/bin/env python3
"""CLI: generic per-project stage runner.

Usage (workspace/discover mode -- this repo contains every project as a
sibling directory, e.g. local dev on this machine):
    scripts/ci/run-project <project-code> --stage test
    scripts/ci/run-project <project-code> --stage preflight --stage test

Usage (local/single-project mode -- a child repo's own CI, where only
that one project's source is checked out, per docs/CI_CD_STANDARD.md's
multi-repo-workspace architecture):
    scripts/ci/run-project <project-code> --local --root .

Invokes exactly the command that project's own PROJECT.yaml declares for
each stage (`commands.<stage>.command`), from that project's own root +
`working_directory`. Never hard-codes a project's implementation here --
if a project's contract changes, this runner's behavior changes with it,
automatically.

Exit codes:
    0   every requested stage either passed or was not declared (reported,
        not silently treated as passed -- see the printed
        "STAGE_NOT_DECLARED" marker)
    1   a requested stage was declared and failed
    2   the project code is unknown, or its contract is invalid
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from workspace import WORKSPACE_ROOT, discover, load_local_project, project_by_code, required_stages


def run_stage(record, project_source_root: Path, stage: str) -> tuple[str, int]:
    contract = record.contract or {}
    commands = contract.get("commands") or {}
    spec = commands.get(stage)
    if not spec:
        return "STAGE_NOT_DECLARED", 0

    command = spec.get("command")
    working_directory = spec.get("working_directory", ".")
    timeout = spec.get("timeout_seconds")

    cwd = (project_source_root / working_directory).resolve()
    print(f"===== {record.code} :: {stage} =====")
    print(f"$ {command}   (cwd={cwd})")
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"STAGE_TIMEOUT after {timeout}s")
        return "STAGE_TIMEOUT", 1
    status = "STAGE_PASSED" if result.returncode == 0 else "STAGE_FAILED"
    print(f"{status} (exit={result.returncode})")
    return status, result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="project code, e.g. mesflow-app")
    parser.add_argument(
        "--stage", action="append", dest="stages",
        help="stage to run; may repeat. Omit to run every stage in this "
             "project's required CI gates (PROJECT.yaml ci.required, or "
             "the preflight/test fallback -- see workspace.required_stages).",
    )
    parser.add_argument(
        "--local", action="store_true",
        help="single-project mode: read PROJECT.yaml directly from --root, "
             "ignore WORKSPACE.yaml/sibling-project discovery entirely. Use "
             "this from a child repo's own CI (see docs/CI_CD_STANDARD.md).",
    )
    parser.add_argument(
        "--root", default=".",
        help="(--local only) the checked-out project root, default '.'",
    )
    args = parser.parse_args(argv)

    if args.local:
        project_source_root = Path(args.root).resolve()
        record = load_local_project(project_source_root, expected_code=args.project)
    else:
        records = discover()
        record = project_by_code(records, args.project)
        project_source_root = WORKSPACE_ROOT / record.root if record else None

    if record is None:
        print(f"UNKNOWN_PROJECT: {args.project}")
        return 2
    if record.status != "MANAGED":
        print(f"NOT_MANAGED: {args.project} (status={record.status}, issues={record.issues})")
        return 2

    stages = args.stages or required_stages(record)
    if not stages:
        print(f"NO_REQUIRED_STAGES_DECLARED: {args.project}")
        return 0

    exit_code = 0
    for stage in stages:
        _, rc = run_stage(record, project_source_root, stage)
        exit_code = exit_code or rc
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
