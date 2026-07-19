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
from backend.app.models.audit import AuditAction, AuditResourceType
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceStatus,
)
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceDashboardRead,
    WorkspaceDashboardReviewMetric,
    WorkspaceDashboardStatusMetric,
    WorkspaceUpdate,
)
from backend.app.services.workspaces import WorkspaceMemberRoleError


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


def patch_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    records: list[dict[str, object]],
) -> None:
    async def fake_create_audit_log(
        session: AsyncSession,
        *,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: AuditAction,
        resource_type: AuditResourceType,
        resource_id: uuid.UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        records.append(
            {
                "workspace_id": workspace_id,
                "actor_user_id": actor_user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "metadata": metadata or {},
            }
        )

    monkeypatch.setattr(workspace_endpoints, "create_audit_log", fake_create_audit_log)


def test_create_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    audit_logs: list[dict[str, object]] = []

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
    patch_audit_log(monkeypatch, audit_logs)
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
    assert audit_logs[0]["action"] == AuditAction.WORKSPACE_CREATED
    assert audit_logs[0]["resource_id"] == workspace.id


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


def test_read_workspace_dashboard_requires_read_role(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    dashboard = WorkspaceDashboardRead(
        workspace_id=workspace.id,
        documents=WorkspaceDashboardStatusMetric(total=2, by_status={"completed": 2}),
        analysis_tasks=WorkspaceDashboardStatusMetric(total=1, by_status={"completed": 1}),
        reviews=WorkspaceDashboardReviewMetric(
            total=3,
            by_status={"needs_review": 2, "approved": 1},
            by_decision={"approve": 1},
        ),
        reports=WorkspaceDashboardStatusMetric(total=1, by_status={"draft": 1}),
        exports=WorkspaceDashboardStatusMetric(total=1, by_status={"completed": 1}),
    )

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

    async def fake_build_workspace_dashboard(
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> WorkspaceDashboardRead:
        assert workspace_id == workspace.id
        return dashboard

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(
        workspace_endpoints,
        "build_workspace_dashboard",
        fake_build_workspace_dashboard,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["workspace_id"] == str(workspace.id)
    assert body["data"]["documents"]["total"] == 2
    assert body["data"]["reviews"]["by_decision"]["approve"] == 1


def test_update_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    audit_logs: list[dict[str, object]] = []

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
    patch_audit_log(monkeypatch, audit_logs)
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
    assert audit_logs[0]["action"] == AuditAction.WORKSPACE_UPDATED
    assert audit_logs[0]["metadata"] == {"name": "Archived Policy Review", "status": "archived"}


def test_delete_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    deleted = False
    audit_logs: list[dict[str, object]] = []

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
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/workspaces/{workspace.id}")
    finally:
        clear_overrides()

    assert response.status_code == 204
    assert response.content == b""
    assert deleted is True
    assert audit_logs[0]["action"] == AuditAction.WORKSPACE_DELETED


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


def make_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceMemberRole = WorkspaceMemberRole.VIEWER,
) -> WorkspaceMember:
    now = datetime.now(UTC)
    return WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role=role.value,
        created_at=now,
        updated_at=now,
    )


def test_list_workspace_members(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    member = make_member(workspace.id, user.id, WorkspaceMemberRole.OWNER)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert "viewer" in allowed_roles
        return workspace

    async def fake_list_workspace_members(
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> list[WorkspaceMember]:
        assert workspace_id == workspace.id
        return [member]

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "list_workspace_members", fake_list_workspace_members)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/workspaces/{workspace.id}/members")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["role"] == "owner"


def test_add_workspace_member(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    new_user = make_user()
    new_user.id = uuid.uuid4()
    workspace = make_workspace(user.id)
    member = make_member(workspace.id, new_user.id, WorkspaceMemberRole.REVIEWER)
    audit_logs: list[dict[str, object]] = []

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert "admin" in allowed_roles
        return workspace

    async def fake_get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User:
        assert user_id == new_user.id
        return new_user

    async def fake_add_workspace_member(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        assert workspace_id == workspace.id
        assert user_id == new_user.id
        assert role == WorkspaceMemberRole.REVIEWER
        return member

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_endpoints, "add_workspace_member", fake_add_workspace_member)
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/members",
            json={"user_id": str(new_user.id), "role": "reviewer"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "workspace member added"
    assert body["data"]["user_id"] == str(new_user.id)
    assert body["data"]["role"] == "reviewer"
    assert audit_logs[0]["action"] == AuditAction.WORKSPACE_MEMBER_ADDED
    assert audit_logs[0]["resource_id"] == member.id


def test_add_workspace_member_returns_404_when_user_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    missing_user_id = uuid.uuid4()

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "get_user_by_id", fake_get_user_by_id)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/members",
            json={"user_id": str(missing_user_id), "role": "viewer"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "User not found"


def test_update_workspace_member(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    member_user_id = uuid.uuid4()
    workspace = make_workspace(user.id)
    member = make_member(workspace.id, member_user_id, WorkspaceMemberRole.VIEWER)
    audit_logs: list[dict[str, object]] = []

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        assert "admin" in allowed_roles
        return workspace

    async def fake_get_workspace_member(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember:
        assert user_id == member_user_id
        return member

    async def fake_update_workspace_member_role(
        session: AsyncSession,
        workspace: Workspace,
        member: WorkspaceMember,
        role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        member.role = role.value
        return member

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(
        workspace_endpoints,
        "update_workspace_member_role",
        fake_update_workspace_member_role,
    )
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/workspaces/{workspace.id}/members/{member_user_id}",
            json={"role": "editor"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "workspace member updated"
    assert body["data"]["role"] == "editor"
    assert audit_logs[0]["action"] == AuditAction.WORKSPACE_MEMBER_UPDATED
    assert audit_logs[0]["metadata"] == {"user_id": str(member_user_id), "role": "editor"}


def test_update_workspace_member_rejects_owner_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    member_user_id = uuid.uuid4()
    workspace = make_workspace(user.id)
    member = make_member(workspace.id, member_user_id, WorkspaceMemberRole.VIEWER)

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_member(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember:
        return member

    async def fake_update_workspace_member_role(
        session: AsyncSession,
        workspace: Workspace,
        member: WorkspaceMember,
        role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        raise WorkspaceMemberRoleError

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(
        workspace_endpoints,
        "update_workspace_member_role",
        fake_update_workspace_member_role,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/workspaces/{workspace.id}/members/{member_user_id}",
            json={"role": "owner"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert "owner role" in response.json()["message"]


def test_remove_workspace_member(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    member_user_id = uuid.uuid4()
    workspace = make_workspace(user.id)
    member = make_member(workspace.id, member_user_id, WorkspaceMemberRole.VIEWER)
    removed = False
    audit_logs: list[dict[str, object]] = []

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        return workspace

    async def fake_get_workspace_member(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember:
        return member

    async def fake_remove_workspace_member(
        session: AsyncSession,
        workspace: Workspace,
        member: WorkspaceMember,
    ) -> None:
        nonlocal removed
        removed = True

    monkeypatch.setattr(workspace_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)
    monkeypatch.setattr(workspace_endpoints, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(
        workspace_endpoints, "remove_workspace_member", fake_remove_workspace_member
    )
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/workspaces/{workspace.id}/members/{member_user_id}")
    finally:
        clear_overrides()

    assert response.status_code == 204
    assert response.content == b""
    assert removed is True
    assert audit_logs[0]["action"] == AuditAction.WORKSPACE_MEMBER_REMOVED
