import importlib.util
from pathlib import Path
from types import ModuleType
from typing import cast


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


def test_day11_require_workspace_ids_adds_constraints_and_indexes() -> None:
    migration = load_migration(
        "migration_0016",
        "20260715_0016_require_workspace_ids.py",
    )

    assert migration.revision == "0016"
    assert migration.down_revision == "0015"
    assert migration.WORKSPACE_SCOPED_TABLES == (
        "knowledge_bases",
        "documents",
        "document_chunks",
        "conversations",
    )

    assert migration.WORKSPACE_INDEXES["knowledge_bases"] == "ix_knowledge_bases_workspace_id"
    assert migration.WORKSPACE_INDEXES["documents"] == "ix_documents_workspace_id"
    assert migration.WORKSPACE_INDEXES["document_chunks"] == "ix_document_chunks_workspace_id"
    assert migration.WORKSPACE_INDEXES["conversations"] == "ix_conversations_workspace_id"
    assert (
        migration.WORKSPACE_FOREIGN_KEYS["knowledge_bases"]
        == "fk_knowledge_bases_workspace_id_workspaces"
    )
    assert (
        migration.WORKSPACE_FOREIGN_KEYS["documents"]
        == "fk_documents_workspace_id_workspaces"
    )
    assert (
        migration.WORKSPACE_FOREIGN_KEYS["document_chunks"]
        == "fk_document_chunks_workspace_id_workspaces"
    )
    assert (
        migration.WORKSPACE_FOREIGN_KEYS["conversations"]
        == "fk_conversations_workspace_id_workspaces"
    )


def test_day20_audit_log_migration_creates_table_without_cascading_foreign_keys() -> None:
    migration = load_migration(
        "migration_0017",
        "20260716_0017_create_audit_logs_table.py",
    )

    assert migration.revision == "0017"
    assert migration.down_revision == "0016"

    assert migration.__file__ is not None
    source = Path(migration.__file__).read_text()
    assert '"audit_logs"' in source
    assert '"workspace_id"' in source
    assert '"actor_user_id"' in source
    assert '"action"' in source
    assert '"resource_type"' in source
    assert '"resource_id"' in source
    assert '"metadata"' in source
    assert "ix_audit_logs_workspace_id" in source
    assert "ix_audit_logs_actor_user_id" in source
    assert "ix_audit_logs_action" in source
    assert "ForeignKeyConstraint" not in source


def test_day22_workspace_template_schema_migration_updates_built_in_templates() -> None:
    migration = load_migration(
        "migration_0018",
        "20260716_0018_update_workspace_template_schemas.py",
    )

    assert migration.revision == "0018"
    assert migration.down_revision == "0017"
    assert len(migration.LEGACY_TEMPLATE_SCHEMAS) == 4

    assert migration.__file__ is not None
    source = Path(migration.__file__).read_text()
    assert "BUILT_IN_WORKSPACE_TEMPLATES" in source
    assert "directory_schema" in source
    assert "analysis_task_schema" in source
    assert "report_schema" in source

    template = migration.BUILT_IN_WORKSPACE_TEMPLATES[0]
    task = cast(list[dict[str, object]], template["analysis_task_schema"]["tasks"])[0]
    section = cast(list[dict[str, object]], template["report_schema"]["sections"])[0]

    assert "output_schema" in task
    assert "source_task_keys" in section
    assert template["report_schema"]["export_formats"] == ["markdown", "docx", "pdf"]


def test_day23_workspace_directory_migration_creates_scoped_directory_table() -> None:
    migration = load_migration(
        "migration_0019",
        "20260716_0019_create_workspace_directories_table.py",
    )

    assert migration.revision == "0019"
    assert migration.down_revision == "0018"

    assert migration.__file__ is not None
    source = Path(migration.__file__).read_text()
    assert '"workspace_directories"' in source
    assert '"workspace_id"' in source
    assert '"parent_id"' in source
    assert '"name"' in source
    assert '"path"' in source
    assert '"description"' in source
    assert '"sort_order"' in source
    assert "fk_workspace_directories_workspace_id_workspaces" in source
    assert "fk_workspace_directories_parent_id_workspace_directories" in source
    assert "uq_workspace_directories_workspace_path" in source
    assert "ix_workspace_directories_workspace_id" in source


def test_day25_template_default_knowledge_base_migration_updates_directory_schema() -> None:
    migration = load_migration(
        "migration_0020",
        "20260716_0020_update_template_default_knowledge_bases.py",
    )

    assert migration.revision == "0020"
    assert migration.down_revision == "0019"

    template = migration.BUILT_IN_WORKSPACE_TEMPLATES[0]
    knowledge_bases = cast(
        list[dict[str, object]],
        template["directory_schema"]["knowledge_bases"],
    )
    assert knowledge_bases
    assert knowledge_bases[0]["directory_key"]

    assert migration.__file__ is not None
    source = Path(migration.__file__).read_text()
    assert "UPDATE_TEMPLATE_DIRECTORY_SCHEMA_SQL" in source
    assert "REMOVE_TEMPLATE_KNOWLEDGE_BASE_SCHEMA_SQL" in source
    assert "knowledge_bases" in source


def test_day26_analysis_tasks_and_reports_migration_creates_template_outputs() -> None:
    migration = load_migration(
        "migration_0021",
        "20260716_0021_create_analysis_tasks_and_reports.py",
    )

    assert migration.revision == "0021"
    assert migration.down_revision == "0020"

    assert migration.__file__ is not None
    source = Path(migration.__file__).read_text()
    assert '"analysis_tasks"' in source
    assert '"template_task_key"' in source
    assert '"input_scope"' in source
    assert '"output_schema"' in source
    assert '"reports"' in source
    assert '"report_sections"' in source
    assert '"template_section_key"' in source
    assert '"source_task_keys"' in source
    assert '"source_result_ids"' in source
    assert "fk_analysis_tasks_workspace_id_workspaces" in source
    assert "fk_reports_workspace_id_workspaces" in source
    assert "fk_report_sections_report_id_reports" in source
    assert "ix_analysis_tasks_workspace_id" in source
    assert "ix_report_sections_workspace_id" in source


def test_day29_analysis_results_migration_creates_workspace_scoped_results() -> None:
    migration = load_migration(
        "migration_0022",
        "20260716_0022_create_analysis_results_table.py",
    )

    assert migration.revision == "0022"
    assert migration.down_revision == "0021"

    assert migration.__file__ is not None
    source = Path(migration.__file__).read_text()
    assert '"analysis_results"' in source
    assert '"workspace_id"' in source
    assert '"analysis_task_id"' in source
    assert '"result"' in source
    assert '"citations"' in source
    assert '"confidence"' in source
    assert '"token_usage"' in source
    assert "fk_analysis_results_workspace_id_workspaces" in source
    assert "fk_analysis_results_analysis_task_id_analysis_tasks" in source
    assert "ix_analysis_results_workspace_id" in source
    assert "ix_analysis_results_analysis_task_id" in source
