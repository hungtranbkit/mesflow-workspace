"""Shared fixtures for the CI foundation's own test suite.

Every test builds a small synthetic workspace tree under tmp_path so
these tests are deterministic and independent of the real (very messy,
pre-existing) workspace state -- see the CI/CD audit report for why the
real workspace has a lot of unrelated dirty state that must not leak into
this suite.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


@pytest.fixture
def fake_workspace(tmp_path: Path) -> Path:
    """A minimal, valid two-project workspace: alpha (has good contract),
    beta (depends on alpha), plus an unmanaged project and a stray dir
    that must NOT be classified as a project."""
    root = tmp_path

    _write(root / "WORKSPACE.yaml", """\
        schema_version: 1
        workspace:
          code: demo
          name: Demo Workspace
        projects:
          - code: alpha
            name: Alpha
            root: alpha
            manifest: alpha/PROJECT.yaml
          - code: beta
            name: Beta
            root: beta
            manifest: beta/PROJECT.yaml
        shared:
          docs: docs
          reports: reports
        dependencies:
          - source: beta
            target: alpha
            type: TEST
            evidence: "synthetic fixture"
        """)

    _write(root / "alpha" / "PROJECT.yaml", """\
        schema_version: 1
        project:
          code: alpha
          name: Alpha
          type: WEB_APP
          role: APPLICATION
        source:
          root: .
        version:
          file: VERSION.txt
        commands:
          preflight:
            command: "true"
            working_directory: .
          test:
            command: "true"
            working_directory: .
        artifacts:
          strategy: immutable
          directory: ../artifacts/alpha
        """)
    _write(root / "alpha" / "VERSION.txt", "1.0.0")

    _write(root / "beta" / "PROJECT.yaml", """\
        schema_version: 1
        project:
          code: beta
          name: Beta
          type: SERVICE
          role: TEST_ORCHESTRATOR
        source:
          root: .
        version:
          file: VERSION.txt
        commands:
          test:
            command: "true"
            working_directory: .
        dependencies:
          - target: alpha
            type: TEST
        """)
    _write(root / "beta" / "VERSION.txt", "0.1.0")

    # Real project directory with no PROJECT.yaml at all -- UNMANAGED.
    _write(root / "gamma" / "AGENTS.md", "# gamma\n")

    # Non-project shared/config dir with zero lifecycle signals -- must
    # never show up in discovery at all.
    (root / "nginx").mkdir()
    (root / "nginx" / "nginx.conf").write_text("# not a project\n", encoding="utf-8")

    (root / "docs").mkdir()
    (root / "reports").mkdir()

    # release_manifest._git_sha needs a real git repo to bind an artifact
    # to (matching every real project in the actual workspace, which is
    # always inside a git repo) -- give the fixture a trivial one.
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=test",
         "commit", "-q", "-m", "init"],
        cwd=root, check=True,
    )

    return root
