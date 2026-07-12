import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.document import ChunkEmbeddingStatus, DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider

if TYPE_CHECKING:
    from backend.app.core.config import Settings


@dataclass(frozen=True)
class RetrievalConfig:
    retrieval_top_k: int = 10
    final_context_k: int = 4
    hybrid_source_top_k: int = 20
    hybrid_candidate_top_k: int = 10
    rrf_k: int = 60

    def __post_init__(self) -> None:
        if self.retrieval_top_k <= 0:
            raise ValueError("retrieval_top_k must be positive")
        if self.final_context_k <= 0:
            raise ValueError("final_context_k must be positive")
        if self.final_context_k > self.retrieval_top_k:
            raise ValueError("final_context_k cannot exceed retrieval_top_k")
        if self.hybrid_source_top_k <= 0:
            raise ValueError("hybrid_source_top_k must be positive")
        if self.hybrid_candidate_top_k <= 0:
            raise ValueError("hybrid_candidate_top_k must be positive")
        if self.rrf_k <= 0:
            raise ValueError("rrf_k must be positive")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    similarity_score: float


@dataclass(frozen=True)
class KeywordRetrievedChunk:
    chunk: DocumentChunk
    keyword_score: float


@dataclass(frozen=True)
class HybridRetrievedChunk:
    chunk: DocumentChunk
    rrf_score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None
    vector_score: float | None = None
    keyword_score: float | None = None


def create_retrieval_config(settings: "Settings") -> RetrievalConfig:
    return RetrievalConfig(
        retrieval_top_k=settings.retrieval_top_k,
        final_context_k=settings.final_context_k,
        hybrid_source_top_k=settings.hybrid_source_top_k,
        hybrid_candidate_top_k=settings.hybrid_candidate_top_k,
        rrf_k=settings.rrf_k,
    )


async def retrieve_similar_chunks(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    query: str,
    provider: EmbeddingProvider,
    config: RetrievalConfig | None = None,
) -> list[RetrievedChunk]:
    effective_config = config or RetrievalConfig()
    query_embedding = await provider.embed_query(query)

    result = await session.execute(
        build_vector_search_statement(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            limit=effective_config.retrieval_top_k,
        )
    )

    candidates = [
        RetrievedChunk(
            chunk=cast(DocumentChunk, row[0]),
            similarity_score=1.0 - float(row[1]),
        )
        for row in result.all()
    ]
    return candidates[: effective_config.final_context_k]


async def retrieve_keyword_chunks(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    query: str,
    limit: int,
) -> list[KeywordRetrievedChunk]:
    if limit <= 0:
        raise ValueError("limit must be positive")

    result = await session.execute(
        build_keyword_search_statement(
            knowledge_base_id=knowledge_base_id,
            query=query,
            limit=limit,
        )
    )
    return [
        KeywordRetrievedChunk(
            chunk=cast(DocumentChunk, row[0]),
            keyword_score=float(row[1]),
        )
        for row in result.all()
    ]


async def retrieve_hybrid_chunks(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    query: str,
    provider: EmbeddingProvider,
    config: RetrievalConfig | None = None,
) -> list[HybridRetrievedChunk]:
    effective_config = config or RetrievalConfig()
    source_config = RetrievalConfig(
        retrieval_top_k=effective_config.hybrid_source_top_k,
        final_context_k=effective_config.hybrid_source_top_k,
        hybrid_source_top_k=effective_config.hybrid_source_top_k,
        hybrid_candidate_top_k=effective_config.hybrid_candidate_top_k,
        rrf_k=effective_config.rrf_k,
    )
    vector_results = await retrieve_similar_chunks(
        session=session,
        knowledge_base_id=knowledge_base_id,
        query=query,
        provider=provider,
        config=source_config,
    )
    keyword_results = await retrieve_keyword_chunks(
        session=session,
        knowledge_base_id=knowledge_base_id,
        query=query,
        limit=effective_config.hybrid_source_top_k,
    )
    return reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
        limit=effective_config.hybrid_candidate_top_k,
        rrf_k=effective_config.rrf_k,
    )


def reciprocal_rank_fusion(
    vector_results: list[RetrievedChunk],
    keyword_results: list[KeywordRetrievedChunk],
    limit: int,
    rrf_k: int = 60,
) -> list[HybridRetrievedChunk]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")

    candidates: dict[uuid.UUID, HybridRetrievedChunk] = {}

    for rank, vector_item in enumerate(vector_results, 1):
        chunk_id = vector_item.chunk.id
        candidates[chunk_id] = HybridRetrievedChunk(
            chunk=vector_item.chunk,
            rrf_score=reciprocal_rank_score(rank, rrf_k),
            vector_rank=rank,
            vector_score=vector_item.similarity_score,
        )

    for rank, keyword_item in enumerate(keyword_results, 1):
        chunk_id = keyword_item.chunk.id
        existing_candidate = candidates.get(chunk_id)
        keyword_rrf_score = reciprocal_rank_score(rank, rrf_k)
        if existing_candidate is None:
            candidates[chunk_id] = HybridRetrievedChunk(
                chunk=keyword_item.chunk,
                rrf_score=keyword_rrf_score,
                keyword_rank=rank,
                keyword_score=keyword_item.keyword_score,
            )
        else:
            candidates[chunk_id] = HybridRetrievedChunk(
                chunk=existing_candidate.chunk,
                rrf_score=existing_candidate.rrf_score + keyword_rrf_score,
                vector_rank=existing_candidate.vector_rank,
                keyword_rank=rank,
                vector_score=existing_candidate.vector_score,
                keyword_score=keyword_item.keyword_score,
            )

    return sorted(
        candidates.values(),
        key=hybrid_candidate_sort_key,
    )[:limit]


def reciprocal_rank_score(rank: int, rrf_k: int = 60) -> float:
    if rank <= 0:
        raise ValueError("rank must be positive")
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")
    return 1.0 / (rrf_k + rank)


def hybrid_candidate_sort_key(candidate: HybridRetrievedChunk) -> tuple[float, int, int]:
    ranks = [rank for rank in (candidate.vector_rank, candidate.keyword_rank) if rank is not None]
    best_rank = min(ranks) if ranks else 0
    return (-candidate.rrf_score, best_rank, candidate.chunk.chunk_index)


# Backward-compatible alias for Day30 callers; Day31 uses RRF for hybrid merging.
def merge_hybrid_results(
    vector_results: list[RetrievedChunk],
    keyword_results: list[KeywordRetrievedChunk],
    limit: int,
) -> list[HybridRetrievedChunk]:
    return reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
        limit=limit,
    )


def build_vector_search_statement(
    knowledge_base_id: uuid.UUID,
    query_embedding: list[float],
    limit: int,
) -> Select[tuple[DocumentChunk, float]]:
    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
    return (
        select(DocumentChunk, distance)
        .options(selectinload(DocumentChunk.document))
        .where(
            DocumentChunk.knowledge_base_id == knowledge_base_id,
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_status == ChunkEmbeddingStatus.EMBEDDED.value,
        )
        .order_by(distance)
        .limit(limit)
    )


def build_keyword_search_statement(
    knowledge_base_id: uuid.UUID,
    query: str,
    limit: int,
) -> Select[tuple[DocumentChunk, float]]:
    ts_query = func.websearch_to_tsquery("simple", query)
    rank = func.ts_rank_cd(DocumentChunk.search_vector, ts_query).label("keyword_score")
    return (
        select(DocumentChunk, rank)
        .options(selectinload(DocumentChunk.document))
        .where(
            DocumentChunk.knowledge_base_id == knowledge_base_id,
            DocumentChunk.search_vector.op("@@")(ts_query),
        )
        .order_by(rank.desc(), DocumentChunk.chunk_index.asc())
        .limit(limit)
    )
