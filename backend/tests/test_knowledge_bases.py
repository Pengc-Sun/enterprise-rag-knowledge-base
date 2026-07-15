import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import knowledge_bases as knowledge_base_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import Workspace
from backend.app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


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
        name="Policy Workspace",
        slug=f"policy-{str(owner_id).replace('-', '')}",
        owner_id=owner_id,
        status="active",
        created_at=now,
        updated_at=now,
    )


def make_knowledge_base(owner_id: uuid.UUID, workspace_id: uuid.UUID) -> KnowledgeBase:
    now = datetime.now(UTC)
    return KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        description="Internal docs",
        owner_id=owner_id,
        workspace_id=workspace_id,
        visibility=KnowledgeBaseVisibility.PRIVATE.value,
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


def patch_workspace_access(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workspace: Workspace | None,
    expected_roles: Callable[[frozenset[str]], None] | None = None,
) -> None:
    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace | None:
        if workspace is not None:
            assert workspace_id == workspace.id
            assert user_id == workspace.owner_id
        if expected_roles is not None:
            expected_roles(allowed_roles)
        return workspace

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )


def assert_read_roles(roles: frozenset[str]) -> None:
    assert "viewer" in roles


def assert_write_roles(roles: frozenset[str]) -> None:
    assert "admin" in roles
    assert "viewer" not in roles


def assert_owner_roles(roles: frozenset[str]) -> None:
    assert roles == frozenset({"owner"})


def test_create_knowledge_base_requires_workspace_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)

    patch_workspace_access(
        monkeypatch,
        workspace=workspace,
        expected_roles=assert_write_roles,
    )

    async def fake_create_knowledge_base(
        session: AsyncSession,
        owner_id: uuid.UUID,
        workspace_id: uuid.UUID,
        knowledge_base_create: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        assert owner_id == user.id
        assert workspace_id == workspace.id
        assert knowledge_base_create.name == "Engineering Handbook"
        return knowledge_base

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "create_knowledge_base",
        fake_create_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases?workspace_id={workspace.id}",
            json={
                "name": "Engineering Handbook",
                "description": "Internal docs",
                "visibility": "private",
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "knowledge base created"
    assert body["data"]["workspace_id"] == str(workspace.id)
    assert body["data"]["owner_id"] == str(user.id)


def test_create_workspace_knowledge_base_route(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)

    patch_workspace_access(monkeypatch, workspace=workspace)

    async def fake_create_knowledge_base(
        session: AsyncSession,
        owner_id: uuid.UUID,
        workspace_id: uuid.UUID,
        knowledge_base_create: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        assert owner_id == user.id
        assert workspace_id == workspace.id
        return knowledge_base

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "create_knowledge_base",
        fake_create_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/knowledge-bases",
            json={"name": "Engineering Handbook"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    assert response.json()["data"]["workspace_id"] == str(workspace.id)


def test_create_knowledge_base_without_workspace_id_returns_422() -> None:
    user = make_user()
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Engineering Handbook"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 422


def test_list_knowledge_bases_is_scoped_to_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)

    patch_workspace_access(
        monkeypatch,
        workspace=workspace,
        expected_roles=assert_read_roles,
    )

    async def fake_list_knowledge_bases_for_workspace(
        session: AsyncSession,
        workspace_id: uuid.UUID,
    ) -> list[KnowledgeBase]:
        assert workspace_id == workspace.id
        return [knowledge_base]

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "list_knowledge_bases_for_workspace",
        fake_list_knowledge_bases_for_workspace,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/knowledge-bases?workspace_id={workspace.id}")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["workspace_id"] == str(workspace.id)


def test_read_knowledge_base_is_scoped_to_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)

    patch_workspace_access(monkeypatch, workspace=workspace)

    async def fake_get_knowledge_base_for_workspace(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert workspace_id == workspace.id
        return knowledge_base

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_knowledge_base_for_workspace",
        fake_get_knowledge_base_for_workspace,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base.id}?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(knowledge_base.id)


def test_update_knowledge_base_requires_workspace_write_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)

    patch_workspace_access(
        monkeypatch,
        workspace=workspace,
        expected_roles=assert_write_roles,
    )

    async def fake_get_knowledge_base_for_workspace(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> KnowledgeBase:
        assert workspace_id == workspace.id
        return knowledge_base

    async def fake_update_knowledge_base(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
        knowledge_base_update: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        knowledge_base.name = knowledge_base_update.name or knowledge_base.name
        if knowledge_base_update.visibility is not None:
            knowledge_base.visibility = knowledge_base_update.visibility.value
        return knowledge_base

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_knowledge_base_for_workspace",
        fake_get_knowledge_base_for_workspace,
    )
    monkeypatch.setattr(
        knowledge_base_endpoints,
        "update_knowledge_base",
        fake_update_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/knowledge-bases/{knowledge_base.id}?workspace_id={workspace.id}",
            json={"name": "Public Handbook", "visibility": "public"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "knowledge base updated"
    assert body["data"]["name"] == "Public Handbook"
    assert body["data"]["visibility"] == "public"


def test_delete_knowledge_base_requires_workspace_owner_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    deleted = False

    patch_workspace_access(
        monkeypatch,
        workspace=workspace,
        expected_roles=assert_owner_roles,
    )

    async def fake_get_knowledge_base_for_workspace(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert workspace_id == workspace.id
        return knowledge_base

    async def fake_delete_knowledge_base(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
    ) -> None:
        nonlocal deleted
        deleted = True

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_knowledge_base_for_workspace",
        fake_get_knowledge_base_for_workspace,
    )
    monkeypatch.setattr(
        knowledge_base_endpoints,
        "delete_knowledge_base",
        fake_delete_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base.id}?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 204
    assert response.content == b""
    assert deleted is True


def test_read_knowledge_base_returns_404_when_workspace_access_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base_id = uuid.uuid4()

    patch_workspace_access(monkeypatch, workspace=None)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_read_knowledge_base_returns_404_when_not_in_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base_id = uuid.uuid4()

    patch_workspace_access(monkeypatch, workspace=workspace)

    async def fake_get_knowledge_base_for_workspace(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_knowledge_base_for_workspace",
        fake_get_knowledge_base_for_workspace,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Knowledge base not found"
