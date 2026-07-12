import uuid
from typing import Any

import pytest

from backend.app.core.config import Settings
from backend.app.models.document import DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.retrieval import (
    RetrievalConfig,
    build_keyword_search_statement,
    build_vector_search_statement,
    create_retrieval_config,
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


def compile_statement(statement: Any) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": False}))
