import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import log_structured
from backend.app.models.document import DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.llms import LLMMessage, LLMProvider, LLMProviderName, LLMUsage
from backend.app.services.query_rewriting import (
    QueryRewriteConfig,
    QueryRewriteMessage,
    QueryRewriteResult,
    rewrite_query,
)
from backend.app.services.rerankers import RerankedChunk, Reranker
from backend.app.services.retrieval import (
    RetrievalConfig,
    RetrievalMetadataFilter,
    retrieve_hybrid_chunks,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an enterprise knowledge base assistant. Answer only from the provided "
    "context. If the context is insufficient, say that the knowledge base does not "
    "contain enough information to answer."
)


@dataclass(frozen=True)
class RAGSourceCitation:
    document_name: str
    page_number: int
    chunk_id: uuid.UUID
    original_text: str
    similarity_score: float


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    model: str
    provider: LLMProviderName
    context_chunks: list[RerankedChunk]
    sources: list[RAGSourceCitation]
    query_rewrite: QueryRewriteResult


async def answer_knowledge_base_question(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    question: str,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    reranker: Reranker,
    retrieval_config: RetrievalConfig,
    query_rewrite_config: QueryRewriteConfig | None = None,
    history: list[QueryRewriteMessage] | None = None,
    metadata_filter: RetrievalMetadataFilter | None = None,
    user_id: uuid.UUID | None = None,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> RAGAnswer:
    started_at = time.perf_counter()
    retrieval_latency_ms = 0.0
    rerank_latency_ms = 0.0
    llm_latency_ms = 0.0
    retrieved_chunks: list[RerankedChunk] = []
    llm_usage: LLMUsage | None = None
    query_rewrite = rewrite_query(question, history or [], query_rewrite_config)
    retrieval_query = query_rewrite.rewritten_query

    try:
        retrieval_started_at = time.perf_counter()
        candidate_chunks = await retrieve_hybrid_chunks(
            session=session,
            knowledge_base_id=knowledge_base_id,
            query=retrieval_query,
            provider=embedding_provider,
            config=retrieval_config,
            metadata_filter=metadata_filter,
        )
        retrieval_latency_ms = elapsed_ms(retrieval_started_at)

        rerank_started_at = time.perf_counter()
        retrieved_chunks = await reranker.rerank(
            query=retrieval_query,
            candidates=candidate_chunks,
            limit=retrieval_config.final_context_k,
        )
        rerank_latency_ms = elapsed_ms(rerank_started_at)

        messages = build_rag_messages(retrieval_query, [item.chunk for item in retrieved_chunks])
        llm_started_at = time.perf_counter()
        llm_response = await llm_provider.generate(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        llm_latency_ms = elapsed_ms(llm_started_at)
        llm_usage = llm_response.usage
        log_rag_query(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query=retrieval_query,
            retrieved_chunks=retrieved_chunks,
            retrieval_latency_ms=retrieval_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            llm_latency_ms=llm_latency_ms,
            total_latency_ms=elapsed_ms(started_at),
            token_usage=llm_usage,
            status="success",
            error=None,
        )
    except Exception as exc:
        log_rag_query(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query=retrieval_query,
            retrieved_chunks=retrieved_chunks,
            retrieval_latency_ms=retrieval_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            llm_latency_ms=llm_latency_ms,
            total_latency_ms=elapsed_ms(started_at),
            token_usage=llm_usage,
            status="error",
            error=str(exc),
        )
        raise

    return RAGAnswer(
        answer=llm_response.content,
        model=llm_response.model,
        provider=llm_response.provider,
        context_chunks=retrieved_chunks,
        sources=build_source_citations(retrieved_chunks),
        query_rewrite=query_rewrite,
    )


def build_source_citations(retrieved_chunks: list[RerankedChunk]) -> list[RAGSourceCitation]:
    return [
        RAGSourceCitation(
            document_name=item.chunk.document.filename,
            page_number=item.chunk.page_number,
            chunk_id=item.chunk.id,
            original_text=item.chunk.content,
            similarity_score=item.rerank_score,
        )
        for item in retrieved_chunks
    ]


def build_rag_messages(question: str, chunks: list[DocumentChunk]) -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=build_user_prompt(question, chunks)),
    ]


def build_user_prompt(question: str, chunks: list[DocumentChunk]) -> str:
    context = build_context(chunks)
    if not context:
        context = "No relevant context was found in this knowledge base."
    return f"Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"


def build_context(chunks: list[DocumentChunk]) -> str:
    return "\n\n".join(format_context_chunk(index, chunk) for index, chunk in enumerate(chunks, 1))


def format_context_chunk(index: int, chunk: DocumentChunk) -> str:
    location_parts = [f"chunk_index={chunk.chunk_index}", f"page={chunk.page_number}"]
    if chunk.section_title:
        location_parts.append(f"section={chunk.section_title}")
    location = ", ".join(location_parts)
    return f"[Context {index} | {location}]\n{chunk.content}"


def elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 3)


def log_rag_query(
    *,
    user_id: uuid.UUID | None,
    knowledge_base_id: uuid.UUID,
    query: str,
    retrieved_chunks: list[RerankedChunk],
    retrieval_latency_ms: float,
    rerank_latency_ms: float,
    llm_latency_ms: float,
    total_latency_ms: float,
    token_usage: LLMUsage | None,
    status: str,
    error: str | None,
) -> None:
    log_structured(
        logger,
        logging.ERROR if error else logging.INFO,
        "rag_query_completed",
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        query=query,
        retrieved_chunk_ids=[item.chunk.id for item in retrieved_chunks],
        retrieval_latency_ms=retrieval_latency_ms,
        rerank_latency_ms=rerank_latency_ms,
        llm_latency_ms=llm_latency_ms,
        total_latency_ms=total_latency_ms,
        token_usage=serialize_token_usage(token_usage),
        status=status,
        error=error,
    )


def serialize_token_usage(token_usage: LLMUsage | None) -> dict[str, int | None] | None:
    if token_usage is None:
        return None
    return {
        "prompt_tokens": token_usage.prompt_tokens,
        "completion_tokens": token_usage.completion_tokens,
        "total_tokens": token_usage.total_tokens,
    }
