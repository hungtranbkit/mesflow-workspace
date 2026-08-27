#!/usr/bin/env python3
"""CLI: generic per-project stage runner.

Usage:
    scripts/ci/run-project <project-code> --stage test
    scripts/ci/run-project <project-code> --stage preflight --stage test

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

from workspace import WORKSPACE_ROOT, discover, project_by_code, required_stages


def run_stage(record, stage: str) -> tuple[str, int]:
    contract = record.contract or {}
    commands = contract.get("commands") or {}
    spec = commands.get(stage)
    if not spec:
        return "STAGE_NOT_DECLARED", 0

    command = spec.get("command")
    working_directory = spec.get("working_directory", ".")
    timeout = spec.get("timeout_seconds")

    cwd = (WORKSPACE_ROOT / record.root / working_directory).resolve()
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
    args = parser.parse_args(argv)

    records = discover()
    record = project_by_code(records, args.project)
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
        _, rc = run_stage(record, stage)
        exit_code = exit_code or rc
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
