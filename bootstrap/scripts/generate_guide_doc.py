#!/usr/bin/env python3
"""Regenerate bootstrap/docs/MESFLOW_SERVER_DEPLOYMENT_GUIDE.md from
bootstrap/guide_content.py (the single source of truth for both the
Markdown runbook and the Bootstrap web page /guide/deployment).

Usage:
    python3 bootstrap/scripts/generate_guide_doc.py

Run this every time guide_content.py changes; never hand-edit the .md
output directly or it will drift from the web page.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import guide_content  # noqa: E402

OUT_FILE = ROOT / "docs" / "MESFLOW_SERVER_DEPLOYMENT_GUIDE.md"


def main() -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(guide_content.render_markdown(), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
