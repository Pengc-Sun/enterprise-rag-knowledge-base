import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import ChunkEmbeddingStatus, DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider

if TYPE_CHECKING:
    from backend.app.core.config import Settings


@dataclass(frozen=True)
class RetrievalConfig:
    retrieval_top_k: int = 10
    final_context_k: int = 4

    def __post_init__(self) -> None:
        if self.retrieval_top_k <= 0:
            raise ValueError("retrieval_top_k must be positive")
        if self.final_context_k <= 0:
            raise ValueError("final_context_k must be positive")
        if self.final_context_k > self.retrieval_top_k:
            raise ValueError("final_context_k cannot exceed retrieval_top_k")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    similarity_score: float


def create_retrieval_config(settings: "Settings") -> RetrievalConfig:
    return RetrievalConfig(
        retrieval_top_k=settings.retrieval_top_k,
        final_context_k=settings.final_context_k,
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


def build_vector_search_statement(
    knowledge_base_id: uuid.UUID,
    query_embedding: list[float],
    limit: int,
) -> Select[tuple[DocumentChunk, float]]:
    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
    return (
        select(DocumentChunk, distance)
        .where(
            DocumentChunk.knowledge_base_id == knowledge_base_id,
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_status == ChunkEmbeddingStatus.EMBEDDED.value,
        )
        .order_by(distance)
        .limit(limit)
    )
