import uuid

from backend.app.models.user import User
from backend.app.models.workspace import (
    Workspace,
    WorkspaceDirectory,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceStatus,
    WorkspaceTemplate,
    WorkspaceTemplateCategory,
)


def test_workspace_status_values() -> None:
    assert WorkspaceStatus.ACTIVE.value == "active"
    assert WorkspaceStatus.ARCHIVED.value == "archived"


def test_workspace_member_role_values() -> None:
    assert WorkspaceMemberRole.OWNER.value == "owner"
    assert WorkspaceMemberRole.ADMIN.value == "admin"
    assert WorkspaceMemberRole.EDITOR.value == "editor"
    assert WorkspaceMemberRole.REVIEWER.value == "reviewer"
    assert WorkspaceMemberRole.VIEWER.value == "viewer"


def test_workspace_owner_and_member_relationships() -> None:
    owner = User(
        id=uuid.uuid4(),
        email="owner@example.com",
        username="owner",
        hashed_password="hashed",
    )
    reviewer = User(
        id=uuid.uuid4(),
        email="reviewer@example.com",
        username="reviewer",
        hashed_password="hashed",
    )
    workspace = Workspace(
        name="Policy Review",
        slug="policy-review",
        owner=owner,
        status=WorkspaceStatus.ACTIVE.value,
    )
    member = WorkspaceMember(
        workspace=workspace,
        user=reviewer,
        role=WorkspaceMemberRole.REVIEWER.value,
    )

    assert workspace.owner is owner
    assert workspace in owner.owned_workspaces
    assert member.workspace is workspace
    assert member.user is reviewer
    assert member in workspace.members
    assert member in reviewer.workspace_memberships
    assert member.role == "reviewer"


def test_workspace_template_relationship() -> None:
    owner = User(
        id=uuid.uuid4(),
        email="template-owner@example.com",
        username="template_owner",
        hashed_password="hashed",
    )
    template = WorkspaceTemplate(
        name="IT Support",
        category=WorkspaceTemplateCategory.IT_SUPPORT.value,
        directory_schema={"directories": [{"name": "Runbooks"}]},
        analysis_task_schema={"tasks": [{"key": "incident_summary"}]},
        report_schema={"sections": [{"title": "Summary"}]},
    )
    workspace = Workspace(
        name="IT Support Workspace",
        slug="it-support-workspace",
        owner=owner,
        template=template,
    )

    assert workspace.template is template
    assert workspace in template.workspaces
    assert template.category == "it_support"
    assert template.directory_schema == {"directories": [{"name": "Runbooks"}]}


def test_workspace_directory_relationships() -> None:
    owner = User(
        id=uuid.uuid4(),
        email="directory-owner@example.com",
        username="directory_owner",
        hashed_password="hashed",
    )
    workspace = Workspace(
        name="Research Workspace",
        slug="research-workspace",
        owner=owner,
    )
    parent = WorkspaceDirectory(
        workspace=workspace,
        name="Papers",
        path="papers",
        sort_order=10,
    )
    child = WorkspaceDirectory(
        workspace=workspace,
        parent=parent,
        name="Reviewed Papers",
        path="papers/reviewed",
        sort_order=20,
    )

    assert parent.workspace is workspace
    assert child.workspace is workspace
    assert child.parent is parent
    assert child in parent.children
    assert parent in workspace.directories
    assert child in workspace.directories
