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
    WorkspaceDirectoryCreate,
    WorkspaceDirectoryUpdate,
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


def test_workspace_directory_create_accepts_nested_path() -> None:
    parent_id = uuid.uuid4()

    directory = WorkspaceDirectoryCreate(
        name="Reviewed Papers",
        path="papers/reviewed",
        description="Reviewed research papers",
        parent_id=parent_id,
        sort_order=20,
    )

    assert directory.parent_id == parent_id
    assert directory.path == "papers/reviewed"


def test_workspace_directory_create_rejects_invalid_path() -> None:
    with pytest.raises(ValidationError):
        WorkspaceDirectoryCreate(name="Invalid", path="Invalid Path")


def test_workspace_directory_update_allows_clearing_parent() -> None:
    update = WorkspaceDirectoryUpdate(parent_id=None)

    assert update.model_dump(exclude_unset=True) == {"parent_id": None}
