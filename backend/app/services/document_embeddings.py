import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from backend.app.services.embeddings import EmbeddingProvider, EmbeddingProviderError


@dataclass(frozen=True)
class BatchEmbeddingResult:
    document_id: str
    embedded_count: int
    failed_count: int


class EmbeddingDimensionMismatchError(EmbeddingProviderError):
    message = "Embedding dimension does not match configured vector dimension"


async def embed_document_chunks(
    session: AsyncSession,
    document: Document,
    provider: EmbeddingProvider,
    batch_size: int,
    max_retries: int,
) -> BatchEmbeddingResult:
    validate_batch_settings(batch_size, max_retries)
    chunks = await list_chunks_for_embedding(session, document)
    if not chunks:
        return BatchEmbeddingResult(document_id=str(document.id), embedded_count=0, failed_count=0)

    document.status = DocumentStatus.EMBEDDING.value
    document.error_message = None
    await session.commit()

    embedded_count = 0
    failed_count = 0
    for batch in iter_batches(chunks, batch_size):
        mark_batch_embedding(batch)
        await session.commit()

        try:
            embeddings = await embed_with_retries(
                provider,
                [chunk.content for chunk in batch],
                max_retries,
            )
            validate_embeddings(embeddings, len(batch), provider.dimension)
        except EmbeddingProviderError as exc:
            mark_batch_failed(batch, exc.message)
            failed_count += len(batch)
            await session.commit()
            continue

        for chunk, embedding in zip(batch, embeddings, strict=True):
            chunk.embedding = embedding
            chunk.embedding_status = ChunkEmbeddingStatus.EMBEDDED.value
            chunk.embedding_error = None
        embedded_count += len(batch)
        await session.commit()

    if failed_count:
        document.status = DocumentStatus.FAILED.value
        document.error_message = "One or more chunks failed to embed"
    else:
        document.status = DocumentStatus.COMPLETED.value
        document.error_message = None
    await session.commit()
    await session.refresh(document)

    return BatchEmbeddingResult(
        document_id=str(document.id),
        embedded_count=embedded_count,
        failed_count=failed_count,
    )


async def list_chunks_for_embedding(
    session: AsyncSession,
    document: Document,
) -> list[DocumentChunk]:
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())


def iter_batches(chunks: list[DocumentChunk], batch_size: int) -> list[list[DocumentChunk]]:
    return [chunks[index : index + batch_size] for index in range(0, len(chunks), batch_size)]


def mark_batch_embedding(chunks: list[DocumentChunk]) -> None:
    for chunk in chunks:
        chunk.embedding_status = ChunkEmbeddingStatus.EMBEDDING.value
        chunk.embedding_error = None


def mark_batch_failed(chunks: list[DocumentChunk], error_message: str) -> None:
    for chunk in chunks:
        chunk.embedding_status = ChunkEmbeddingStatus.FAILED.value
        chunk.embedding_error = error_message


async def embed_with_retries(
    provider: EmbeddingProvider,
    texts: list[str],
    max_retries: int,
) -> list[list[float]]:
    attempt = 0
    while True:
        try:
            return await provider.embed_documents(texts)
        except EmbeddingProviderError:
            attempt += 1
            if attempt >= max_retries:
                raise
            await asyncio.sleep(0)


def validate_embeddings(
    embeddings: list[list[float]],
    expected_count: int,
    expected_dimension: int,
) -> None:
    if len(embeddings) != expected_count:
        raise EmbeddingDimensionMismatchError
    if any(len(embedding) != expected_dimension for embedding in embeddings):
        raise EmbeddingDimensionMismatchError


def validate_batch_settings(batch_size: int, max_retries: int) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if max_retries <= 0:
        raise ValueError("max_retries must be positive")
