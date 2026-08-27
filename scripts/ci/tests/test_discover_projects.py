from pathlib import Path

from workspace import (
    INVALID_CONTRACT,
    MANAGED,
    UNMANAGED,
    UNREGISTERED_CONTRACT,
    discover,
    project_by_code,
    required_stages,
)


def test_registered_projects_with_valid_contracts_are_managed(fake_workspace):
    records = discover(fake_workspace)
    alpha = project_by_code(records, "alpha")
    beta = project_by_code(records, "beta")
    assert alpha.status == MANAGED
    assert beta.status == MANAGED
    assert alpha.registered and beta.registered


def test_unmanaged_project_has_no_manifest_and_is_reported_not_ignored(fake_workspace):
    records = discover(fake_workspace)
    gamma = project_by_code(records, "gamma")
    assert gamma is not None, "a real project dir with no PROJECT.yaml must still be reported"
    assert gamma.status == UNMANAGED
    assert gamma.manifest is None
    assert "no PROJECT.yaml" in gamma.issues


def test_non_project_shared_config_dir_is_never_classified_as_a_project(fake_workspace):
    records = discover(fake_workspace)
    codes = {r.code for r in records}
    assert "nginx" not in codes
    assert "docs" not in codes
    assert "reports" not in codes


def test_project_with_contract_but_missing_from_registry_is_unregistered(fake_workspace):
    # Add a new project dir with a valid PROJECT.yaml that WORKSPACE.yaml
    # does not know about.
    delta = fake_workspace / "delta"
    delta.mkdir()
    (delta / "PROJECT.yaml").write_text(
        "schema_version: 1\nproject:\n  code: delta\nsource:\n  root: .\ncommands: {}\n",
        encoding="utf-8",
    )
    records = discover(fake_workspace)
    delta_record = project_by_code(records, "delta")
    assert delta_record.status == UNREGISTERED_CONTRACT
    assert delta_record.registered is False


def test_registered_project_with_broken_contract_is_invalid_not_managed(fake_workspace):
    # Overwrite alpha's PROJECT.yaml with something missing required fields.
    (fake_workspace / "alpha" / "PROJECT.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    records = discover(fake_workspace)
    alpha = project_by_code(records, "alpha")
    assert alpha.status == INVALID_CONTRACT
    assert any("missing required field" in issue for issue in alpha.issues)


def test_registered_project_with_missing_manifest_file_is_invalid(fake_workspace):
    (fake_workspace / "alpha" / "PROJECT.yaml").unlink()
    records = discover(fake_workspace)
    alpha = project_by_code(records, "alpha")
    assert alpha.status == INVALID_CONTRACT
    assert alpha.manifest is None


def test_unknown_project_code_returns_none(fake_workspace):
    records = discover(fake_workspace)
    assert project_by_code(records, "does-not-exist") is None


def test_required_stages_prefers_explicit_ci_required_block(fake_workspace):
    (fake_workspace / "alpha" / "PROJECT.yaml").write_text(
        (fake_workspace / "alpha" / "PROJECT.yaml").read_text(encoding="utf-8")
        + "\nci:\n  required: [test]\n",
        encoding="utf-8",
    )
    records = discover(fake_workspace)
    alpha = project_by_code(records, "alpha")
    assert required_stages(alpha) == ["test"]


def test_required_stages_falls_back_to_declared_preflight_and_test(fake_workspace):
    records = discover(fake_workspace)
    alpha = project_by_code(records, "alpha")
    beta = project_by_code(records, "beta")
    assert set(required_stages(alpha)) == {"preflight", "test"}
    assert required_stages(beta) == ["test"]  # beta never declared preflight
