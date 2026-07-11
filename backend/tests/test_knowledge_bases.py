import uuid
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


def make_knowledge_base(owner_id: uuid.UUID) -> KnowledgeBase:
    now = datetime.now(UTC)
    return KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        description="Internal docs",
        owner_id=owner_id,
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


def test_create_knowledge_base(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)

    async def fake_create_knowledge_base(
        session: AsyncSession,
        owner_id: uuid.UUID,
        knowledge_base_create: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        assert owner_id == user.id
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
            "/api/v1/knowledge-bases",
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
    assert body["data"]["name"] == "Engineering Handbook"
    assert body["data"]["owner_id"] == str(user.id)


def test_list_knowledge_bases(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)

    async def fake_list_knowledge_bases_for_owner(
        session: AsyncSession,
        owner_id: uuid.UUID,
    ) -> list[KnowledgeBase]:
        assert owner_id == user.id
        return [knowledge_base]

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "list_knowledge_bases_for_owner",
        fake_list_knowledge_bases_for_owner,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get("/api/v1/knowledge-bases")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == str(knowledge_base.id)


def test_read_knowledge_base(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)

    async def fake_get_knowledge_base_for_owner(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert owner_id == user.id
        return knowledge_base

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_knowledge_base_for_owner",
        fake_get_knowledge_base_for_owner,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/knowledge-bases/{knowledge_base.id}")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(knowledge_base.id)


def test_update_knowledge_base(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)

    async def fake_get_knowledge_base_for_owner(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> KnowledgeBase:
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
        "get_knowledge_base_for_owner",
        fake_get_knowledge_base_for_owner,
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
            f"/api/v1/knowledge-bases/{knowledge_base.id}",
            json={"name": "Public Handbook", "visibility": "public"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "knowledge base updated"
    assert body["data"]["name"] == "Public Handbook"
    assert body["data"]["visibility"] == "public"


def test_delete_knowledge_base(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    deleted = False

    async def fake_get_knowledge_base_for_owner(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_delete_knowledge_base(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
    ) -> None:
        nonlocal deleted
        deleted = True

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_knowledge_base_for_owner",
        fake_get_knowledge_base_for_owner,
    )
    monkeypatch.setattr(
        knowledge_base_endpoints,
        "delete_knowledge_base",
        fake_delete_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/knowledge-bases/{knowledge_base.id}")
    finally:
        clear_overrides()

    assert response.status_code == 204
    assert response.content == b""
    assert deleted is True


def test_read_knowledge_base_returns_404_when_not_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    knowledge_base_id = uuid.uuid4()

    async def fake_get_knowledge_base_for_owner(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_knowledge_base_for_owner",
        fake_get_knowledge_base_for_owner,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/knowledge-bases/{knowledge_base_id}")
    finally:
        clear_overrides()

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Knowledge base not found"
