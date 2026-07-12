import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.llms import LLMMessage, LLMProvider, LLMProviderName
from backend.app.services.rerankers import RerankedChunk, Reranker
from backend.app.services.retrieval import RetrievalConfig, retrieve_hybrid_chunks

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


async def answer_knowledge_base_question(
    session: AsyncSession,
    knowledge_base_id: uuid.UUID,
    question: str,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    reranker: Reranker,
    retrieval_config: RetrievalConfig,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> RAGAnswer:
    candidate_chunks = await retrieve_hybrid_chunks(
        session=session,
        knowledge_base_id=knowledge_base_id,
        query=question,
        provider=embedding_provider,
        config=retrieval_config,
    )
    retrieved_chunks = await reranker.rerank(
        query=question,
        candidates=candidate_chunks,
        limit=retrieval_config.final_context_k,
    )
    messages = build_rag_messages(question, [item.chunk for item in retrieved_chunks])
    llm_response = await llm_provider.generate(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return RAGAnswer(
        answer=llm_response.content,
        model=llm_response.model,
        provider=llm_response.provider,
        context_chunks=retrieved_chunks,
        sources=build_source_citations(retrieved_chunks),
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
