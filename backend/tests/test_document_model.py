import uuid

from backend.app.models.document import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User


def test_document_status_values() -> None:
    assert DocumentStatus.UPLOADED.value == "uploaded"
    assert DocumentStatus.PARSING.value == "parsing"
    assert DocumentStatus.CHUNKING.value == "chunking"
    assert DocumentStatus.EMBEDDING.value == "embedding"
    assert DocumentStatus.COMPLETED.value == "completed"
    assert DocumentStatus.FAILED.value == "failed"


def test_document_relationships() -> None:
    user = User(
        id=uuid.uuid4(),
        email="uploader@example.com",
        username="uploader",
        hashed_password="hashed",
    )
    knowledge_base = KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        owner=user,
    )
    document = Document(
        knowledge_base=knowledge_base,
        filename="architecture.pdf",
        file_type="pdf",
        file_size=2048,
        file_hash="sha256:architecture",
        storage_path="knowledge-bases/engineering/architecture.pdf",
        status=DocumentStatus.UPLOADED.value,
        creator=user,
    )

    assert document.knowledge_base is knowledge_base
    assert document.creator is user
    assert document in knowledge_base.documents
    assert document in user.documents
    assert document.status == "uploaded"


def test_document_chunk_relationship() -> None:
    user = User(
        id=uuid.uuid4(),
        email="chunker@example.com",
        username="chunker",
        hashed_password="hashed",
    )
    knowledge_base = KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        owner=user,
    )
    document = Document(
        id=uuid.uuid4(),
        knowledge_base=knowledge_base,
        filename="architecture.pdf",
        file_type="pdf",
        file_size=2048,
        file_hash="sha256:architecture",
        storage_path="knowledge-bases/engineering/architecture.pdf",
        status=DocumentStatus.UPLOADED.value,
        creator=user,
    )
    chunk = DocumentChunk(
        document=document,
        knowledge_base_id=knowledge_base.id,
        workspace_id=knowledge_base.workspace_id,
        content="Architecture overview",
        chunk_index=0,
        page_number=1,
        section_title="Overview",
        token_count=2,
        chunk_metadata={"file_type": "pdf"},
    )

    assert chunk.document is document
    assert chunk in document.chunks
    assert chunk.knowledge_base_id == knowledge_base.id
    assert chunk.chunk_metadata == {"file_type": "pdf"}


def test_document_chunk_accepts_embedding_vector() -> None:
    chunk = DocumentChunk(
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        content="Architecture overview",
        chunk_index=0,
        page_number=1,
        section_title="Overview",
        token_count=2,
        embedding=[0.1, 0.2, 0.3],
        chunk_metadata={},
    )

    assert chunk.embedding == [0.1, 0.2, 0.3]


def test_document_chunk_embedding_status_defaults() -> None:
    chunk = DocumentChunk(
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        content="Architecture overview",
        chunk_index=0,
        page_number=1,
        token_count=2,
        chunk_metadata={},
    )

    assert ChunkEmbeddingStatus.PENDING.value == "pending"
    assert chunk.embedding is None
    assert chunk.embedding_error is None


def test_document_and_chunk_accept_nullable_workspace_id() -> None:
    workspace_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        workspace_id=workspace_id,
        filename="architecture.pdf",
        file_type="pdf",
        file_size=2048,
        file_hash="sha256:architecture",
        storage_path="knowledge-bases/engineering/architecture.pdf",
        status=DocumentStatus.UPLOADED.value,
        created_by=uuid.uuid4(),
    )
    chunk = DocumentChunk(
        document_id=document.id,
        knowledge_base_id=knowledge_base_id,
        workspace_id=workspace_id,
        content="Architecture overview",
        chunk_index=0,
        page_number=1,
        token_count=2,
        chunk_metadata={},
    )

    assert document.workspace_id == workspace_id
    assert chunk.workspace_id == workspace_id
