from typing import cast

from backend.app.models.workspace import WorkspaceTemplateCategory
from backend.app.services.workspace_template_definitions import BUILT_IN_WORKSPACE_TEMPLATES


def test_built_in_workspace_templates_cover_supported_categories() -> None:
    categories = {template["category"] for template in BUILT_IN_WORKSPACE_TEMPLATES}

    assert categories == {
        WorkspaceTemplateCategory.GENERAL,
        WorkspaceTemplateCategory.POLICY_REVIEW,
        WorkspaceTemplateCategory.IT_SUPPORT,
        WorkspaceTemplateCategory.RESEARCH_REVIEW,
    }


def test_built_in_workspace_templates_have_instantiable_schemas() -> None:
    for template in BUILT_IN_WORKSPACE_TEMPLATES:
        directory_schema = template["directory_schema"]
        analysis_task_schema = template["analysis_task_schema"]
        report_schema = template["report_schema"]

        assert directory_schema["version"] == "1.0"
        assert analysis_task_schema["version"] == "1.0"
        assert report_schema["version"] == "1.0"

        directories = cast(list[dict[str, object]], directory_schema["directories"])
        tasks = cast(list[dict[str, object]], analysis_task_schema["tasks"])
        sections = cast(list[dict[str, object]], report_schema["sections"])

        directory_keys = {directory["key"] for directory in directories}
        task_keys = {task["key"] for task in tasks}

        assert len(directory_keys) == len(directories)
        assert len(task_keys) == len(tasks)
        assert len(sections) >= 3
        assert cast(list[str], report_schema["export_formats"]) == ["markdown", "docx", "pdf"]

        for directory in directories:
            assert directory["name"]
            assert directory["path"]
            assert isinstance(directory["sort_order"], int)

        for task in tasks:
            output_schema = cast(dict[str, object], task["output_schema"])

            assert task["name"]
            assert task["task_type"]
            assert task["prompt_template"]
            assert task["default_enabled"] is True
            assert output_schema["type"] == "object"
            assert "citations" in cast(dict[str, object], output_schema["properties"])

        for section in sections:
            source_task_keys = set(cast(list[str], section["source_task_keys"]))

            assert section["key"]
            assert section["title"]
            assert isinstance(section["sort_order"], int)
            assert source_task_keys
            assert source_task_keys <= task_keys


def test_different_built_in_workspace_templates_have_different_task_sets() -> None:
    task_sets = {
        template["category"]: tuple(
            task["key"]
            for task in cast(
                list[dict[str, object]],
                template["analysis_task_schema"]["tasks"],
            )
        )
        for template in BUILT_IN_WORKSPACE_TEMPLATES
    }

    assert task_sets[WorkspaceTemplateCategory.POLICY_REVIEW] == (
        "policy_requirements",
        "policy_risk_review",
    )
    assert task_sets[WorkspaceTemplateCategory.IT_SUPPORT] == (
        "support_steps",
        "incident_priority_summary",
    )
    assert task_sets[WorkspaceTemplateCategory.RESEARCH_REVIEW] == (
        "evidence_table",
        "paper_comparison",
    )
    assert len(set(task_sets.values())) == len(task_sets)

