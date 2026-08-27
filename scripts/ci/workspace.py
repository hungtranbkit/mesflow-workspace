"""Universal CI/CD Standard V1 -- shared workspace/project discovery logic.

Pure stdlib + PyYAML. No dependency on any one project's own tooling
(mesflow/qa-center/deploy-agent/esp-kiosk) so this stays generic and
reusable when a new project joins the workspace.

Design notes (see docs/CI_CD_STANDARD.md for the normative version):

- Workspace root is derived from this file's own location
  (`<root>/scripts/ci/workspace.py`), not from the caller's cwd -- so
  every CLI in this directory behaves the same regardless of where it is
  invoked from.
- `WORKSPACE.yaml` (if present) is the preferred project registry.
  A conservative `*/PROJECT.yaml` fallback scan always runs too, so a
  missing/incomplete registry entry is reported, never silently dropped.
- Classification is one of MANAGED / UNREGISTERED_CONTRACT /
  INVALID_CONTRACT / UNMANAGED -- never silently PASS for a project with
  no real contract.
"""
from __future__ import annotations

import dataclasses
import glob
import os
from pathlib import Path
from typing import Any

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_REGISTRY_FILE = WORKSPACE_ROOT / "WORKSPACE.yaml"

# Fields every valid PROJECT.yaml must have for its contract to be usable
# by the generic runner.
REQUIRED_PROJECT_FIELDS = ("project", "source", "commands")

MANAGED = "MANAGED"
UNREGISTERED_CONTRACT = "UNREGISTERED_CONTRACT"
INVALID_CONTRACT = "INVALID_CONTRACT"
UNMANAGED = "UNMANAGED"


@dataclasses.dataclass
class ProjectRecord:
    code: str
    root: str  # relative to WORKSPACE_ROOT
    manifest: str | None  # relative path to PROJECT.yaml, if any
    status: str
    registered: bool  # True if listed in WORKSPACE.yaml
    issues: list[str] = dataclasses.field(default_factory=list)
    contract: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "root": self.root,
            "manifest": self.manifest,
            "status": self.status,
            "registered": self.registered,
            "issues": self.issues,
        }


def load_registry(root: Path = WORKSPACE_ROOT) -> dict[str, Any] | None:
    registry_file = root / "WORKSPACE.yaml"
    if not registry_file.exists():
        return None
    with open(registry_file, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_project_yaml(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    if not path.exists():
        return None, [f"manifest not found: {path}"]
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        return None, [f"manifest does not parse as YAML: {exc}"]
    for field in REQUIRED_PROJECT_FIELDS:
        if field not in data:
            issues.append(f"missing required field: {field}")
    return data, issues


def _shared_paths(registry: dict[str, Any] | None) -> set[str]:
    if not registry:
        return set()
    shared = registry.get("shared") or {}
    return {str(v) for v in shared.values()}


def _registered_roots(registry: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """root (relative path string) -> registry project entry."""
    if not registry:
        return {}
    out = {}
    for entry in registry.get("projects") or []:
        root = str(entry.get("root", "")).strip("/")
        if root:
            out[root] = entry
    return out


def _fallback_scan(root: Path) -> dict[str, Path]:
    """dir name (relative) -> PROJECT.yaml path, one level below root."""
    out = {}
    for match in glob.glob(str(root / "*" / "PROJECT.yaml")):
        p = Path(match)
        rel_dir = p.parent.relative_to(root).as_posix()
        out[rel_dir] = p
    return out


def _unmanaged_candidates(root: Path, exclude_roots: set[str], shared: set[str]) -> list[str]:
    """Top-level dirs with independent-lifecycle signals (own .git, own
    AGENTS.md, own VERSION/VERSION.txt) but no PROJECT.yaml at all."""
    candidates = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith("."):
            continue
        if name in exclude_roots or name in shared:
            continue
        if (entry / "PROJECT.yaml").exists():
            continue  # handled by registry/fallback scan already
        has_git = (entry / ".git").exists()
        has_agents = (entry / "AGENTS.md").exists()
        has_version = (entry / "VERSION").exists() or (entry / "VERSION.txt").exists()
        if has_git or has_agents or has_version:
            candidates.append(name)
    return candidates


def discover(root: Path = WORKSPACE_ROOT) -> list[ProjectRecord]:
    registry = load_registry(root)
    registered = _registered_roots(registry)
    fallback = _fallback_scan(root)
    shared = _shared_paths(registry)

    records: list[ProjectRecord] = []
    seen_roots: set[str] = set()

    # 1. Everything the registry declares (source of truth).
    for proj_root, entry in registered.items():
        seen_roots.add(proj_root)
        code = entry.get("code", proj_root)
        manifest_rel = entry.get("manifest", f"{proj_root}/PROJECT.yaml")
        manifest_path = root / manifest_rel
        contract, issues = _load_project_yaml(manifest_path)
        status = MANAGED if contract and not issues else INVALID_CONTRACT
        records.append(
            ProjectRecord(
                code=code,
                root=proj_root,
                manifest=manifest_rel if manifest_path.exists() else None,
                status=status,
                registered=True,
                issues=issues,
                contract=contract,
            )
        )

    # 2. PROJECT.yaml found on disk but not in the registry.
    for proj_root, manifest_path in fallback.items():
        if proj_root in seen_roots:
            continue
        contract, issues = _load_project_yaml(manifest_path)
        code = (contract or {}).get("project", {}).get("code", proj_root)
        records.append(
            ProjectRecord(
                code=code,
                root=proj_root,
                manifest=manifest_path.relative_to(root).as_posix(),
                status=UNREGISTERED_CONTRACT,
                registered=False,
                issues=["not listed in WORKSPACE.yaml projects:"] + issues,
                contract=contract,
            )
        )
        seen_roots.add(proj_root)

    # 3. Real project directories with no PROJECT.yaml at all.
    exclude_roots = seen_roots | {"scripts"}
    for proj_root in _unmanaged_candidates(root, exclude_roots, shared):
        records.append(
            ProjectRecord(
                code=proj_root,
                root=proj_root,
                manifest=None,
                status=UNMANAGED,
                registered=False,
                issues=["no PROJECT.yaml"],
            )
        )

    return sorted(records, key=lambda r: r.code)


def project_by_code(records: list[ProjectRecord], code: str) -> ProjectRecord | None:
    for r in records:
        if r.code == code:
            return r
    return None


def required_stages(record: ProjectRecord) -> list[str]:
    """Which commands.* keys are mandatory CI gates for this project.

    Prefers an explicit `ci.required:` list (the one new, additive,
    backward-compatible PROJECT.yaml field this standard introduces).
    Falls back to whichever of preflight/test the project has actually
    declared, so every pre-existing PROJECT.yaml keeps working unchanged.
    """
    contract = record.contract or {}
    ci_block = contract.get("ci") or {}
    explicit = ci_block.get("required")
    if explicit:
        return list(explicit)
    commands = contract.get("commands") or {}
    return [stage for stage in ("preflight", "test") if stage in commands]


def dependents_of(records: list[ProjectRecord], registry: dict[str, Any] | None, changed_code: str) -> set[str]:
    """Every project whose own contract or the workspace registry declares
    a dependency ON changed_code (i.e. must react when it changes)."""
    result: set[str] = set()
    reg_deps = (registry or {}).get("dependencies") or []
    for dep in reg_deps:
        if dep.get("target") == changed_code:
            result.add(dep.get("source"))
    for record in records:
        for dep in (record.contract or {}).get("dependencies") or []:
            if dep.get("target") == changed_code:
                result.add(record.code)
    result.discard(None)
    return result
