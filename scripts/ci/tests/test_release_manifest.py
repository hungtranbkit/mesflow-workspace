import hashlib
import json

import pytest

from release_manifest import build_manifest, main as release_manifest_main, sha256_of


def test_manifest_has_required_fields_and_correct_sha256(fake_workspace, tmp_path):
    artifact = tmp_path / "alpha-1.0.0.deploy.zip"
    artifact.write_bytes(b"pretend zip bytes")

    manifest = build_manifest("alpha", artifact, root=fake_workspace)

    assert manifest["project"] == "alpha"
    assert manifest["version"] == "1.0.0"
    assert manifest["artifact"] == "alpha-1.0.0.deploy.zip"
    assert manifest["sha256"] == hashlib.sha256(b"pretend zip bytes").hexdigest()
    assert "git_sha" in manifest and manifest["git_sha"]
    assert "built_at" in manifest


def test_sha256_of_matches_hashlib_reference(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"a" * 5000)
    assert sha256_of(f) == hashlib.sha256(b"a" * 5000).hexdigest()


def test_manifest_raises_for_unmanaged_project(fake_workspace, tmp_path):
    artifact = tmp_path / "gamma-1.0.0.deploy.zip"
    artifact.write_bytes(b"x")

    with pytest.raises(SystemExit):
        build_manifest("gamma", artifact, root=fake_workspace)


def test_manifest_raises_for_missing_artifact(fake_workspace, tmp_path):
    with pytest.raises(SystemExit):
        build_manifest("alpha", tmp_path / "does-not-exist.zip", root=fake_workspace)


def test_cli_writes_manifest_file(fake_workspace, monkeypatch, tmp_path):
    import release_manifest as rm

    monkeypatch.setattr(rm, "WORKSPACE_ROOT", fake_workspace)
    # main() always resolves against the module-level WORKSPACE_ROOT default
    # (there is no --root CLI flag by design -- a real invocation always
    # means "this workspace"), so this is the one place patching the
    # module attribute is the right tool, and it is enough on its own
    # because build_manifest's `root` parameter default is looked up fresh
    # from rm.WORKSPACE_ROOT only through this call path (main -> build_manifest
    # invoked with no explicit root=).
    monkeypatch.setattr(rm, "build_manifest", lambda *a, **kw: build_manifest(*a, **{**kw, "root": fake_workspace}))

    artifact = tmp_path / "alpha-1.0.0.deploy.zip"
    artifact.write_bytes(b"content")
    out_file = tmp_path / "manifest.json"

    rc = rm.main(["alpha", str(artifact), "--out", str(out_file)])
    assert rc == 0
    written = json.loads(out_file.read_text(encoding="utf-8"))
    assert written["project"] == "alpha"
    assert written["sha256"] == hashlib.sha256(b"content").hexdigest()
