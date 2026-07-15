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


def test_day10_backfill_migration_updates_v1_relationships_in_order() -> None:
    migration = load_migration(
        "migration_0015",
        "20260715_0015_backfill_v1_data_workspace_ids.py",
    )

    assert migration.revision == "0015"
    assert migration.down_revision == "0014"
    assert migration.DEFAULT_WORKSPACE_SLUG_PREFIX == "v1-default-"

    knowledge_base_sql = str(migration.BACKFILL_KNOWLEDGE_BASE_WORKSPACES_SQL).lower()
    document_sql = str(migration.BACKFILL_DOCUMENT_WORKSPACES_SQL).lower()
    chunk_sql = str(migration.BACKFILL_CHUNK_WORKSPACES_SQL).lower()
    conversation_sql = str(migration.BACKFILL_CONVERSATION_WORKSPACES_SQL).lower()
    clear_conversation_sql = str(migration.CLEAR_CONVERSATION_WORKSPACES_SQL).lower()

    assert "update knowledge_bases" in knowledge_base_sql
    assert "workspaces.slug" in knowledge_base_sql
    assert "knowledge_bases.workspace_id is null" in knowledge_base_sql
    assert "update documents" in document_sql
    assert "documents.knowledge_base_id = knowledge_bases.id" in document_sql
    assert "update document_chunks" in chunk_sql
    assert "document_chunks.document_id = documents.id" in chunk_sql
    assert "update conversations" in conversation_sql
    assert "conversations.knowledge_base_id = knowledge_bases.id" in conversation_sql
    assert "set workspace_id = null" in clear_conversation_sql
