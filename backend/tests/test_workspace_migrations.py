import importlib.util
from pathlib import Path
from types import ModuleType


def load_migration(module_name: str, filename: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "migrations" / "versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_day9_default_workspace_migration_targets_v1_owners() -> None:
    migration = load_migration(
        "migration_0014",
        "20260715_0014_create_default_workspaces_for_v1_owners.py",
    )

    assert migration.revision == "0014"
    assert migration.down_revision == "0013"
    assert migration.DEFAULT_WORKSPACE_SLUG_PREFIX == "v1-default-"
    assert "v2.0 migration" in migration.DEFAULT_WORKSPACE_DESCRIPTION

    workspace_sql = str(migration.CREATE_DEFAULT_WORKSPACES_SQL).lower()
    member_sql = str(migration.CREATE_DEFAULT_WORKSPACE_MEMBERS_SQL).lower()
    assert "select distinct owner_id" in workspace_sql
    assert "from knowledge_bases" in workspace_sql
    assert "insert into workspaces" in workspace_sql
    assert "on conflict do nothing" in workspace_sql
    assert ":default-workspace" not in workspace_sql
    assert ":default-workspace" not in member_sql
    assert "insert into workspace_members" in member_sql
    assert "'owner'" in member_sql
