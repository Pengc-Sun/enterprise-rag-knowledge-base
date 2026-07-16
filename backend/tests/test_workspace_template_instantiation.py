import uuid
from datetime import UTC, datetime
from typing import cast

from backend.app.models.workspace import Workspace, WorkspaceTemplate
from backend.app.services.workspace_template_definitions import (
    BUILT_IN_WORKSPACE_TEMPLATES,
    BuiltInWorkspaceTemplate,
)
from backend.app.services.workspaces import (
    instantiate_workspace_analysis_tasks_from_template,
    instantiate_workspace_directories_from_template,
    instantiate_workspace_knowledge_bases_from_template,
    instantiate_workspace_report_from_template,
)


def make_workspace() -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid.uuid4(),
        name="Template Workspace",
        slug="template-workspace",
        description="Template test workspace",
        owner_id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_template(definition: BuiltInWorkspaceTemplate) -> WorkspaceTemplate:
    now = datetime.now(UTC)
    return WorkspaceTemplate(
        id=uuid.UUID(definition["id"]),
        name=definition["name"],
        description=definition["description"],
        category=definition["category"].value,
        version=definition["version"],
        is_active=True,
        directory_schema=definition["directory_schema"],
        analysis_task_schema=definition["analysis_task_schema"],
        report_schema=definition["report_schema"],
        created_at=now,
        updated_at=now,
    )


def test_each_built_in_template_instantiates_expected_workspace_structure() -> None:
    owner_id = uuid.uuid4()

    for definition in BUILT_IN_WORKSPACE_TEMPLATES:
        workspace = make_workspace()
        template = make_template(definition)

        directories = instantiate_workspace_directories_from_template(workspace, template)
        knowledge_bases = instantiate_workspace_knowledge_bases_from_template(
            workspace,
            owner_id,
            template,
        )
        analysis_tasks = instantiate_workspace_analysis_tasks_from_template(
            workspace,
            owner_id,
            template,
        )
        report = instantiate_workspace_report_from_template(workspace, owner_id, template)

        directory_schema = template.directory_schema
        analysis_task_schema = template.analysis_task_schema
        report_schema = template.report_schema
        directory_entries = cast(list[dict[str, object]], directory_schema["directories"])
        knowledge_base_entries = cast(list[dict[str, object]], directory_schema["knowledge_bases"])
        task_entries = cast(list[dict[str, object]], analysis_task_schema["tasks"])
        section_entries = cast(list[dict[str, object]], report_schema["sections"])

        assert [directory.path for directory in directories] == [
            entry["path"] for entry in directory_entries
        ]
        assert {directory.workspace for directory in directories} == {workspace}

        assert [knowledge_base.name for knowledge_base in knowledge_bases] == [
            entry["name"] for entry in knowledge_base_entries
        ]
        assert {knowledge_base.workspace_id for knowledge_base in knowledge_bases} == {
            workspace.id
        }
        assert {knowledge_base.owner_id for knowledge_base in knowledge_bases} == {owner_id}
        assert {
            member.permission
            for knowledge_base in knowledge_bases
            for member in knowledge_base.members
        } == {"owner"}

        assert [task.template_task_key for task in analysis_tasks] == [
            entry["key"] for entry in task_entries
        ]
        assert [task.task_type for task in analysis_tasks] == [
            entry["task_type"] for entry in task_entries
        ]
        assert {task.status for task in analysis_tasks} == {"pending"}
        assert {task.created_by for task in analysis_tasks} == {owner_id}
        assert all(task.output_schema for task in analysis_tasks)

        assert report.workspace_id == workspace.id
        assert report.created_by == owner_id
        assert report.status == "draft"
        assert [section.template_section_key for section in report.sections] == [
            entry["key"] for entry in section_entries
        ]
        assert [section.title for section in report.sections] == [
            entry["title"] for entry in section_entries
        ]
        assert [section.source_task_keys for section in report.sections] == [
            entry["source_task_keys"] for entry in section_entries
        ]
        assert {section.status for section in report.sections} == {"draft"}
        assert {section.body_markdown for section in report.sections} == {""}
        assert {tuple(section.source_result_ids) for section in report.sections} == {()}


def test_template_instantiation_preserves_directory_parent_links() -> None:
    workspace = make_workspace()
    now = datetime.now(UTC)
    template = WorkspaceTemplate(
        id=uuid.uuid4(),
        name="Nested Template",
        category="general",
        version="1.0",
        is_active=True,
        directory_schema={
            "version": "1.0",
            "directories": [
                {
                    "key": "policies",
                    "name": "Policies",
                    "path": "policies",
                    "parent_key": None,
                    "sort_order": 10,
                },
                {
                    "key": "reviewed",
                    "name": "Reviewed",
                    "path": "policies/reviewed",
                    "parent_key": "policies",
                    "sort_order": 20,
                },
            ],
        },
        analysis_task_schema={"version": "1.0", "tasks": []},
        report_schema={"version": "1.0", "sections": []},
        created_at=now,
        updated_at=now,
    )

    directories = instantiate_workspace_directories_from_template(workspace, template)

    parent = directories[0]
    child = directories[1]
    assert child.parent is parent
    assert child in parent.children
    assert child.path == "policies/reviewed"
