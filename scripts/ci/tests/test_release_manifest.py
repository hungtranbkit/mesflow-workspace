import hashlib
import json

import pytest

from release_manifest import build_manifest, sha256_of


def _artifact(tmp_path_factory, name, content=b"pretend zip bytes"):
    # Deliberately NOT inside fake_workspace (which is itself the git repo
    # under test) -- artifacts live outside project source (AGENTS.md Rule
    # 8), and writing one inside the repo would make it dirty for no
    # reason related to what these tests actually check.
    d = tmp_path_factory.mktemp("artifacts")
    p = d / name
    p.write_bytes(content)
    return p


def test_manifest_has_required_fields_and_correct_sha256(fake_workspace, tmp_path_factory):
    artifact = _artifact(tmp_path_factory, "alpha-1.0.0.deploy.zip")

    manifest = build_manifest("alpha", artifact, root=fake_workspace)

    assert manifest["project"] == "alpha"
    assert manifest["version"] == "1.0.0"
    assert manifest["artifact"] == "alpha-1.0.0.deploy.zip"
    assert manifest["sha256"] == hashlib.sha256(b"pretend zip bytes").hexdigest()
    assert "git_sha" in manifest and manifest["git_sha"]
    assert "built_at" in manifest
    assert manifest["dirty"] is False
    assert manifest["release_type"] == "RELEASE"


def test_sha256_of_matches_hashlib_reference(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"a" * 5000)
    assert sha256_of(f) == hashlib.sha256(b"a" * 5000).hexdigest()


def test_manifest_raises_for_unmanaged_project(fake_workspace, tmp_path_factory):
    artifact = _artifact(tmp_path_factory, "gamma-1.0.0.deploy.zip", b"x")
    with pytest.raises(SystemExit):
        build_manifest("gamma", artifact, root=fake_workspace)


def test_manifest_raises_for_missing_artifact(fake_workspace, tmp_path):
    with pytest.raises(SystemExit):
        build_manifest("alpha", tmp_path / "does-not-exist.zip", root=fake_workspace)


def test_dirty_tree_blocks_official_manifest_by_default(fake_workspace, tmp_path_factory):
    # Make the fixture repo dirty by editing a tracked file without committing.
    (fake_workspace / "alpha" / "VERSION.txt").write_text("1.0.1\n", encoding="utf-8")
    artifact = _artifact(tmp_path_factory, "alpha-1.0.1.deploy.zip")

    with pytest.raises(SystemExit, match="DIRTY_TREE_BLOCKED"):
        build_manifest("alpha", artifact, root=fake_workspace)


def test_dirty_tree_allowed_and_marked_non_release_with_flag(fake_workspace, tmp_path_factory):
    (fake_workspace / "alpha" / "VERSION.txt").write_text("1.0.1\n", encoding="utf-8")
    artifact = _artifact(tmp_path_factory, "alpha-1.0.1.deploy.zip")

    manifest = build_manifest("alpha", artifact, root=fake_workspace, allow_dirty=True)
    assert manifest["dirty"] is True
    assert manifest["release_type"] == "NON_RELEASE"


def test_cli_writes_manifest_file(fake_workspace, tmp_path_factory):
    import release_manifest as rm

    artifact = _artifact(tmp_path_factory, "alpha-1.0.0.deploy.zip", b"content")
    out_dir = tmp_path_factory.mktemp("out")
    out_file = out_dir / "manifest.json"

    rc = rm.main(["alpha", str(artifact), "--root", str(fake_workspace), "--out", str(out_file)])
    assert rc == 0
    written = json.loads(out_file.read_text(encoding="utf-8"))
    assert written["project"] == "alpha"
    assert written["sha256"] == hashlib.sha256(b"content").hexdigest()


def test_cli_local_mode_reads_project_yaml_directly(fake_workspace, tmp_path_factory):
    import release_manifest as rm

    artifact = _artifact(tmp_path_factory, "alpha-1.0.0.deploy.zip", b"content")
    out_dir = tmp_path_factory.mktemp("out")
    out_file = out_dir / "manifest.json"

    rc = rm.main([
        "alpha", str(artifact), "--local", "--root", str(fake_workspace / "alpha"),
        "--out", str(out_file),
    ])
    assert rc == 0
    written = json.loads(out_file.read_text(encoding="utf-8"))
    assert written["project"] == "alpha"
    assert written["version"] == "1.0.0"
