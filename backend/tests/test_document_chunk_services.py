import uuid

import pytest
from sqlalchemy.sql.dml import Delete

from backend.app.models.document import Document, DocumentChunk, DocumentStatus
from backend.app.services.document_chunkers import TextChunk
from backend.app.services.document_chunks import replace_document_chunks


class FakeSession:
    def __init__(self) -> None:
        self.executed_statement: Delete | None = None
        self.added: list[DocumentChunk] = []
        self.committed = False

    async def execute(self, statement: Delete) -> None:
        self.executed_statement = statement

    def add_all(self, instances: list[DocumentChunk]) -> None:
        self.added = instances

    async def commit(self) -> None:
        self.committed = True


def make_document() -> Document:
    return Document(
        id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        filename="architecture.pdf",
        file_type="pdf",
        file_size=2048,
        file_hash="sha256:architecture",
        storage_path="knowledge-bases/engineering/architecture.pdf",
        status=DocumentStatus.UPLOADED.value,
        created_by=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_replace_document_chunks_deletes_existing_and_adds_new_chunks() -> None:
    document = make_document()
    session = FakeSession()
    chunks = [
        TextChunk(
            document_id=str(document.id),
            content="Architecture overview",
            chunk_index=0,
            page_number=1,
            section_title="Overview",
            token_count=2,
            metadata={"file_type": "pdf"},
        ),
        TextChunk(
            document_id=str(document.id),
            content="Deployment notes",
            chunk_index=1,
            page_number=2,
            section_title=None,
            token_count=2,
            metadata={},
        ),
    ]

    stored_chunks = await replace_document_chunks(session, document, chunks)  # type: ignore[arg-type]

    assert session.executed_statement is not None
    assert session.added == stored_chunks
    assert session.committed is True
    assert [chunk.chunk_index for chunk in stored_chunks] == [0, 1]
    assert all(chunk.document_id == document.id for chunk in stored_chunks)
    assert all(chunk.knowledge_base_id == document.knowledge_base_id for chunk in stored_chunks)
    assert stored_chunks[0].content == "Architecture overview"
    assert stored_chunks[0].page_number == 1
    assert stored_chunks[0].section_title == "Overview"
    assert stored_chunks[0].token_count == 2
    assert stored_chunks[0].chunk_metadata == {"file_type": "pdf"}
    assert stored_chunks[1].chunk_metadata == {}
