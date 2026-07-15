import uuid

from backend.app.models.conversation import Conversation, Message, MessageRole
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User


def test_message_role_values() -> None:
    assert MessageRole.USER.value == "user"
    assert MessageRole.ASSISTANT.value == "assistant"
    assert MessageRole.SYSTEM.value == "system"


def test_conversation_and_message_relationships() -> None:
    user = User(
        id=uuid.uuid4(),
        email="chat@example.com",
        username="chat_user",
        hashed_password="hashed",
    )
    knowledge_base = KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        owner=user,
    )
    conversation = Conversation(
        user=user,
        knowledge_base=knowledge_base,
        title="Travel policy",
    )
    message = Message(
        conversation=conversation,
        role=MessageRole.USER.value,
        content="What is the travel policy?",
        sources=[],
        token_usage={"prompt_tokens": 12},
        latency_ms=25,
    )

    assert conversation.user is user
    assert conversation.knowledge_base is knowledge_base
    assert conversation in user.conversations
    assert conversation in knowledge_base.conversations
    assert message.conversation is conversation
    assert message in conversation.messages
    assert message.role == "user"
    assert message.sources == []


def test_conversation_accepts_nullable_workspace_id() -> None:
    workspace_id = uuid.uuid4()
    conversation = Conversation(
        user_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        workspace_id=workspace_id,
        title="Travel policy",
    )

    assert conversation.workspace_id == workspace_id


def test_conversation_workspace_id_defaults_to_none() -> None:
    conversation = Conversation(
        user_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        title="Travel policy",
    )

    assert conversation.workspace_id is None
