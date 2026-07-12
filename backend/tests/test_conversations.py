import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import conversations as conversation_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.conversation import Conversation, Message, MessageRole
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate


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


def make_conversation(user_id: uuid.UUID, knowledge_base_id: uuid.UUID) -> Conversation:
    now = datetime.now(UTC)
    return Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        title="Travel policy",
        created_at=now,
        updated_at=now,
    )


def make_message(conversation_id: uuid.UUID) -> Message:
    now = datetime.now(UTC)
    return Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=MessageRole.USER.value,
        content="What is the travel policy?",
        sources=[],
        token_usage=None,
        latency_ms=None,
        created_at=now,
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


def test_create_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    conversation = make_conversation(user.id, knowledge_base.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert user_id == user.id
        assert "viewer" in allowed_permissions
        return knowledge_base

    async def fake_create_conversation(
        session: AsyncSession,
        user_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        conversation_create: ConversationCreate,
    ) -> Conversation:
        assert user_id == user.id
        assert knowledge_base_id == knowledge_base.id
        assert conversation_create.title == "Travel policy"
        return conversation

    monkeypatch.setattr(
        conversation_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(conversation_endpoints, "create_conversation", fake_create_conversation)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/conversations",
            json={"title": "Travel policy"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "conversation created"
    assert body["data"]["id"] == str(conversation.id)
    assert body["data"]["title"] == "Travel policy"


def test_list_conversations(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    conversation = make_conversation(user.id, knowledge_base.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_list_conversations_for_user(
        session: AsyncSession,
        user_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> list[Conversation]:
        assert user_id == user.id
        assert knowledge_base_id == knowledge_base.id
        return [conversation]

    monkeypatch.setattr(
        conversation_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        conversation_endpoints,
        "list_conversations_for_user",
        fake_list_conversations_for_user,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/knowledge-bases/{knowledge_base.id}/conversations")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == str(conversation.id)


def test_update_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    conversation = make_conversation(user.id, knowledge_base.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_get_conversation_for_user(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> Conversation:
        assert conversation_id == conversation.id
        assert user_id == user.id
        assert knowledge_base_id == knowledge_base.id
        return conversation

    async def fake_update_conversation(
        session: AsyncSession,
        conversation: Conversation,
        conversation_update: ConversationUpdate,
    ) -> Conversation:
        conversation.title = conversation_update.title or conversation.title
        return conversation

    monkeypatch.setattr(
        conversation_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        conversation_endpoints,
        "get_conversation_for_user",
        fake_get_conversation_for_user,
    )
    monkeypatch.setattr(conversation_endpoints, "update_conversation", fake_update_conversation)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/conversations/{conversation.id}",
            json={"title": "Updated title"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["message"] == "conversation updated"
    assert response.json()["data"]["title"] == "Updated title"


def test_create_message(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    conversation = make_conversation(user.id, knowledge_base.id)
    message = make_message(conversation.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_get_conversation_for_user(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> Conversation:
        return conversation

    async def fake_create_message(
        session: AsyncSession,
        conversation: Conversation,
        message_create: MessageCreate,
    ) -> Message:
        assert message_create.role == MessageRole.USER
        assert message_create.content == "What is the travel policy?"
        return message

    monkeypatch.setattr(
        conversation_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        conversation_endpoints,
        "get_conversation_for_user",
        fake_get_conversation_for_user,
    )
    monkeypatch.setattr(conversation_endpoints, "create_message", fake_create_message)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/conversations/{conversation.id}/messages",
            json={"role": "user", "content": "What is the travel policy?"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "message created"
    assert body["data"]["conversation_id"] == str(conversation.id)
    assert body["data"]["role"] == "user"


def test_read_conversation_returns_404_when_not_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_get_conversation_for_user(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(
        conversation_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        conversation_endpoints,
        "get_conversation_for_user",
        fake_get_conversation_for_user,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/conversations/{uuid.uuid4()}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Conversation not found"
