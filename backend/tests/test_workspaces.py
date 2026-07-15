import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import workspaces as workspace_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import Workspace, WorkspaceStatus
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="enterprise_user",
        hashed_password="hashed",
        role=UserRole.USER.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_workspace(owner_id: uuid.UUID) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid.uuid4(),
        name="Policy Review",
        slug="policy-review",
        description="Review policies",
        owner_id=owner_id,
        status=WorkspaceStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )


def override_db_session() -> AsyncSession:
    return cast(AsyncSession, object())


def set_overrides(user: User) -> None:
    def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_db_session


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_create_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)

    async def fake_create_workspace(
        session: AsyncSession,
        owner_id: uuid.UUID,
        workspace_create: WorkspaceCreate,
    ) -> Workspace:
        assert owner_id == user.id
        assert workspace_create.name == "Policy Review"
        assert workspace_create.slug == "policy-review"
        return workspace

    monkeypatch.setattr(workspace_endpoints, "create_workspace", fake_create_workspace)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/workspaces",
            json={
                "name": "Policy Review",
                "slug": "policy-review",
                "description": "Review policies",
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "workspace created"
    assert body["data"]["name"] == "Policy Review"
    assert body["data"]["slug"] == "policy-review"
    assert body["data"]["owner_id"] == str(user.id)


def test_list_workspaces(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)

    async def fake_list_workspaces_for_user(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[Workspace]:
        assert user_id == user.id
        return [workspace]

    monkeypatch.setattr(
        workspace_endpoints,
        "list_workspaces_for_user",
        fake_list_workspaces_for_user,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get("/api/v1/workspaces")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == str(workspace.id)


def test_read_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert workspace_id == workspace.id
        assert user_id == user.id
        assert "viewer" in allowed_roles
        return workspace

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace.id}")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(workspace.id)


def test_update_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert "admin" in allowed_roles
        assert "viewer" not in allowed_roles
        return workspace

    async def fake_update_workspace(
        session: AsyncSession,
        workspace: Workspace,
        workspace_update: WorkspaceUpdate,
    ) -> Workspace:
        workspace.name = workspace_update.name or workspace.name
        if workspace_update.status is not None:
            workspace.status = workspace_update.status.value
        return workspace

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "update_workspace", fake_update_workspace)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/workspaces/{workspace.id}",
            json={"name": "Archived Policy Review", "status": "archived"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "workspace updated"
    assert body["data"]["name"] == "Archived Policy Review"
    assert body["data"]["status"] == "archived"


def test_delete_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    deleted = False

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert allowed_roles == frozenset({"owner"})
        return workspace

    async def fake_delete_workspace(session: AsyncSession, workspace: Workspace) -> None:
        nonlocal deleted
        deleted = True

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "delete_workspace", fake_delete_workspace)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/workspaces/{workspace.id}")
    finally:
        clear_overrides()

    assert response.status_code == 204
    assert response.content == b""
    assert deleted is True


def test_read_workspace_returns_404_when_not_member(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> None:
        return None

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace_id}")
    finally:
        clear_overrides()

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Workspace not found"
