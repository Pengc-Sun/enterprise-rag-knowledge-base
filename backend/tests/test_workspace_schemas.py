import uuid

import pytest
from pydantic import ValidationError

from backend.app.models.workspace import (
    WorkspaceMemberRole,
    WorkspaceStatus,
    WorkspaceTemplateCategory,
)
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceTemplateCreate,
    WorkspaceUpdate,
)


def test_workspace_create_accepts_valid_payload() -> None:
    template_id = uuid.uuid4()

    workspace = WorkspaceCreate(
        name="Policy Review",
        slug="policy-review",
        description="Review policy documents",
        template_id=template_id,
    )

    assert workspace.name == "Policy Review"
    assert workspace.slug == "policy-review"
    assert workspace.template_id == template_id


def test_workspace_create_rejects_invalid_slug() -> None:
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="Invalid", slug="Invalid Slug")


def test_workspace_update_accepts_status() -> None:
    update = WorkspaceUpdate(status=WorkspaceStatus.ARCHIVED)

    assert update.status == WorkspaceStatus.ARCHIVED


def test_workspace_template_create_accepts_structured_schemas() -> None:
    template = WorkspaceTemplateCreate(
        name="Research Review",
        category=WorkspaceTemplateCategory.RESEARCH_REVIEW,
        directory_schema={"directories": [{"name": "Papers"}]},
        analysis_task_schema={"tasks": [{"key": "evidence_table"}]},
        report_schema={"sections": [{"title": "Findings"}]},
    )

    assert template.category == WorkspaceTemplateCategory.RESEARCH_REVIEW
    assert template.directory_schema["directories"] == [{"name": "Papers"}]


def test_workspace_member_create_defaults_to_viewer() -> None:
    member = WorkspaceMemberCreate(user_id=uuid.uuid4())

    assert member.role == WorkspaceMemberRole.VIEWER
