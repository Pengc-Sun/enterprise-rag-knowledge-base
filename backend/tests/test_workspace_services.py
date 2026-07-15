import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.workspace import Workspace, WorkspaceMemberRole, WorkspaceStatus
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from backend.app.services.workspaces import (
    OWNER_ROLES,
    READ_ROLES,
    WRITE_ROLES,
    get_workspace_for_user,
    update_workspace,
)


class FakePermissionResult:
    def __init__(self, row: tuple[Workspace, str | None] | None) -> None:
        self.row = row

    def first(self) -> tuple[Workspace, str | None] | None:
        return self.row


class FakePermissionSession:
    def __init__(self, row: tuple[Workspace, str | None] | None) -> None:
        self.row = row
        self.statement: object | None = None

    async def execute(self, statement: object) -> FakePermissionResult:
        self.statement = statement
        return FakePermissionResult(self.row)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = False

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = True


def make_workspace() -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid.uuid4(),
        name="Policy Review",
        slug="policy-review",
        description="Review policies",
        owner_id=uuid.uuid4(),
        status=WorkspaceStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )


def test_workspace_create_schema_requires_valid_slug() -> None:
    workspace_create = WorkspaceCreate(name="Policy Review", slug="policy-review")

    assert workspace_create.name == "Policy Review"
    assert workspace_create.slug == "policy-review"


@pytest.mark.asyncio
async def test_update_workspace_updates_only_provided_fields() -> None:
    workspace = make_workspace()
    session = FakeSession()
    update = WorkspaceUpdate(description="Updated", status=WorkspaceStatus.ARCHIVED)

    updated_workspace = await update_workspace(session, workspace, update)  # type: ignore[arg-type]

    assert updated_workspace is workspace
    assert workspace.name == "Policy Review"
    assert workspace.description == "Updated"
    assert workspace.status == "archived"
    assert session.committed is True
    assert session.refreshed is True


@pytest.mark.asyncio
async def test_get_workspace_for_user_allows_owner_without_membership() -> None:
    workspace = make_workspace()
    session = FakePermissionSession((workspace, None))

    result = await get_workspace_for_user(
        session,  # type: ignore[arg-type]
        workspace.id,
        workspace.owner_id,
        OWNER_ROLES,
    )

    assert result is workspace


@pytest.mark.asyncio
async def test_get_workspace_for_user_denies_viewer_for_write_roles() -> None:
    workspace = make_workspace()
    viewer_id = uuid.uuid4()
    session = FakePermissionSession((workspace, WorkspaceMemberRole.VIEWER.value))

    result = await get_workspace_for_user(
        session,  # type: ignore[arg-type]
        workspace.id,
        viewer_id,
        WRITE_ROLES,
    )

    assert result is None
    assert "viewer" in READ_ROLES
    assert "viewer" not in WRITE_ROLES


@pytest.mark.asyncio
async def test_get_workspace_for_user_returns_none_when_missing() -> None:
    session = FakePermissionSession(None)

    result = await get_workspace_for_user(
        session,  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
        READ_ROLES,
    )

    assert result is None
