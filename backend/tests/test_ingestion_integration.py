import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy.sql.dml import Delete
from starlette.datastructures import Headers

from backend.app.models.document import Document, DocumentChunk, DocumentStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.services.document_embeddings import embed_document_chunks
from backend.app.services.documents import create_document_from_upload, reprocess_document
from backend.app.services.embeddings import DeterministicEmbeddingProvider, EmbeddingProvider
from backend.app.services.llms import LLMMessage, LLMProvider, LLMProviderName, LLMResponse
from backend.app.services.rag import answer_knowledge_base_question
from backend.app.services.rerankers import DeterministicCrossEncoderReranker
from backend.app.services.retrieval import RetrievalConfig, retrieve_hybrid_chunks


class FakeScalarOneResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class FakeScalarListResult:
    def __init__(self, values: list[DocumentChunk]) -> None:
        self.values = values

    def all(self) -> list[DocumentChunk]:
        return self.values


class FakeScalarsResult:
    def __init__(self, values: list[DocumentChunk]) -> None:
        self.values = values

    def scalars(self) -> FakeScalarListResult:
        return FakeScalarListResult(self.values)


class FakeRowsResult:
    def __init__(self, rows: list[tuple[DocumentChunk, float]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[DocumentChunk, float]]:
        return self.rows


class InMemoryIngestionSession:
    def __init__(self) -> None:
        self.documents: list[Document] = []
        self.chunks: list[DocumentChunk] = []
        self.commit_count = 0

    async def execute(self, statement: object) -> object:
        if isinstance(statement, Delete):
            self.chunks.clear()
            return FakeRowsResult([])

        sql = str(statement)
        if "documents.file_hash" in sql:
            return FakeScalarOneResult(None)
        if "document_chunks.document_id" in sql and "ORDER BY document_chunks.chunk_index" in sql:
            return FakeScalarsResult(sorted(self.chunks, key=lambda chunk: chunk.chunk_index))
        if "websearch_to_tsquery" in sql:
            rows = [
                (chunk, keyword_score(chunk)) for chunk in self.chunks if keyword_score(chunk) > 0
            ]
            return FakeRowsResult(sorted(rows, key=lambda row: (-row[1], row[0].chunk_index)))
        if "embedding" in sql and "distance" in sql:
            rows = [
                (chunk, vector_distance(chunk))
                for chunk in self.chunks
                if chunk.embedding is not None
            ]
            return FakeRowsResult(sorted(rows, key=lambda row: (row[1], row[0].chunk_index)))

        return FakeRowsResult([])

    def add(self, instance: object) -> None:
        if isinstance(instance, Document):
            self.documents.append(instance)

    def add_all(self, instances: Iterable[object]) -> None:
        for instance in instances:
            if isinstance(instance, DocumentChunk):
                document = next(
                    document for document in self.documents if document.id == instance.document_id
                )
                instance.document = document
                self.chunks.append(instance)

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, instance: object) -> None:
        return None


def keyword_score(chunk: DocumentChunk) -> float:
    content = chunk.content.lower()
    score = 0.0
    for term in ("meal", "allowance", "policy"):
        if term in content:
            score += 1.0
    return score


def vector_distance(chunk: DocumentChunk) -> float:
    # Deterministic local embeddings are enough for the pipeline; keyword retrieval gives the
    # relevant chunk a stronger candidate score in this integration test.
    return 0.1 + (chunk.chunk_index * 0.01)


class CapturingLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.prompt = ""

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.prompt = messages[-1].content
        return LLMResponse(
            content="The meal allowance is GBP 40 per day.",
            model="integration-llm",
            provider=LLMProviderName.DETERMINISTIC,
        )


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="integration@example.com",
        username="integration_user",
        hashed_password="hashed",
        role=UserRole.USER.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_knowledge_base(owner_id: uuid.UUID) -> KnowledgeBase:
    now = datetime.now(UTC)
    return KnowledgeBase(
        id=uuid.uuid4(),
        name="Travel Handbook",
        description="Integration test handbook",
        owner_id=owner_id,
        visibility=KnowledgeBaseVisibility.PRIVATE.value,
        created_at=now,
        updated_at=now,
    )


def make_upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "text/plain"}),
    )


@pytest.mark.asyncio
async def test_document_ingestion_pipeline_uploads_chunks_embeds_retrieves_and_generates(
    tmp_path: Path,
) -> None:
    session = InMemoryIngestionSession()
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    provider: EmbeddingProvider = DeterministicEmbeddingProvider(dimension=8)
    llm_provider = CapturingLLMProvider()
    upload_file = make_upload(
        "travel_policy.txt",
        (
            b"Travel policy handbook.\n\n"
            b"The meal allowance is GBP 40 per day for approved business travel.\n\n"
            b"Receipts are required for reimbursement."
        ),
    )

    uploaded = await create_document_from_upload(
        session,  # type: ignore[arg-type]
        knowledge_base,
        user,
        upload_file,
        tmp_path.as_posix(),
        1024 * 1024,
    )
    processed = await reprocess_document(session, uploaded)  # type: ignore[arg-type]
    embedding_result = await embed_document_chunks(
        session,  # type: ignore[arg-type]
        processed,
        provider,
        batch_size=2,
        max_retries=2,
    )
    candidates = await retrieve_hybrid_chunks(
        session=session,  # type: ignore[arg-type]
        knowledge_base_id=knowledge_base.id,
        query="What is the meal allowance?",
        provider=provider,
        config=RetrievalConfig(
            retrieval_top_k=3,
            final_context_k=1,
            hybrid_source_top_k=3,
            hybrid_candidate_top_k=2,
            rrf_k=60,
        ),
    )
    answer = await answer_knowledge_base_question(
        session=session,  # type: ignore[arg-type]
        knowledge_base_id=knowledge_base.id,
        question="What is the meal allowance?",
        embedding_provider=provider,
        llm_provider=llm_provider,
        reranker=DeterministicCrossEncoderReranker(model="integration-reranker"),
        retrieval_config=RetrievalConfig(
            retrieval_top_k=3,
            final_context_k=1,
            hybrid_source_top_k=3,
            hybrid_candidate_top_k=2,
            rrf_k=60,
        ),
    )

    assert uploaded in session.documents
    assert Path(uploaded.storage_path).read_text(encoding="utf-8").startswith("Travel policy")
    assert processed.status == DocumentStatus.COMPLETED.value
    assert len(session.chunks) == 1
    assert embedding_result.embedded_count == 1
    assert embedding_result.failed_count == 0
    assert all(chunk.embedding is not None for chunk in session.chunks)
    assert candidates
    assert candidates[0].chunk.content.startswith("Travel policy handbook")
    assert answer.answer == "The meal allowance is GBP 40 per day."
    assert answer.sources[0].document_name == "travel_policy.txt"
    assert "GBP 40 per day" in llm_provider.prompt
