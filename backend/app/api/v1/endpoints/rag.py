import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse, RAGSourceCitationRead
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.embeddings import EmbeddingProviderError, create_embedding_provider
from backend.app.services.knowledge_bases import READ_PERMISSIONS, get_knowledge_base_for_user
from backend.app.services.llms import LLMProviderError, create_llm_provider
from backend.app.services.rag import answer_knowledge_base_question
from backend.app.services.retrieval import create_retrieval_config

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/query", tags=["rag"])


@router.post("", response_model=APIResponse[RAGQueryResponse])
async def query_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    query_request: RAGQueryRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[RAGQueryResponse]:
    knowledge_base = await get_knowledge_base_for_user(
        session,
        knowledge_base_id,
        current_user.id,
        READ_PERMISSIONS,
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    settings = get_settings()
    try:
        rag_answer = await answer_knowledge_base_question(
            session=session,
            knowledge_base_id=knowledge_base.id,
            question=query_request.question,
            embedding_provider=create_embedding_provider(settings),
            llm_provider=create_llm_provider(settings),
            retrieval_config=create_retrieval_config(settings),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except (EmbeddingProviderError, LLMProviderError, ValueError) as exc:
        message = getattr(exc, "message", "RAG query failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return success_response(
        RAGQueryResponse(
            answer=rag_answer.answer,
            model=rag_answer.model,
            provider=rag_answer.provider,
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
        )
    )
