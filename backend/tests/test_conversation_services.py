import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.conversation import Conversation, Message, MessageRole
from backend.app.schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate
from backend.app.services.conversations import (
    build_query_rewrite_history,
    create_conversation,
    create_message,
    delete_conversation,
    update_conversation,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: object | None = None
        self.deleted: object | None = None
        self.committed = False
        self.refreshed: list[object] = []

    def add(self, instance: object) -> None:
        self.added = instance

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed.append(instance)

    async def delete(self, instance: object) -> None:
        self.deleted = instance


def make_conversation() -> Conversation:
    now = datetime.now(UTC)
    return Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        title="Travel policy",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_conversation_persists_user_and_knowledge_base() -> None:
    session = FakeSession()
    user_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()

    conversation = await create_conversation(
        session,  # type: ignore[arg-type]
        user_id,
        knowledge_base_id,
        ConversationCreate(title="Travel policy"),
    )

    assert session.added is conversation
    assert session.committed is True
    assert session.refreshed == [conversation]
    assert conversation.user_id == user_id
    assert conversation.knowledge_base_id == knowledge_base_id
    assert conversation.title == "Travel policy"


@pytest.mark.asyncio
async def test_update_conversation_updates_only_provided_fields() -> None:
    session = FakeSession()
    conversation = make_conversation()

    updated = await update_conversation(
        session,  # type: ignore[arg-type]
        conversation,
        ConversationUpdate(title="Updated title"),
    )

    assert updated is conversation
    assert conversation.title == "Updated title"
    assert session.committed is True
    assert session.refreshed == [conversation]


@pytest.mark.asyncio
async def test_delete_conversation_deletes_and_commits() -> None:
    session = FakeSession()
    conversation = make_conversation()

    await delete_conversation(session, conversation)  # type: ignore[arg-type]

    assert session.deleted is conversation
    assert session.committed is True


@pytest.mark.asyncio
async def test_create_message_persists_sources_and_metrics() -> None:
    session = FakeSession()
    conversation = make_conversation()

    message = await create_message(
        session,  # type: ignore[arg-type]
        conversation,
        MessageCreate(
            role=MessageRole.ASSISTANT,
            content="Policy answer",
            sources=[{"document_name": "policy.md"}],
            token_usage={"completion_tokens": 18},
            latency_ms=120,
        ),
    )

    assert isinstance(message, Message)
    assert session.added is message
    assert session.committed is True
    assert session.refreshed == [message, conversation]
    assert message.conversation_id == conversation.id
    assert message.role == "assistant"
    assert message.sources == [{"document_name": "policy.md"}]
    assert message.token_usage == {"completion_tokens": 18}
    assert message.latency_ms == 120


def test_build_query_rewrite_history_limits_recent_user_and_assistant_messages() -> None:
    conversation = make_conversation()
    messages = [
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.SYSTEM.value,
            content="system note",
            sources=[],
        ),
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content="What is the travel policy?",
            sources=[],
        ),
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT.value,
            content="It covers business travel.",
            sources=[],
        ),
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content="What about London?",
            sources=[],
        ),
    ]

    history = build_query_rewrite_history(messages, limit=3)

    assert [item.role for item in history] == ["user", "assistant", "user"]
    assert [item.content for item in history] == [
        "What is the travel policy?",
        "It covers business travel.",
        "What about London?",
    ]


def test_build_query_rewrite_history_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="conversation_context_limit must be positive"):
        build_query_rewrite_history([], limit=0)
