import uuid
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from backend.app.models.document import Document, DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.llms import (
    LLMMessage,
    LLMProvider,
    LLMProviderName,
    LLMResponse,
    LLMUsage,
)
from backend.app.services.query_rewriting import QueryMessageRole, QueryRewriteMessage
from backend.app.services.rag import (
    answer_knowledge_base_question,
    build_context,
    build_rag_messages,
    build_source_citations,
    build_user_prompt,
)
from backend.app.services.rerankers import RerankedChunk, Reranker
from backend.app.services.retrieval import (
    HybridRetrievedChunk,
    RetrievalConfig,
    RetrievalMetadataFilter,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return 3

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.messages: list[LLMMessage] = []
        self.temperature: float | None = None
        self.max_tokens: int | None = None

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        return LLMResponse(
            content="RAG answer",
            model="test-chat",
            provider=LLMProviderName.DETERMINISTIC,
            usage=LLMUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        )


class FakeReranker(Reranker):
    def __init__(self) -> None:
        self.query: str | None = None
        self.limit: int | None = None

    async def rerank(
        self,
        query: str,
        candidates: list[HybridRetrievedChunk],
        limit: int,
    ) -> list[RerankedChunk]:
        self.query = query
        self.limit = limit
        return [
            RerankedChunk(
                chunk=candidate.chunk,
                rerank_score=0.95 - index,
                rrf_score=candidate.rrf_score,
                vector_score=candidate.vector_score,
                keyword_score=candidate.keyword_score,
            )
            for index, candidate in enumerate(candidates[:limit])
        ]


def make_chunk(index: int, knowledge_base_id: uuid.UUID) -> DocumentChunk:
    now = datetime.now(UTC)
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        filename=f"handbook-{index}.md",
        file_type="md",
        file_size=128,
        file_hash=f"{index}" * 64,
        storage_path=f"storage/uploads/handbook-{index}.md",
        status="completed",
        error_message=None,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        knowledge_base_id=knowledge_base_id,
        content=f"context body {index}",
        chunk_index=index,
        page_number=index + 1,
        section_title="Architecture" if index == 0 else None,
        token_count=3,
        embedding=[1.0, 0.0, 0.0],
        embedding_status="embedded",
        embedding_error=None,
        chunk_metadata={},
        created_at=now,
        updated_at=now,
    )
    chunk.document = document
    return chunk


def test_build_user_prompt_uses_safe_fallback_when_context_is_empty() -> None:
    prompt = build_user_prompt("What is the policy?", [])

    assert "No relevant context was found in this knowledge base." in prompt
    assert "Question:\nWhat is the policy?" in prompt
    assert prompt.endswith("Answer:")


def test_build_context_formats_chunk_locations() -> None:
    knowledge_base_id = uuid.uuid4()
    chunks = [make_chunk(0, knowledge_base_id), make_chunk(1, knowledge_base_id)]

    context = build_context(chunks)

    assert "[Context 1 | chunk_index=0, page=1, section=Architecture]" in context
    assert "context body 0" in context
    assert "[Context 2 | chunk_index=1, page=2]" in context


def test_build_source_citations_returns_document_metadata() -> None:
    knowledge_base_id = uuid.uuid4()
    chunk = make_chunk(0, knowledge_base_id)

    sources = build_source_citations([RerankedChunk(chunk=chunk, rerank_score=0.83, rrf_score=0.1)])

    assert len(sources) == 1
    assert sources[0].document_name == "handbook-0.md"
    assert sources[0].page_number == 1
    assert sources[0].chunk_id == chunk.id
    assert sources[0].original_text == "context body 0"
    assert sources[0].similarity_score == 0.83


def test_build_rag_messages_includes_question_and_empty_context_notice() -> None:
    messages = build_rag_messages("What is the retention policy?", [])

    assert [message.role for message in messages] == ["system", "user"]
    assert "No relevant context was found" in messages[1].content
    assert "What is the retention policy?" in messages[1].content


@pytest.mark.asyncio
async def test_answer_knowledge_base_question_retrieves_context_and_generates_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_base_id = uuid.uuid4()
    chunks = [make_chunk(0, knowledge_base_id), make_chunk(1, knowledge_base_id)]
    llm_provider = FakeLLMProvider()
    reranker = FakeReranker()

    async def fake_retrieve_hybrid_chunks(
        session: object,
        knowledge_base_id: uuid.UUID,
        query: str,
        provider: EmbeddingProvider,
        config: RetrievalConfig | None = None,
        metadata_filter: RetrievalMetadataFilter | None = None,
    ) -> list[HybridRetrievedChunk]:
        assert query == "How does ingestion work about London?"
        assert config == RetrievalConfig(retrieval_top_k=10, final_context_k=2)
        assert metadata_filter == RetrievalMetadataFilter(
            file_types=("md",),
            departments=("engineering",),
        )
        return [
            HybridRetrievedChunk(chunk=chunk, rrf_score=0.1, vector_score=0.8) for chunk in chunks
        ]

    monkeypatch.setattr(
        "backend.app.services.rag.retrieve_hybrid_chunks",
        fake_retrieve_hybrid_chunks,
    )

    answer = await answer_knowledge_base_question(
        session=object(),  # type: ignore[arg-type]
        knowledge_base_id=knowledge_base_id,
        question="What about London?",
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=llm_provider,
        reranker=reranker,
        retrieval_config=RetrievalConfig(retrieval_top_k=10, final_context_k=2),
        history=[
            QueryRewriteMessage(
                role=QueryMessageRole.USER,
                content="How does ingestion work?",
            )
        ],
        metadata_filter=RetrievalMetadataFilter(file_types=("md",), departments=("engineering",)),
        temperature=0.2,
        max_tokens=512,
    )

    assert answer.answer == "RAG answer"
    assert answer.model == "test-chat"
    assert len(answer.context_chunks) == 2
    assert [source.document_name for source in answer.sources] == ["handbook-0.md", "handbook-1.md"]
    assert answer.sources[0].original_text == "context body 0"
    assert answer.sources[0].similarity_score == 0.95
    assert reranker.query == "How does ingestion work about London?"
    assert reranker.limit == 2
    assert "context body 0" in llm_provider.messages[1].content
    assert "How does ingestion work about London?" in llm_provider.messages[1].content
    assert answer.query_rewrite.rewritten_query == "How does ingestion work about London?"
    assert answer.query_rewrite.was_rewritten is True
    assert llm_provider.temperature == 0.2
    assert llm_provider.max_tokens == 512


@pytest.mark.asyncio
async def test_answer_knowledge_base_question_logs_structured_rag_metrics(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_base_id = uuid.uuid4()
    user_id = uuid.uuid4()
    chunk = make_chunk(0, knowledge_base_id)

    async def fake_retrieve_hybrid_chunks(
        session: object,
        knowledge_base_id: uuid.UUID,
        query: str,
        provider: EmbeddingProvider,
        config: RetrievalConfig | None = None,
        metadata_filter: RetrievalMetadataFilter | None = None,
    ) -> list[HybridRetrievedChunk]:
        return [HybridRetrievedChunk(chunk=chunk, rrf_score=0.1, vector_score=0.8)]

    monkeypatch.setattr(
        "backend.app.services.rag.retrieve_hybrid_chunks",
        fake_retrieve_hybrid_chunks,
    )

    with caplog.at_level("INFO", logger="backend.app.services.rag"):
        await answer_knowledge_base_question(
            session=object(),  # type: ignore[arg-type]
            knowledge_base_id=knowledge_base_id,
            question="What is the policy?",
            embedding_provider=FakeEmbeddingProvider(),
            llm_provider=FakeLLMProvider(),
            reranker=FakeReranker(),
            retrieval_config=RetrievalConfig(retrieval_top_k=10, final_context_k=1),
            user_id=user_id,
        )

    rag_records = [record for record in caplog.records if record.message == "rag_query_completed"]
    assert len(rag_records) == 1
    record = cast(Any, rag_records[0])
    fields = cast(dict[str, Any], record.structured_fields)
    assert fields["user_id"] == user_id
    assert fields["knowledge_base_id"] == knowledge_base_id
    assert fields["query"] == "What is the policy?"
    assert fields["retrieved_chunk_ids"] == [chunk.id]
    assert fields["status"] == "success"
    assert fields["error"] is None
    assert fields["token_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert fields["retrieval_latency_ms"] >= 0
    assert fields["rerank_latency_ms"] >= 0
    assert fields["llm_latency_ms"] >= 0
    assert fields["total_latency_ms"] >= 0
