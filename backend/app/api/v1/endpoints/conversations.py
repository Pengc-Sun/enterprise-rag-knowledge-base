import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.db.session import get_db_session
from backend.app.models.conversation import Conversation
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User
from backend.app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.conversations import (
    create_conversation,
    create_message,
    delete_conversation,
    get_conversation_for_user,
    list_conversations_for_user,
    list_messages_for_conversation,
    update_conversation,
)
from backend.app.services.knowledge_bases import READ_PERMISSIONS, get_knowledge_base_for_user

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/conversations",
    tags=["conversations"],
)


@router.post("", response_model=APIResponse[ConversationRead], status_code=status.HTTP_201_CREATED)
async def create_conversation_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_create: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ConversationRead]:
    knowledge_base = await get_knowledge_base_or_404(
        session,
        knowledge_base_id,
        current_user.id,
    )
    conversation = await create_conversation(
        session,
        current_user.id,
        knowledge_base.id,
        conversation_create,
    )
    return success_response(
        ConversationRead.model_validate(conversation),
        message="conversation created",
    )


@router.get("", response_model=APIResponse[list[ConversationRead]])
async def list_conversations_endpoint(
    knowledge_base_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[ConversationRead]]:
    knowledge_base = await get_knowledge_base_or_404(
        session,
        knowledge_base_id,
        current_user.id,
    )
    conversations = await list_conversations_for_user(session, current_user.id, knowledge_base.id)
    return success_response([ConversationRead.model_validate(item) for item in conversations])


@router.get("/{conversation_id}", response_model=APIResponse[ConversationRead])
async def read_conversation_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ConversationRead]:
    conversation = await get_conversation_or_404(
        session,
        knowledge_base_id,
        conversation_id,
        current_user.id,
    )
    return success_response(ConversationRead.model_validate(conversation))


@router.patch("/{conversation_id}", response_model=APIResponse[ConversationRead])
async def update_conversation_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    conversation_update: ConversationUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ConversationRead]:
    conversation = await get_conversation_or_404(
        session,
        knowledge_base_id,
        conversation_id,
        current_user.id,
    )
    updated_conversation = await update_conversation(session, conversation, conversation_update)
    return success_response(
        ConversationRead.model_validate(updated_conversation),
        message="conversation updated",
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    conversation = await get_conversation_or_404(
        session,
        knowledge_base_id,
        conversation_id,
        current_user.id,
    )
    await delete_conversation(session, conversation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/messages",
    response_model=APIResponse[MessageRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_message_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_create: MessageCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[MessageRead]:
    conversation = await get_conversation_or_404(
        session,
        knowledge_base_id,
        conversation_id,
        current_user.id,
    )
    message = await create_message(session, conversation, message_create)
    return success_response(MessageRead.model_validate(message), message="message created")


@router.get("/{conversation_id}/messages", response_model=APIResponse[list[MessageRead]])
async def list_messages_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[list[MessageRead]]:
    conversation = await get_conversation_or_404(
        session,
        knowledge_base_id,
        conversation_id,
        current_user.id,
    )
    messages = await list_messages_for_conversation(session, conversation)
    return success_response([MessageRead.model_validate(item) for item in messages])


async def get_knowledge_base_or_404(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    user_id: uuid.UUID,
) -> KnowledgeBase:
    knowledge_base = await get_knowledge_base_for_user(
        session,
        knowledge_base_id,
        user_id,
        READ_PERMISSIONS,
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )
    return knowledge_base


async def get_conversation_or_404(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Conversation:
    knowledge_base = await get_knowledge_base_or_404(session, knowledge_base_id, user_id)
    conversation = await get_conversation_for_user(
        session,
        conversation_id,
        user_id,
        knowledge_base.id,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation
