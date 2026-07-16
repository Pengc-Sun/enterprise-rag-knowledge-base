import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from backend.app.core.config import Settings
from backend.app.models.document import DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.retrieval import (
    KeywordRetrievedChunk,
    RetrievalConfig,
    RetrievalMetadataFilter,
    RetrievedChunk,
    build_keyword_search_statement,
    build_vector_search_statement,
    create_retrieval_config,
    merge_hybrid_results,
    reciprocal_rank_fusion,
    reciprocal_rank_score,
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


def make_chunk(
    index: int,
    knowledge_base_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
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

    with pytest.raises(ValueError):
        RetrievalConfig(hybrid_source_top_k=0)

    with pytest.raises(ValueError):
        RetrievalConfig(hybrid_candidate_top_k=0)

    with pytest.raises(ValueError):
        RetrievalConfig(rrf_k=0)


def test_create_retrieval_config_uses_settings() -> None:
    settings = Settings(
        retrieval_top_k=12,
        final_context_k=5,
        hybrid_source_top_k=20,
        hybrid_candidate_top_k=10,
        rrf_k=50,
    )

    config = create_retrieval_config(settings)

    assert config.retrieval_top_k == 12
    assert config.final_context_k == 5
    assert config.hybrid_source_top_k == 20
    assert config.hybrid_candidate_top_k == 10
    assert config.rrf_k == 50


def test_retrieval_metadata_filter_reports_when_empty_or_populated() -> None:
    assert RetrievalMetadataFilter().has_filters is False
    assert RetrievalMetadataFilter(file_types=("pdf",)).has_filters is True


def test_retrieval_metadata_filter_rejects_invalid_date_range() -> None:
    with pytest.raises(ValueError, match="created_after cannot be later than created_before"):
        RetrievalMetadataFilter(
            created_after=datetime(2026, 2, 1, tzinfo=UTC),
            created_before=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_build_vector_search_statement_applies_metadata_filters() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()

    statement = build_vector_search_statement(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        query_embedding=[1.0, 0.0, 0.0],
        limit=10,
        metadata_filter=RetrievalMetadataFilter(
            document_ids=(document_id,),
            file_types=("pdf",),
            created_after=datetime(2026, 1, 1, tzinfo=UTC),
            created_before=datetime(2026, 1, 31, tzinfo=UTC),
            departments=("legal",),
            permissions=("internal",),
        ),
    )
    sql = compile_statement(statement)

    assert "document_chunks.document_id IN" in sql
    assert "EXISTS" in sql
    assert "documents.file_type IN" in sql
    assert "documents.created_at >= " in sql
    assert "documents.created_at <= " in sql
    assert "document_chunks.metadata" in sql
    assert "->>" in sql


def test_build_vector_search_statement_filters_and_orders() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()

    statement = build_vector_search_statement(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        query_embedding=[1.0, 0.0, 0.0],
        limit=10,
    )
    sql = compile_statement(statement)

    assert "document_chunks.workspace_id" in sql
    assert "document_chunks.knowledge_base_id" in sql
    assert "document_chunks.embedding IS NOT NULL" in sql
    assert "document_chunks.embedding_status" in sql
    assert "embedding <=>" in sql
    assert "ORDER BY distance" in sql
    assert "LIMIT" in sql


def test_vector_search_binds_workspace_and_knowledge_base_ids() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()

    statement = build_vector_search_statement(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        query_embedding=[1.0, 0.0, 0.0],
        limit=10,
    )
    params = compile_params(statement)

    assert params["workspace_id_1"] == workspace_id
    assert params["workspace_id_1"] != other_workspace_id
    assert params["knowledge_base_id_1"] == knowledge_base_id


def test_build_keyword_search_statement_uses_postgresql_full_text_search() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()

    statement = build_keyword_search_statement(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        query="POLICY-2024-IT-07",
        limit=10,
    )
    sql = compile_statement(statement)

    assert "document_chunks.workspace_id" in sql
    assert "document_chunks.knowledge_base_id" in sql
    assert "websearch_to_tsquery" in sql
    assert "document_chunks.search_vector @@" in sql
    assert "ts_rank_cd" in sql
    assert "ORDER BY keyword_score DESC" in sql
    assert "document_chunks.chunk_index ASC" in sql
    assert "LIMIT" in sql


def test_keyword_search_binds_workspace_and_knowledge_base_ids() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()

    statement = build_keyword_search_statement(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        query="travel policy",
        limit=10,
    )
    params = compile_params(statement)

    assert params["workspace_id_1"] == workspace_id
    assert params["workspace_id_1"] != other_workspace_id
    assert params["knowledge_base_id_1"] == knowledge_base_id


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
        workspace_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        query=query,
        limit=5,
    )

    assert "websearch_to_tsquery" in compile_statement(statement)


def test_reciprocal_rank_score_uses_rank_and_rrf_k() -> None:
    assert reciprocal_rank_score(rank=1, rrf_k=60) == pytest.approx(1 / 61)
    assert reciprocal_rank_score(rank=10, rrf_k=60) == pytest.approx(1 / 70)

    with pytest.raises(ValueError):
        reciprocal_rank_score(rank=0)

    with pytest.raises(ValueError):
        reciprocal_rank_score(rank=1, rrf_k=0)


def test_reciprocal_rank_fusion_deduplicates_and_ranks_shared_matches_first() -> None:
    knowledge_base_id = uuid.uuid4()
    vector_only_chunk = make_chunk(0, knowledge_base_id)
    shared_chunk = make_chunk(1, knowledge_base_id)
    keyword_only_chunk = make_chunk(2, knowledge_base_id)

    candidates = reciprocal_rank_fusion(
        vector_results=[
            RetrievedChunk(chunk=vector_only_chunk, similarity_score=0.9),
            RetrievedChunk(chunk=shared_chunk, similarity_score=0.7),
        ],
        keyword_results=[
            KeywordRetrievedChunk(chunk=shared_chunk, keyword_score=0.8),
            KeywordRetrievedChunk(chunk=keyword_only_chunk, keyword_score=0.6),
        ],
        limit=10,
        rrf_k=60,
    )

    assert [item.chunk.id for item in candidates] == [
        shared_chunk.id,
        vector_only_chunk.id,
        keyword_only_chunk.id,
    ]
    assert candidates[0].rrf_score == pytest.approx((1 / 62) + (1 / 61))
    assert candidates[0].vector_rank == 2
    assert candidates[0].keyword_rank == 1
    assert candidates[0].vector_score == 0.7
    assert candidates[0].keyword_score == 0.8
    assert candidates[1].rrf_score == pytest.approx(1 / 61)
    assert candidates[1].vector_rank == 1
    assert candidates[1].keyword_rank is None
    assert candidates[2].rrf_score == pytest.approx(1 / 62)
    assert candidates[2].vector_rank is None
    assert candidates[2].keyword_rank == 2


def test_reciprocal_rank_fusion_applies_candidate_limit() -> None:
    knowledge_base_id = uuid.uuid4()
    candidates = reciprocal_rank_fusion(
        vector_results=[
            RetrievedChunk(chunk=make_chunk(0, knowledge_base_id), similarity_score=0.9),
            RetrievedChunk(chunk=make_chunk(1, knowledge_base_id), similarity_score=0.8),
        ],
        keyword_results=[
            KeywordRetrievedChunk(chunk=make_chunk(2, knowledge_base_id), keyword_score=0.7),
        ],
        limit=2,
    )

    assert len(candidates) == 2


def test_reciprocal_rank_fusion_rejects_invalid_settings() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion(vector_results=[], keyword_results=[], limit=0)

    with pytest.raises(ValueError):
        reciprocal_rank_fusion(vector_results=[], keyword_results=[], limit=1, rrf_k=0)


def test_merge_hybrid_results_uses_rrf_for_backward_compatibility() -> None:
    knowledge_base_id = uuid.uuid4()
    shared_chunk = make_chunk(0, knowledge_base_id)

    candidates = merge_hybrid_results(
        vector_results=[RetrievedChunk(chunk=shared_chunk, similarity_score=0.9)],
        keyword_results=[KeywordRetrievedChunk(chunk=shared_chunk, keyword_score=0.8)],
        limit=1,
    )

    assert candidates[0].rrf_score == pytest.approx((1 / 61) + (1 / 61))
    assert candidates[0].vector_rank == 1
    assert candidates[0].keyword_rank == 1


@pytest.mark.asyncio
async def test_retrieve_similar_chunks_embeds_query_and_returns_final_context() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    rows = [
        (make_chunk(0, knowledge_base_id, workspace_id), 0.1),
        (make_chunk(1, knowledge_base_id, workspace_id), 0.2),
        (make_chunk(2, knowledge_base_id, workspace_id), 0.5),
    ]
    session = FakeSession(rows)
    provider = FakeEmbeddingProvider()

    retrieved_chunks = await retrieve_similar_chunks(
        session,  # type: ignore[arg-type]
        workspace_id=workspace_id,
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
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    rows = [
        (make_chunk(0, knowledge_base_id, workspace_id), 0.8),
        (make_chunk(1, knowledge_base_id, workspace_id), 0.4),
    ]
    session = FakeSession(rows)

    retrieved_chunks = await retrieve_keyword_chunks(
        session,  # type: ignore[arg-type]
        workspace_id=workspace_id,
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
            workspace_id=uuid.uuid4(),
            knowledge_base_id=uuid.uuid4(),
            query="policy",
            limit=0,
        )


@pytest.mark.asyncio
async def test_retrieve_hybrid_chunks_runs_vector_and_keyword_searches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    vector_chunk = make_chunk(0, knowledge_base_id, expected_workspace_id)
    keyword_chunk = make_chunk(1, knowledge_base_id, expected_workspace_id)
    calls: list[str] = []

    async def fake_retrieve_similar_chunks(
        session: object,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        query: str,
        provider: EmbeddingProvider,
        config: RetrievalConfig | None = None,
        metadata_filter: RetrievalMetadataFilter | None = None,
    ) -> list[RetrievedChunk]:
        calls.append("vector")
        assert workspace_id == expected_workspace_id
        assert query == "POLICY-2024-IT-07"
        assert config == RetrievalConfig(
            retrieval_top_k=4,
            final_context_k=4,
            hybrid_source_top_k=4,
            hybrid_candidate_top_k=2,
            rrf_k=60,
        )
        assert metadata_filter == RetrievalMetadataFilter(file_types=("md",))
        return [RetrievedChunk(chunk=vector_chunk, similarity_score=0.9)]

    async def fake_retrieve_keyword_chunks(
        session: object,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        query: str,
        limit: int,
        metadata_filter: RetrievalMetadataFilter | None = None,
    ) -> list[KeywordRetrievedChunk]:
        calls.append("keyword")
        assert workspace_id == expected_workspace_id
        assert query == "POLICY-2024-IT-07"
        assert limit == 4
        assert metadata_filter == RetrievalMetadataFilter(file_types=("md",))
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
        workspace_id=expected_workspace_id,
        knowledge_base_id=knowledge_base_id,
        query="POLICY-2024-IT-07",
        provider=FakeEmbeddingProvider(),
        config=RetrievalConfig(
            retrieval_top_k=4,
            final_context_k=2,
            hybrid_source_top_k=4,
            hybrid_candidate_top_k=2,
            rrf_k=60,
        ),
        metadata_filter=RetrievalMetadataFilter(file_types=("md",)),
    )

    assert calls == ["vector", "keyword"]
    assert [item.chunk.chunk_index for item in candidates] == [0, 1]
    assert candidates[0].vector_score == 0.9
    assert candidates[0].keyword_score is None
    assert candidates[0].rrf_score == pytest.approx(1 / 61)
    assert candidates[1].vector_score is None
    assert candidates[1].keyword_score == 0.7
    assert candidates[1].rrf_score == pytest.approx(1 / 61)


def compile_statement(statement: Any) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": False}))


def compile_params(statement: Any) -> dict[str, object]:
    return dict(statement.compile(compile_kwargs={"literal_binds": False}).params)
