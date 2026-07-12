import uuid

from backend.app.models.document import Document, DocumentStatus
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
