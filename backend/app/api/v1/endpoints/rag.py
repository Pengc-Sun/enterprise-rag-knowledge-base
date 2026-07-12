import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models.user import User
from backend.app.schemas.rag import (
    RAGMetadataFilter,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGRetrievalDebugCandidateRead,
    RAGRetrievalDebugResponse,
    RAGSourceCitationRead,
)
from backend.app.schemas.response import APIResponse, success_response
from backend.app.services.embeddings import EmbeddingProviderError, create_embedding_provider
from backend.app.services.knowledge_bases import READ_PERMISSIONS, get_knowledge_base_for_user
from backend.app.services.llms import LLMProviderError, create_llm_provider
from backend.app.services.query_rewriting import (
    QueryRewriteMessage,
    create_query_rewrite_config,
)
from backend.app.services.rag import answer_knowledge_base_question
from backend.app.services.rerankers import RerankerError, create_reranker
from backend.app.services.retrieval import RetrievalMetadataFilter, create_retrieval_config
from backend.app.services.retrieval_debug import debug_knowledge_base_retrieval

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
            reranker=create_reranker(settings),
            retrieval_config=create_retrieval_config(settings),
            query_rewrite_config=create_query_rewrite_config(settings),
            history=[
                QueryRewriteMessage(role=item.role, content=item.content)
                for item in query_request.history
            ],
            metadata_filter=build_retrieval_metadata_filter(query_request.filters),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except (EmbeddingProviderError, LLMProviderError, RerankerError, ValueError) as exc:
        message = getattr(exc, "message", "RAG query failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return success_response(
        RAGQueryResponse(
            answer=rag_answer.answer,
            rewritten_question=rag_answer.query_rewrite.rewritten_query,
            question_was_rewritten=rag_answer.query_rewrite.was_rewritten,
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


@router.post("/debug", response_model=APIResponse[RAGRetrievalDebugResponse])
async def debug_knowledge_base_retrieval_endpoint(
    knowledge_base_id: uuid.UUID,
    query_request: RAGQueryRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[RAGRetrievalDebugResponse]:
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
        debug_result = await debug_knowledge_base_retrieval(
            session=session,
            knowledge_base_id=knowledge_base.id,
            question=query_request.question,
            embedding_provider=create_embedding_provider(settings),
            reranker=create_reranker(settings),
            retrieval_config=create_retrieval_config(settings),
            query_rewrite_config=create_query_rewrite_config(settings),
            history=[
                QueryRewriteMessage(role=item.role, content=item.content)
                for item in query_request.history
            ],
            metadata_filter=build_retrieval_metadata_filter(query_request.filters),
        )
    except (EmbeddingProviderError, RerankerError, ValueError) as exc:
        message = getattr(exc, "message", "Retrieval debug query failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    return success_response(
        RAGRetrievalDebugResponse(
            original_question=debug_result.query_rewrite.original_query,
            rewritten_question=debug_result.query_rewrite.rewritten_query,
            question_was_rewritten=debug_result.query_rewrite.was_rewritten,
            candidate_count=len(debug_result.candidates),
            candidates=[
                RAGRetrievalDebugCandidateRead(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    document_name=candidate.document_name,
                    chunk_index=candidate.chunk_index,
                    page_number=candidate.page_number,
                    section_title=candidate.section_title,
                    content_preview=candidate.content_preview,
                    vector_rank=candidate.vector_rank,
                    keyword_rank=candidate.keyword_rank,
                    vector_score=candidate.vector_score,
                    keyword_score=candidate.keyword_score,
                    rrf_score=candidate.rrf_score,
                    rerank_score=candidate.rerank_score,
                    final_rank=candidate.final_rank,
                )
                for candidate in debug_result.candidates
            ],
        )
    )


def build_retrieval_metadata_filter(filters: RAGMetadataFilter) -> RetrievalMetadataFilter:
    return RetrievalMetadataFilter(
        document_ids=tuple(filters.document_ids),
        file_types=tuple(filters.file_types),
        created_after=filters.created_after,
        created_before=filters.created_before,
        departments=tuple(filters.departments),
        permissions=tuple(filters.permissions),
    )
