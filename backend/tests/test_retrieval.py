import uuid
from typing import Any

import pytest

from backend.app.core.config import Settings
from backend.app.models.document import DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.retrieval import (
    KeywordRetrievedChunk,
    RetrievalConfig,
    RetrievedChunk,
    build_keyword_search_statement,
    build_vector_search_statement,
    create_retrieval_config,
    merge_hybrid_results,
    retrieve_hybrid_chunks,
    retrieve_keyword_chunks,
    retrieve_similar_chunks,
)


class FakeResult:
    def __init__(self, rows: list[tuple[DocumentChunk, float]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[DocumentChunk, float]]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[tuple[DocumentChunk, float]]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        return FakeResult(self.rows)


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.queries: list[str] = []

    @property
    def dimension(self) -> int:
        return 3

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [1.0, 0.0, 0.0]


def make_chunk(index: int, knowledge_base_id: uuid.UUID) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        content=f"chunk {index}",
        chunk_index=index,
        page_number=1,
        token_count=2,
        embedding=[1.0, 0.0, 0.0],
        embedding_status="embedded",
        chunk_metadata={},
    )


def test_retrieval_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        RetrievalConfig(retrieval_top_k=0)

    with pytest.raises(ValueError):
        RetrievalConfig(retrieval_top_k=2, final_context_k=0)

    with pytest.raises(ValueError):
        RetrievalConfig(retrieval_top_k=2, final_context_k=3)


def test_create_retrieval_config_uses_settings() -> None:
    settings = Settings(retrieval_top_k=12, final_context_k=5)

    config = create_retrieval_config(settings)

    assert config.retrieval_top_k == 12
    assert config.final_context_k == 5


def test_build_vector_search_statement_filters_and_orders() -> None:
    knowledge_base_id = uuid.uuid4()

    statement = build_vector_search_statement(
        knowledge_base_id=knowledge_base_id,
        query_embedding=[1.0, 0.0, 0.0],
        limit=10,
    )
    sql = compile_statement(statement)

    assert "document_chunks.knowledge_base_id" in sql
    assert "document_chunks.embedding IS NOT NULL" in sql
    assert "document_chunks.embedding_status" in sql
    assert "embedding <=>" in sql
    assert "ORDER BY distance" in sql
    assert "LIMIT" in sql


def test_build_keyword_search_statement_uses_postgresql_full_text_search() -> None:
    knowledge_base_id = uuid.uuid4()

    statement = build_keyword_search_statement(
        knowledge_base_id=knowledge_base_id,
        query="POLICY-2024-IT-07",
        limit=10,
    )
    sql = compile_statement(statement)

    assert "document_chunks.knowledge_base_id" in sql
    assert "websearch_to_tsquery" in sql
    assert "document_chunks.search_vector @@" in sql
    assert "ts_rank_cd" in sql
    assert "ORDER BY keyword_score DESC" in sql
    assert "document_chunks.chunk_index ASC" in sql
    assert "LIMIT" in sql


@pytest.mark.parametrize(
    "query",
    [
        "POLICY-2024-IT-07",
        "A100-X9",
        "ERR_AUTH_401",
    ],
)
def test_build_keyword_search_statement_accepts_codes_policy_numbers_and_models(
    query: str,
) -> None:
    statement = build_keyword_search_statement(
        knowledge_base_id=uuid.uuid4(),
        query=query,
        limit=5,
    )

    assert "websearch_to_tsquery" in compile_statement(statement)


def test_merge_hybrid_results_deduplicates_chunks_and_preserves_vector_order() -> None:
    knowledge_base_id = uuid.uuid4()
    vector_only_chunk = make_chunk(0, knowledge_base_id)
    shared_chunk = make_chunk(1, knowledge_base_id)
    keyword_only_chunk = make_chunk(2, knowledge_base_id)

    candidates = merge_hybrid_results(
        vector_results=[
            RetrievedChunk(chunk=vector_only_chunk, similarity_score=0.9),
            RetrievedChunk(chunk=shared_chunk, similarity_score=0.7),
        ],
        keyword_results=[
            KeywordRetrievedChunk(chunk=shared_chunk, keyword_score=0.8),
            KeywordRetrievedChunk(chunk=keyword_only_chunk, keyword_score=0.6),
        ],
        limit=10,
    )

    assert [item.chunk.id for item in candidates] == [
        vector_only_chunk.id,
        shared_chunk.id,
        keyword_only_chunk.id,
    ]
    assert candidates[0].vector_score == 0.9
    assert candidates[0].keyword_score is None
    assert candidates[1].vector_score == 0.7
    assert candidates[1].keyword_score == 0.8
    assert candidates[2].vector_score is None
    assert candidates[2].keyword_score == 0.6


def test_merge_hybrid_results_applies_final_limit() -> None:
    knowledge_base_id = uuid.uuid4()
    candidates = merge_hybrid_results(
        vector_results=[
            RetrievedChunk(chunk=make_chunk(0, knowledge_base_id), similarity_score=0.9),
            RetrievedChunk(chunk=make_chunk(1, knowledge_base_id), similarity_score=0.8),
        ],
        keyword_results=[
            KeywordRetrievedChunk(chunk=make_chunk(2, knowledge_base_id), keyword_score=0.7),
        ],
        limit=2,
    )

    assert [item.chunk.chunk_index for item in candidates] == [0, 1]


def test_merge_hybrid_results_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError):
        merge_hybrid_results(vector_results=[], keyword_results=[], limit=0)


@pytest.mark.asyncio
async def test_retrieve_similar_chunks_embeds_query_and_returns_final_context() -> None:
    knowledge_base_id = uuid.uuid4()
    rows = [
        (make_chunk(0, knowledge_base_id), 0.1),
        (make_chunk(1, knowledge_base_id), 0.2),
        (make_chunk(2, knowledge_base_id), 0.5),
    ]
    session = FakeSession(rows)
    provider = FakeEmbeddingProvider()

    retrieved_chunks = await retrieve_similar_chunks(
        session,  # type: ignore[arg-type]
        knowledge_base_id=knowledge_base_id,
        query="What is the plan?",
        provider=provider,
        config=RetrievalConfig(retrieval_top_k=3, final_context_k=2),
    )

    assert provider.queries == ["What is the plan?"]
    assert session.statement is not None
    assert [item.chunk.chunk_index for item in retrieved_chunks] == [0, 1]
    assert [item.similarity_score for item in retrieved_chunks] == [0.9, 0.8]


@pytest.mark.asyncio
async def test_retrieve_keyword_chunks_returns_keyword_scores() -> None:
    knowledge_base_id = uuid.uuid4()
    rows = [
        (make_chunk(0, knowledge_base_id), 0.8),
        (make_chunk(1, knowledge_base_id), 0.4),
    ]
    session = FakeSession(rows)

    retrieved_chunks = await retrieve_keyword_chunks(
        session,  # type: ignore[arg-type]
        knowledge_base_id=knowledge_base_id,
        query="A100-X9",
        limit=5,
    )

    assert session.statement is not None
    assert [item.chunk.chunk_index for item in retrieved_chunks] == [0, 1]
    assert [item.keyword_score for item in retrieved_chunks] == [0.8, 0.4]


@pytest.mark.asyncio
async def test_retrieve_keyword_chunks_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError):
        await retrieve_keyword_chunks(
            FakeSession([]),  # type: ignore[arg-type]
            knowledge_base_id=uuid.uuid4(),
            query="policy",
            limit=0,
        )


@pytest.mark.asyncio
async def test_retrieve_hybrid_chunks_runs_vector_and_keyword_searches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_base_id = uuid.uuid4()
    vector_chunk = make_chunk(0, knowledge_base_id)
    keyword_chunk = make_chunk(1, knowledge_base_id)
    calls: list[str] = []

    async def fake_retrieve_similar_chunks(
        session: object,
        knowledge_base_id: uuid.UUID,
        query: str,
        provider: EmbeddingProvider,
        config: RetrievalConfig | None = None,
    ) -> list[RetrievedChunk]:
        calls.append("vector")
        assert query == "POLICY-2024-IT-07"
        assert config == RetrievalConfig(retrieval_top_k=4, final_context_k=4)
        return [RetrievedChunk(chunk=vector_chunk, similarity_score=0.9)]

    async def fake_retrieve_keyword_chunks(
        session: object,
        knowledge_base_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[KeywordRetrievedChunk]:
        calls.append("keyword")
        assert query == "POLICY-2024-IT-07"
        assert limit == 4
        return [KeywordRetrievedChunk(chunk=keyword_chunk, keyword_score=0.7)]

    monkeypatch.setattr(
        "backend.app.services.retrieval.retrieve_similar_chunks",
        fake_retrieve_similar_chunks,
    )
    monkeypatch.setattr(
        "backend.app.services.retrieval.retrieve_keyword_chunks",
        fake_retrieve_keyword_chunks,
    )

    candidates = await retrieve_hybrid_chunks(
        session=object(),  # type: ignore[arg-type]
        knowledge_base_id=knowledge_base_id,
        query="POLICY-2024-IT-07",
        provider=FakeEmbeddingProvider(),
        config=RetrievalConfig(retrieval_top_k=4, final_context_k=2),
    )

    assert calls == ["vector", "keyword"]
    assert [item.chunk.chunk_index for item in candidates] == [0, 1]
    assert candidates[0].vector_score == 0.9
    assert candidates[0].keyword_score is None
    assert candidates[1].vector_score is None
    assert candidates[1].keyword_score == 0.7


def compile_statement(statement: Any) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": False}))
