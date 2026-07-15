import uuid
from datetime import UTC, datetime

import pytest

from backend.app.models.document import Document, DocumentChunk
from backend.app.services.embeddings import EmbeddingProvider
from backend.app.services.query_rewriting import QueryMessageRole, QueryRewriteMessage
from backend.app.services.rerankers import RerankedChunk, Reranker
from backend.app.services.retrieval import (
    HybridRetrievedChunk,
    RetrievalConfig,
    RetrievalMetadataFilter,
)
from backend.app.services.retrieval_debug import (
    build_content_preview,
    debug_knowledge_base_retrieval,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return 3

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


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
                rerank_score=score,
                rrf_score=candidate.rrf_score,
                vector_score=candidate.vector_score,
                keyword_score=candidate.keyword_score,
            )
            for candidate, score in zip(reversed(candidates), [0.9, 0.5], strict=True)
        ]


def make_chunk(
    index: int,
    knowledge_base_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> DocumentChunk:
    effective_workspace_id = workspace_id or uuid.uuid4()
    now = datetime.now(UTC)
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        workspace_id=effective_workspace_id,
        filename=f"debug-{index}.md",
        file_type="md",
        file_size=128,
        file_hash=f"{index}" * 64,
        storage_path=f"storage/uploads/debug-{index}.md",
        status="completed",
        error_message=None,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        workspace_id=effective_workspace_id,
        knowledge_base_id=knowledge_base_id,
        content=f"debug context body {index}",
        chunk_index=index,
        page_number=index + 1,
        section_title="Debug" if index == 0 else None,
        token_count=4,
        embedding=[1.0, 0.0, 0.0],
        embedding_status="embedded",
        embedding_error=None,
        chunk_metadata={},
        created_at=now,
        updated_at=now,
    )
    chunk.document = document
    return chunk


def test_build_content_preview_compacts_and_truncates_content() -> None:
    content = "alpha   beta\n" + "x" * 300

    preview = build_content_preview(content, limit=20)

    assert preview == "alpha beta xxxxxx..."


@pytest.mark.asyncio
async def test_debug_knowledge_base_retrieval_returns_scores_and_final_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    chunks = [
        make_chunk(0, knowledge_base_id, expected_workspace_id),
        make_chunk(1, knowledge_base_id, expected_workspace_id),
    ]
    reranker = FakeReranker()

    async def fake_retrieve_hybrid_chunks(
        session: object,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        query: str,
        provider: EmbeddingProvider,
        config: RetrievalConfig | None = None,
        metadata_filter: RetrievalMetadataFilter | None = None,
    ) -> list[HybridRetrievedChunk]:
        assert workspace_id == expected_workspace_id
        assert query == "What is the travel policy about London?"
        assert config == RetrievalConfig(retrieval_top_k=10, final_context_k=2)
        assert metadata_filter == RetrievalMetadataFilter(file_types=("md",))
        return [
            HybridRetrievedChunk(
                chunk=chunks[0],
                rrf_score=0.03,
                vector_rank=1,
                keyword_rank=None,
                vector_score=0.8,
                keyword_score=None,
            ),
            HybridRetrievedChunk(
                chunk=chunks[1],
                rrf_score=0.04,
                vector_rank=2,
                keyword_rank=1,
                vector_score=0.7,
                keyword_score=0.9,
            ),
        ]

    monkeypatch.setattr(
        "backend.app.services.retrieval_debug.retrieve_hybrid_chunks",
        fake_retrieve_hybrid_chunks,
    )

    result = await debug_knowledge_base_retrieval(
        session=object(),  # type: ignore[arg-type]
        workspace_id=expected_workspace_id,
        knowledge_base_id=knowledge_base_id,
        question="What about London?",
        embedding_provider=FakeEmbeddingProvider(),
        reranker=reranker,
        retrieval_config=RetrievalConfig(retrieval_top_k=10, final_context_k=2),
        history=[
            QueryRewriteMessage(
                role=QueryMessageRole.USER,
                content="What is the travel policy?",
            )
        ],
        metadata_filter=RetrievalMetadataFilter(file_types=("md",)),
    )

    assert result.query_rewrite.rewritten_query == "What is the travel policy about London?"
    assert result.query_rewrite.was_rewritten is True
    assert reranker.query == "What is the travel policy about London?"
    assert reranker.limit == 2
    assert [candidate.chunk_id for candidate in result.candidates] == [chunks[1].id, chunks[0].id]
    assert [candidate.final_rank for candidate in result.candidates] == [1, 2]
    assert result.candidates[0].document_name == "debug-1.md"
    assert result.candidates[0].vector_rank == 2
    assert result.candidates[0].keyword_rank == 1
    assert result.candidates[0].vector_score == 0.7
    assert result.candidates[0].keyword_score == 0.9
    assert result.candidates[0].rrf_score == 0.04
    assert result.candidates[0].rerank_score == 0.9
