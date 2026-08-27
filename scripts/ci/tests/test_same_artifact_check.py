from same_artifact_check import check


def test_matching_sha256_allows_production():
    test_manifest = {"project": "alpha", "sha256": "abc123"}
    prod_manifest = {"project": "alpha", "sha256": "abc123"}
    ok, reason = check(test_manifest, prod_manifest)
    assert ok is True
    assert "matches" in reason


def test_mismatched_sha256_blocks_production():
    test_manifest = {"project": "alpha", "sha256": "abc123"}
    prod_manifest = {"project": "alpha", "sha256": "def456"}
    ok, reason = check(test_manifest, prod_manifest)
    assert ok is False
    assert "sha256 mismatch" in reason


def test_mismatched_project_blocks_production_even_if_sha256_matches():
    # Defensive: two manifests for different projects that happen to share
    # a hash by coincidence must never be treated as "the same artifact".
    test_manifest = {"project": "alpha", "sha256": "same"}
    prod_manifest = {"project": "beta", "sha256": "same"}
    ok, reason = check(test_manifest, prod_manifest)
    assert ok is False
    assert "project mismatch" in reason


def test_missing_sha256_blocks_production():
    ok, reason = check({"project": "alpha"}, {"project": "alpha", "sha256": "x"})
    assert ok is False
    assert "missing sha256" in reason


def test_cli_exit_code_reflects_gate(tmp_path):
    import json
    import same_artifact_check as sac

    test_path = tmp_path / "test.json"
    prod_path = tmp_path / "prod.json"
    test_path.write_text(json.dumps({"project": "alpha", "sha256": "same"}), encoding="utf-8")
    prod_path.write_text(json.dumps({"project": "alpha", "sha256": "same"}), encoding="utf-8")
    assert sac.main([str(test_path), str(prod_path)]) == 0

    prod_path.write_text(json.dumps({"project": "alpha", "sha256": "different"}), encoding="utf-8")
    assert sac.main([str(test_path), str(prod_path)]) == 1
