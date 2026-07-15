import uuid

import pytest
from sqlalchemy.sql import Select

from backend.app.models.document import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from backend.app.services.document_embeddings import (
    EmbeddingDimensionMismatchError,
    embed_document_chunks,
    embed_with_retries,
    iter_batches,
    validate_batch_settings,
)
from backend.app.services.embeddings import EmbeddingProvider, EmbeddingProviderError


class FakeScalarResult:
    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks

    def all(self) -> list[DocumentChunk]:
        return self.chunks


class FakeResult:
    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.chunks)


class FakeSession:
    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks
        self.commit_count = 0
        self.refreshed = False

    async def execute(self, statement: Select[tuple[DocumentChunk]]) -> FakeResult:
        return FakeResult(self.chunks)

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, instance: object) -> None:
        self.refreshed = True


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        embeddings: list[list[float]] | None = None,
        failures_before_success: int = 0,
        dimension: int = 3,
    ) -> None:
        self.embeddings = embeddings
        self.failures_before_success = failures_before_success
        self.call_count = 0
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        if self.call_count <= self.failures_before_success:
            raise EmbeddingProviderError("temporary failure")
        if self.embeddings is not None:
            return self.embeddings[: len(texts)]
        return [[float(index), 0.0, 1.0] for index, _ in enumerate(texts)]


def make_document() -> Document:
    return Document(
        id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        filename="notes.txt",
        file_type="txt",
        file_size=10,
        file_hash="hash",
        storage_path="storage/uploads/notes.txt",
        status=DocumentStatus.COMPLETED.value,
        created_by=uuid.uuid4(),
    )


def make_chunks(document: Document, count: int) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            content=f"chunk {index}",
            chunk_index=index,
            page_number=1,
            token_count=2,
            chunk_metadata={},
        )
        for index in range(count)
    ]


def test_iter_batches_splits_chunks() -> None:
    document = make_document()
    chunks = make_chunks(document, 5)

    batches = iter_batches(chunks, batch_size=2)

    assert [len(batch) for batch in batches] == [2, 2, 1]


@pytest.mark.asyncio
async def test_embed_document_chunks_embeds_batches_and_marks_completed() -> None:
    document = make_document()
    chunks = make_chunks(document, 3)
    session = FakeSession(chunks)
    provider = FakeEmbeddingProvider()

    result = await embed_document_chunks(
        session,  # type: ignore[arg-type]
        document,
        provider,
        batch_size=2,
        max_retries=2,
    )

    assert result.document_id == str(document.id)
    assert result.embedded_count == 3
    assert result.failed_count == 0
    assert provider.call_count == 2
    assert document.status == DocumentStatus.COMPLETED.value
    assert document.error_message is None
    assert session.refreshed is True
    assert all(chunk.embedding_status == ChunkEmbeddingStatus.EMBEDDED.value for chunk in chunks)
    assert all(chunk.embedding_error is None for chunk in chunks)
    assert all(chunk.embedding is not None for chunk in chunks)


@pytest.mark.asyncio
async def test_embed_with_retries_retries_temporary_provider_failures() -> None:
    provider = FakeEmbeddingProvider(failures_before_success=1)

    embeddings = await embed_with_retries(provider, ["hello"], max_retries=2)

    assert provider.call_count == 2
    assert embeddings == [[0.0, 0.0, 1.0]]


@pytest.mark.asyncio
async def test_embed_document_chunks_records_batch_failure() -> None:
    document = make_document()
    chunks = make_chunks(document, 2)
    session = FakeSession(chunks)
    provider = FakeEmbeddingProvider(failures_before_success=3)

    result = await embed_document_chunks(
        session,  # type: ignore[arg-type]
        document,
        provider,
        batch_size=2,
        max_retries=2,
    )

    assert result.embedded_count == 0
    assert result.failed_count == 2
    assert document.status == DocumentStatus.FAILED.value
    assert document.error_message == "One or more chunks failed to embed"
    assert all(chunk.embedding_status == ChunkEmbeddingStatus.FAILED.value for chunk in chunks)
    assert all(chunk.embedding_error == EmbeddingProviderError.message for chunk in chunks)


@pytest.mark.asyncio
async def test_embed_document_chunks_records_dimension_mismatch() -> None:
    document = make_document()
    chunks = make_chunks(document, 1)
    session = FakeSession(chunks)
    provider = FakeEmbeddingProvider(embeddings=[[1.0, 2.0]], dimension=3)

    result = await embed_document_chunks(
        session,  # type: ignore[arg-type]
        document,
        provider,
        batch_size=1,
        max_retries=1,
    )

    assert result.failed_count == 1
    assert chunks[0].embedding_status == ChunkEmbeddingStatus.FAILED.value
    assert chunks[0].embedding_error == EmbeddingDimensionMismatchError.message


def test_validate_batch_settings_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        validate_batch_settings(batch_size=0, max_retries=1)

    with pytest.raises(ValueError):
        validate_batch_settings(batch_size=1, max_retries=0)
