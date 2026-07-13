import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models.conversation import Conversation, MessageRole
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User
from backend.app.schemas.conversation import (
    ConversationChatRequest,
    ConversationChatResponse,
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)
from backend.app.schemas.rag import RAGMetadataFilter, RAGSourceCitationRead
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.conversations import (
    build_query_rewrite_history,
    create_conversation,
    create_message,
    delete_conversation,
    get_conversation_for_user,
    list_conversations_for_user,
    list_messages_for_conversation,
    update_conversation,
)
from backend.app.services.embeddings import EmbeddingProviderError, create_embedding_provider
from backend.app.services.knowledge_bases import READ_PERMISSIONS, get_knowledge_base_for_user
from backend.app.services.llms import LLMProviderError, create_llm_provider
from backend.app.services.query_rewriting import create_query_rewrite_config
from backend.app.services.rag import RAGSourceCitation, answer_knowledge_base_question
from backend.app.services.rerankers import RerankerError, create_reranker
from backend.app.services.retrieval import RetrievalMetadataFilter, create_retrieval_config
from backend.app.services.streaming import format_sse_event, stream_text_tokens

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


@router.post("/{conversation_id}/chat", response_model=APIResponse[ConversationChatResponse])
async def chat_with_conversation_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    chat_request: ConversationChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[ConversationChatResponse]:
    conversation = await get_conversation_or_404(
        session,
        knowledge_base_id,
        conversation_id,
        current_user.id,
    )
    context_messages = await list_messages_for_conversation(session, conversation)
    settings = get_settings()
    try:
        rag_answer = await answer_knowledge_base_question(
            session=session,
            knowledge_base_id=knowledge_base_id,
            question=chat_request.question,
            embedding_provider=create_embedding_provider(settings),
            llm_provider=create_llm_provider(settings),
            reranker=create_reranker(settings),
            retrieval_config=create_retrieval_config(settings),
            query_rewrite_config=create_query_rewrite_config(settings),
            history=build_query_rewrite_history(
                context_messages,
                settings.conversation_context_limit,
            ),
            metadata_filter=build_retrieval_metadata_filter(chat_request.filters),
            user_id=current_user.id,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except (EmbeddingProviderError, LLMProviderError, RerankerError, ValueError) as exc:
        message = getattr(exc, "message", "Conversation chat failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    user_message = await create_message(
        session,
        conversation,
        MessageCreate(role=MessageRole.USER, content=chat_request.question),
    )
    assistant_message = await create_message(
        session,
        conversation,
        MessageCreate(
            role=MessageRole.ASSISTANT,
            content=rag_answer.answer,
            sources=[serialize_source(source) for source in rag_answer.sources],
            token_usage={"model": rag_answer.model, "provider": rag_answer.provider.value},
        ),
    )

    return success_response(
        ConversationChatResponse(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            answer=rag_answer.answer,
            rewritten_question=rag_answer.query_rewrite.rewritten_query,
            question_was_rewritten=rag_answer.query_rewrite.was_rewritten,
            model=rag_answer.model,
            provider=rag_answer.provider.value,
            context_message_count=min(len(context_messages), settings.conversation_context_limit),
            context_chunk_count=len(rag_answer.context_chunks),
            context_chunk_ids=[item.chunk.id for item in rag_answer.context_chunks],
            sources=[
                RAGSourceCitationRead(
                    document_name=source.document_name,
                    page_number=source.page_number,
                    chunk_id=source.chunk_id,
                    original_text=source.original_text,
                    similarity_score=source.similarity_score,
                )
                for source in rag_answer.sources
            ],
        ),
        message="conversation answered",
    )


@router.post("/{conversation_id}/chat/stream")
async def stream_chat_with_conversation_endpoint(
    knowledge_base_id: uuid.UUID,
    conversation_id: uuid.UUID,
    chat_request: ConversationChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    conversation = await get_conversation_or_404(
        session,
        knowledge_base_id,
        conversation_id,
        current_user.id,
    )
    return StreamingResponse(
        stream_conversation_answer(
            session=session,
            knowledge_base_id=knowledge_base_id,
            conversation=conversation,
            chat_request=chat_request,
            user_id=current_user.id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def stream_conversation_answer(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    conversation: Conversation,
    chat_request: ConversationChatRequest,
    user_id: uuid.UUID,
) -> AsyncIterator[str]:
    yield format_sse_event("start", {"conversation_id": str(conversation.id)})
    settings = get_settings()
    try:
        context_messages = await list_messages_for_conversation(session, conversation)
        rag_answer = await answer_knowledge_base_question(
            session=session,
            knowledge_base_id=knowledge_base_id,
            question=chat_request.question,
            embedding_provider=create_embedding_provider(settings),
            llm_provider=create_llm_provider(settings),
            reranker=create_reranker(settings),
            retrieval_config=create_retrieval_config(settings),
            query_rewrite_config=create_query_rewrite_config(settings),
            history=build_query_rewrite_history(
                context_messages,
                settings.conversation_context_limit,
            ),
            metadata_filter=build_retrieval_metadata_filter(chat_request.filters),
            user_id=user_id,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        yield format_sse_event(
            "metadata",
            {
                "rewritten_question": rag_answer.query_rewrite.rewritten_query,
                "question_was_rewritten": rag_answer.query_rewrite.was_rewritten,
                "model": rag_answer.model,
                "provider": rag_answer.provider.value,
                "context_message_count": min(
                    len(context_messages),
                    settings.conversation_context_limit,
                ),
                "context_chunk_count": len(rag_answer.context_chunks),
                "context_chunk_ids": [str(item.chunk.id) for item in rag_answer.context_chunks],
            },
        )

        async for token in stream_text_tokens(rag_answer.answer):
            yield format_sse_event("token", {"token": token})

        user_message = await create_message(
            session,
            conversation,
            MessageCreate(role=MessageRole.USER, content=chat_request.question),
        )
        assistant_message = await create_message(
            session,
            conversation,
            MessageCreate(
                role=MessageRole.ASSISTANT,
                content=rag_answer.answer,
                sources=[serialize_source(source) for source in rag_answer.sources],
                token_usage={"model": rag_answer.model, "provider": rag_answer.provider.value},
            ),
        )
        yield format_sse_event(
            "done",
            {
                "user_message_id": str(user_message.id),
                "assistant_message_id": str(assistant_message.id),
                "sources": [serialize_source(source) for source in rag_answer.sources],
            },
        )
    except asyncio.CancelledError:
        raise
    except (EmbeddingProviderError, LLMProviderError, RerankerError, ValueError) as exc:
        message = getattr(exc, "message", "Conversation stream failed")
        yield format_sse_event("error", {"message": message})
    except Exception:
        yield format_sse_event("error", {"message": "Conversation stream failed"})


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


def build_retrieval_metadata_filter(filters: RAGMetadataFilter) -> RetrievalMetadataFilter:
    return RetrievalMetadataFilter(
        document_ids=tuple(filters.document_ids),
        file_types=tuple(filters.file_types),
        created_after=filters.created_after,
        created_before=filters.created_before,
        departments=tuple(filters.departments),
        permissions=tuple(filters.permissions),
    )


def serialize_source(source: RAGSourceCitation) -> dict[str, object]:
    return {
        "document_name": source.document_name,
        "page_number": source.page_number,
        "chunk_id": str(source.chunk_id),
        "original_text": source.original_text,
        "similarity_score": source.similarity_score,
    }
