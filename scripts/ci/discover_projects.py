#!/usr/bin/env python3
"""CLI: workspace project discovery.

Usage:
    scripts/ci/discover-projects            # human table
    scripts/ci/discover-projects --json      # machine-readable

Exit code is always 0 -- discovery reporting an UNMANAGED/INVALID_CONTRACT
project is information, not a CI failure by itself (see
docs/CI_CD_STANDARD.md section 13 for the policy on when that DOES fail
CI).
"""
from __future__ import annotations

import argparse
import json
import sys

from workspace import discover


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    records = discover()

    if args.json:
        print(json.dumps([r.to_dict() for r in records], indent=2))
        return 0

    width = max((len(r.code) for r in records), default=10)
    for r in records:
        line = f"{r.code:<{width}}  {r.status:<22} root={r.root}"
        if r.issues:
            line += "  [" + "; ".join(r.issues) + "]"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
