from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document, DocumentChunk
from backend.app.services.document_chunkers import TextChunk


async def replace_document_chunks(
    session: AsyncSession,
    document: Document,
    chunks: list[TextChunk],
) -> list[DocumentChunk]:
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

    document_chunks = [
        DocumentChunk(
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            workspace_id=document.workspace_id,
            content=chunk.content,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            token_count=chunk.token_count,
            chunk_metadata={**chunk.metadata},
        )
        for chunk in chunks
    ]
    session.add_all(document_chunks)
    await session.commit()
    return document_chunks
