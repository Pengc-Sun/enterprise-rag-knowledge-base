import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "validate_docker_v1_upgrade.py"
    spec = importlib.util.spec_from_file_location("validate_docker_v1_upgrade", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_upgrade_result(script: ModuleType) -> dict[str, object]:
    return {
        "alembic_version": script.HEAD_REVISION,
        "seed_revision": script.V1_REVISION,
        "head_revision": script.HEAD_REVISION,
        "owner_users": 2,
        "knowledge_bases": 1,
        "knowledge_base_members": 1,
        "documents": 1,
        "document_chunks": 1,
        "conversations": 1,
        "messages": 1,
        "workspace_templates": 4,
        "workspace_slug": script.SEED_WORKSPACE_SLUG,
        "workspace_member_role": "owner",
        "workspace_ids_match": True,
        "null_workspace_counts": {
            "knowledge_bases": 0,
            "documents": 0,
            "document_chunks": 0,
            "conversations": 0,
        },
    }


def test_validation_requires_explicit_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setattr("sys.argv", ["validate_docker_v1_upgrade.py"])

    assert script.main() == 2


def test_seed_sql_represents_v1_snapshot_without_workspace_columns() -> None:
    script = load_script()

    sql = script.seed_v1_snapshot_sql().lower()

    assert script.V1_REVISION == "0010"
    assert "insert into knowledge_bases" in sql
    assert "insert into documents" in sql
    assert "insert into document_chunks" in sql
    assert "insert into conversations" in sql
    assert "workspace_id" not in sql


def test_validate_upgrade_result_accepts_complete_migration() -> None:
    script = load_script()

    script.validate_upgrade_result(valid_upgrade_result(script))


def test_validate_upgrade_result_rejects_data_loss() -> None:
    script = load_script()
    result = valid_upgrade_result(script)
    result["messages"] = 0

    with pytest.raises(RuntimeError, match="Expected messages=1"):
        script.validate_upgrade_result(result)


def test_validate_upgrade_result_rejects_null_workspace_ids() -> None:
    script = load_script()
    result = valid_upgrade_result(script)
    null_workspace_counts = result["null_workspace_counts"]
    assert isinstance(null_workspace_counts, dict)
    null_workspace_counts["documents"] = 1

    with pytest.raises(RuntimeError, match="Expected no null workspace IDs in documents"):
        script.validate_upgrade_result(result)
