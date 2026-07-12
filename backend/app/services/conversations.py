import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.conversation import Conversation, Message
from backend.app.schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate


async def create_conversation(
    session: AsyncSession,
    user_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    conversation_create: ConversationCreate,
) -> Conversation:
    conversation = Conversation(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        title=conversation_create.title,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.knowledge_base_id == knowledge_base_id,
        )
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation_for_user(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
) -> Conversation | None:
    result = await session.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.knowledge_base_id == knowledge_base_id,
        )
    )
    return result.scalar_one_or_none()


async def update_conversation(
    session: AsyncSession,
    conversation: Conversation,
    conversation_update: ConversationUpdate,
) -> Conversation:
    update_data = conversation_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)

    await session.commit()
    await session.refresh(conversation)
    return conversation


async def delete_conversation(session: AsyncSession, conversation: Conversation) -> None:
    await session.delete(conversation)
    await session.commit()


async def create_message(
    session: AsyncSession,
    conversation: Conversation,
    message_create: MessageCreate,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=message_create.role.value,
        content=message_create.content,
        sources=message_create.sources,
        token_usage=message_create.token_usage,
        latency_ms=message_create.latency_ms,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    await session.refresh(conversation)
    return message


async def list_messages_for_conversation(
    session: AsyncSession,
    conversation: Conversation,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return list(result.scalars().all())
