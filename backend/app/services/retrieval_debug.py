import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.query_rewriting import (
    QueryRewriteConfig,
    QueryRewriteMessage,
    QueryRewriteResult,
    rewrite_query,
)
from backend.app.services.rerankers import Reranker
from backend.app.services.retrieval import (
    HybridRetrievedChunk,
    RetrievalConfig,
    RetrievalMetadataFilter,
    retrieve_hybrid_chunks,
)


@dataclass(frozen=True)
class RetrievalDebugCandidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    chunk_index: int
    page_number: int
    section_title: str | None
    content_preview: str
    vector_rank: int | None
    keyword_rank: int | None
    vector_score: float | None
    keyword_score: float | None
    rrf_score: float
    rerank_score: float
    final_rank: int


@dataclass(frozen=True)
class RetrievalDebugResult:
    query_rewrite: QueryRewriteResult
    candidates: list[RetrievalDebugCandidate]


async def debug_knowledge_base_retrieval(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    question: str,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    retrieval_config: RetrievalConfig,
    query_rewrite_config: QueryRewriteConfig | None = None,
    history: list[QueryRewriteMessage] | None = None,
    metadata_filter: RetrievalMetadataFilter | None = None,
) -> RetrievalDebugResult:
    query_rewrite = rewrite_query(question, history or [], query_rewrite_config)
    retrieval_query = query_rewrite.rewritten_query
    hybrid_candidates = await retrieve_hybrid_chunks(
        session=session,
        knowledge_base_id=knowledge_base_id,
        query=retrieval_query,
        provider=embedding_provider,
        config=retrieval_config,
        metadata_filter=metadata_filter,
    )
    if not hybrid_candidates:
        return RetrievalDebugResult(query_rewrite=query_rewrite, candidates=[])

    candidate_by_chunk_id = {candidate.chunk.id: candidate for candidate in hybrid_candidates}
    reranked_candidates = await reranker.rerank(
        query=retrieval_query,
        candidates=hybrid_candidates,
        limit=len(hybrid_candidates),
    )
    return RetrievalDebugResult(
        query_rewrite=query_rewrite,
        candidates=[
            build_debug_candidate(
                final_rank=rank,
                hybrid_candidate=candidate_by_chunk_id[item.chunk.id],
                rerank_score=item.rerank_score,
            )
            for rank, item in enumerate(reranked_candidates, 1)
        ],
    )


def build_debug_candidate(
    final_rank: int,
    hybrid_candidate: HybridRetrievedChunk,
    rerank_score: float,
) -> RetrievalDebugCandidate:
    chunk = hybrid_candidate.chunk
    return RetrievalDebugCandidate(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_name=chunk.document.filename,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        section_title=chunk.section_title,
        content_preview=build_content_preview(chunk.content),
        vector_rank=hybrid_candidate.vector_rank,
        keyword_rank=hybrid_candidate.keyword_rank,
        vector_score=hybrid_candidate.vector_score,
        keyword_score=hybrid_candidate.keyword_score,
        rrf_score=hybrid_candidate.rrf_score,
        rerank_score=rerank_score,
        final_rank=final_rank,
    )


def build_content_preview(content: str, limit: int = 240) -> str:
    normalized_content = " ".join(content.split())
    if len(normalized_content) <= limit:
        return normalized_content
    return f"{normalized_content[: limit - 3]}..."
