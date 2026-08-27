def test_direct_change_also_expands_to_its_declared_dependent(fake_workspace, monkeypatch):
    import workspace
    import changed_projects as cp
    monkeypatch.setattr(cp, "discover", lambda: workspace.discover(fake_workspace))
    monkeypatch.setattr(cp, "load_registry", lambda: workspace.load_registry(fake_workspace))

    # beta depends on alpha (fixture), so a direct change to alpha must
    # also mark beta affected -- see test_dependency_expansion_when_dependency_target_changes
    # below for the assertion on *why* (the reasons dict).
    result = cp.affected_projects(["alpha/app/main.py"])
    assert set(result["affected_projects"]) == {"alpha", "beta"}
    assert result["shared_path_expansion"] is False
    assert "direct:alpha/app/main.py" in result["reasons"]["alpha"]


def test_dependency_expansion_when_dependency_target_changes(fake_workspace, monkeypatch):
    import workspace
    import changed_projects as cp
    monkeypatch.setattr(cp, "discover", lambda: workspace.discover(fake_workspace))
    monkeypatch.setattr(cp, "load_registry", lambda: workspace.load_registry(fake_workspace))

    # alpha changed; beta depends on alpha (both via WORKSPACE.yaml
    # dependencies: and beta/PROJECT.yaml's own dependencies:) -> beta
    # must also be marked affected.
    result = cp.affected_projects(["alpha/app/main.py"])
    assert set(result["affected_projects"]) == {"alpha", "beta"}
    assert any(r.startswith("dependency-of:alpha") for r in result["reasons"]["beta"])


def test_shared_path_change_expands_to_every_managed_project(fake_workspace, monkeypatch):
    import workspace
    import changed_projects as cp
    monkeypatch.setattr(cp, "discover", lambda: workspace.discover(fake_workspace))
    monkeypatch.setattr(cp, "load_registry", lambda: workspace.load_registry(fake_workspace))

    result = cp.affected_projects(["docs/some-standard.md"])
    assert result["shared_path_expansion"] is True
    assert set(result["affected_projects"]) == {"alpha", "beta"}


def test_change_in_unrelated_project_does_not_affect_others(fake_workspace, monkeypatch):
    import workspace
    import changed_projects as cp
    monkeypatch.setattr(cp, "discover", lambda: workspace.discover(fake_workspace))
    monkeypatch.setattr(cp, "load_registry", lambda: workspace.load_registry(fake_workspace))

    # beta changing must NOT affect alpha (alpha does not depend on beta).
    result = cp.affected_projects(["beta/service.py"])
    assert result["affected_projects"] == ["beta"]


def test_no_changed_paths_means_no_affected_projects(fake_workspace, monkeypatch):
    import workspace
    import changed_projects as cp
    monkeypatch.setattr(cp, "discover", lambda: workspace.discover(fake_workspace))
    monkeypatch.setattr(cp, "load_registry", lambda: workspace.load_registry(fake_workspace))

    result = cp.affected_projects([])
    assert result["affected_projects"] == []
    assert result["shared_path_expansion"] is False


def test_unmanaged_project_change_produces_a_warning_not_a_silent_pass(fake_workspace, monkeypatch):
    import workspace
    import changed_projects as cp
    monkeypatch.setattr(cp, "discover", lambda: workspace.discover(fake_workspace))
    monkeypatch.setattr(cp, "load_registry", lambda: workspace.load_registry(fake_workspace))

    # gamma (fixture) is a real project dir with no PROJECT.yaml -- UNMANAGED.
    result = cp.affected_projects(["gamma/AGENTS.md"])
    assert result["affected_projects"] == []
    assert len(result["warnings"]) == 1
    assert "gamma" in result["warnings"][0]
    assert "UNMANAGED" in result["warnings"][0]


def test_change_with_no_project_at_all_produces_no_warning(fake_workspace, monkeypatch):
    # A path that doesn't belong to any known project (managed or not) is
    # simply irrelevant -- not every unmatched path is a "finding".
    import workspace
    import changed_projects as cp
    monkeypatch.setattr(cp, "discover", lambda: workspace.discover(fake_workspace))
    monkeypatch.setattr(cp, "load_registry", lambda: workspace.load_registry(fake_workspace))

    result = cp.affected_projects(["README.md"])
    assert result["affected_projects"] == []
    assert result["warnings"] == []
