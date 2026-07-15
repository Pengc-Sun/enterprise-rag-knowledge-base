import uuid
from datetime import UTC, datetime

import pytest

from backend.app.core.config import Settings
from backend.app.models.document import DocumentChunk
from backend.app.services.rerankers import (
    DeterministicCrossEncoderReranker,
    RerankerConfigurationError,
    RerankerProviderName,
    UnsupportedRerankerProviderError,
    build_reranker,
    create_reranker,
    tokenize,
)
from backend.app.services.retrieval import HybridRetrievedChunk


def make_chunk(index: int, content: str, section_title: str | None = None) -> DocumentChunk:
    now = datetime.now(UTC)
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        content=content,
        chunk_index=index,
        page_number=1,
        section_title=section_title,
        token_count=3,
        embedding=[1.0, 0.0, 0.0],
        embedding_status="embedded",
        chunk_metadata={},
        created_at=now,
        updated_at=now,
    )


def test_tokenize_normalizes_words_codes_and_models() -> None:
    assert tokenize("POLICY-2024 A100_X9 auth") == {"policy", "2024", "a100_x9", "auth"}


def test_build_reranker_rejects_unknown_provider() -> None:
    with pytest.raises(UnsupportedRerankerProviderError):
        build_reranker(provider="unknown", model="test-model")


def test_build_reranker_rejects_empty_model() -> None:
    with pytest.raises(RerankerConfigurationError):
        build_reranker(provider=RerankerProviderName.DETERMINISTIC.value, model="")


def test_create_reranker_uses_settings() -> None:
    settings = Settings(reranker_provider="deterministic", reranker_model="local-reranker")

    reranker = create_reranker(settings)

    assert isinstance(reranker, DeterministicCrossEncoderReranker)
    assert reranker.model == "local-reranker"


@pytest.mark.asyncio
async def test_deterministic_reranker_orders_by_query_chunk_overlap() -> None:
    reranker = DeterministicCrossEncoderReranker(model="deterministic-cross-encoder")
    weak_match = HybridRetrievedChunk(
        chunk=make_chunk(0, "general travel policy"),
        rrf_score=0.03,
        vector_score=0.6,
    )
    strong_match = HybridRetrievedChunk(
        chunk=make_chunk(1, "POLICY 2024 IT 07 travel allowance", "Policy Number"),
        rrf_score=0.02,
        keyword_score=0.8,
    )

    reranked = await reranker.rerank(
        query="POLICY 2024 travel allowance",
        candidates=[weak_match, strong_match],
        limit=2,
    )

    assert [item.chunk.chunk_index for item in reranked] == [1, 0]
    assert reranked[0].rerank_score > reranked[1].rerank_score
    assert reranked[0].keyword_score == 0.8
    assert reranked[1].vector_score == 0.6


@pytest.mark.asyncio
async def test_deterministic_reranker_applies_limit() -> None:
    reranker = DeterministicCrossEncoderReranker(model="deterministic-cross-encoder")
    candidates = [
        HybridRetrievedChunk(chunk=make_chunk(0, "alpha"), rrf_score=0.03),
        HybridRetrievedChunk(chunk=make_chunk(1, "alpha beta"), rrf_score=0.02),
    ]

    reranked = await reranker.rerank(query="alpha", candidates=candidates, limit=1)

    assert len(reranked) == 1


@pytest.mark.asyncio
async def test_deterministic_reranker_rejects_invalid_limit() -> None:
    reranker = DeterministicCrossEncoderReranker(model="deterministic-cross-encoder")

    with pytest.raises(RerankerConfigurationError):
        await reranker.rerank(query="alpha", candidates=[], limit=0)


@pytest.mark.asyncio
async def test_deterministic_reranker_tiebreaks_by_rrf_then_chunk_index() -> None:
    reranker = DeterministicCrossEncoderReranker(model="deterministic-cross-encoder")
    candidates = [
        HybridRetrievedChunk(chunk=make_chunk(3, "alpha"), rrf_score=0.01),
        HybridRetrievedChunk(chunk=make_chunk(2, "alpha"), rrf_score=0.02),
        HybridRetrievedChunk(chunk=make_chunk(1, "alpha"), rrf_score=0.02),
    ]

    reranked = await reranker.rerank(query="alpha", candidates=candidates, limit=3)

    assert [item.chunk.chunk_index for item in reranked] == [1, 2, 3]
