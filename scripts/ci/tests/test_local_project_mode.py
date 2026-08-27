"""Multi-repo-workspace mode: a project checked out on its own, with no
WORKSPACE.yaml/sibling projects present at all (a child repo's own CI
runner after a normal single-repo checkout) -- see
docs/CI_CD_STANDARD.md's repository-model finding.
"""
import subprocess

import pytest

from workspace import MANAGED, INVALID_CONTRACT, load_local_project


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path, commit_message="init"):
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], path)
    _git(["add", "-A"], path)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", commit_message], path)


def test_load_local_project_reads_project_yaml_with_no_registry_present(tmp_path):
    # No WORKSPACE.yaml anywhere -- this is the whole point of local mode.
    (tmp_path / "PROJECT.yaml").write_text(
        "schema_version: 1\nproject:\n  code: solo\nsource:\n  root: .\n"
        "version:\n  file: VERSION.txt\ncommands:\n  test:\n    command: \"true\"\n",
        encoding="utf-8",
    )
    (tmp_path / "VERSION.txt").write_text("3.2.1", encoding="utf-8")

    record = load_local_project(tmp_path)
    assert record.status == MANAGED
    assert record.code == "solo"
    assert record.root == "."


def test_load_local_project_invalid_when_project_yaml_missing(tmp_path):
    record = load_local_project(tmp_path)
    assert record.status == INVALID_CONTRACT


def test_load_local_project_flags_code_mismatch(tmp_path):
    (tmp_path / "PROJECT.yaml").write_text(
        "schema_version: 1\nproject:\n  code: solo\nsource:\n  root: .\ncommands: {}\n",
        encoding="utf-8",
    )
    record = load_local_project(tmp_path, expected_code="not-solo")
    assert record.status == INVALID_CONTRACT
    assert any("does not match expected" in i for i in record.issues)


def test_artifact_git_sha_is_the_projects_own_repo_head_not_an_outer_workspace_sha(tmp_path):
    # The regression this specifically guards: in the real multi-repo
    # workspace, mesflow/ (and qa-center/, etc.) are independent git repos
    # nested under the outer workspace repo. A release manifest must never
    # report the OUTER workspace's commit SHA for a project's own artifact.
    from release_manifest import build_manifest

    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / "WORKSPACE.yaml").write_text("workspace:\n  code: demo\n", encoding="utf-8")
    _init_repo(outer, "outer commit")
    outer_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=outer, capture_output=True, text=True, check=True,
    ).stdout.strip()

    project = outer / "alpha"
    project.mkdir()
    (project / "PROJECT.yaml").write_text(
        "schema_version: 1\nproject:\n  code: alpha\nsource:\n  root: .\n"
        "version:\n  file: VERSION.txt\ncommands: {}\n",
        encoding="utf-8",
    )
    (project / "VERSION.txt").write_text("9.9.9", encoding="utf-8")
    _init_repo(project, "alpha's own first commit")
    alpha_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True,
    ).stdout.strip()

    assert alpha_sha != outer_sha  # the two repos really do have different history

    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    artifact = artifact_dir / "alpha-9.9.9.deploy.zip"
    artifact.write_bytes(b"zip")

    manifest = build_manifest("alpha", artifact, local=True, root=project)
    assert manifest["git_sha"] == alpha_sha
    assert manifest["git_sha"] != outer_sha
