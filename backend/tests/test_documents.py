import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import documents as document_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.services.documents import DuplicateDocumentError


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="enterprise_user",
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
        name="Engineering Handbook",
        description="Internal docs",
        owner_id=owner_id,
        visibility=KnowledgeBaseVisibility.PRIVATE.value,
        created_at=now,
        updated_at=now,
    )


def make_document(knowledge_base_id: uuid.UUID, created_by: uuid.UUID) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        filename="architecture.pdf",
        file_type="pdf",
        file_size=1024,
        file_hash="a" * 64,
        storage_path="storage/uploads/architecture.pdf",
        status="uploaded",
        error_message=None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def override_db_session() -> AsyncSession:
    return cast(AsyncSession, object())


def set_overrides(user: User) -> None:
    def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_db_session


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_upload_document_returns_created_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document = make_document(knowledge_base.id, user.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert user_id == user.id
        assert allowed_permissions == frozenset({"owner", "editor"})
        return knowledge_base

    async def fake_create_document_from_upload(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
        current_user: User,
        upload_file: UploadFile,
        upload_dir: str,
        max_file_size_bytes: int,
    ) -> Document:
        assert current_user is user
        assert upload_file.filename == "architecture.pdf"
        assert upload_file.content_type == "application/pdf"
        assert upload_dir == "storage/uploads"
        assert max_file_size_bytes == 10 * 1024 * 1024
        return document

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        document_endpoints,
        "create_document_from_upload",
        fake_create_document_from_upload,
    )
    monkeypatch.setattr(
        document_endpoints,
        "get_settings",
        lambda: SimpleNamespace(
            upload_dir="storage/uploads",
            max_upload_size_bytes=10 * 1024 * 1024,
        ),
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "document uploaded"
    assert body["data"]["filename"] == "architecture.pdf"
    assert body["data"]["status"] == "uploaded"


def test_upload_document_requires_write_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base_id = uuid.uuid4()

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> None:
        return None

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Knowledge base not found"


def test_upload_document_rejects_duplicate_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_create_document_from_upload(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
        current_user: User,
        upload_file: UploadFile,
        upload_dir: str,
        max_file_size_bytes: int,
    ) -> Document:
        raise DuplicateDocumentError

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        document_endpoints,
        "create_document_from_upload",
        fake_create_document_from_upload,
    )
    monkeypatch.setattr(
        document_endpoints,
        "get_settings",
        lambda: SimpleNamespace(
            upload_dir="storage/uploads",
            max_upload_size_bytes=10 * 1024 * 1024,
        ),
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 409
    assert response.json()["message"] == "Document already exists"


def test_reprocess_document_returns_processed_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document = make_document(knowledge_base.id, user.id)
    document.status = "completed"

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        assert allowed_permissions == frozenset({"owner", "editor"})
        return knowledge_base

    async def fake_get_document_for_knowledge_base(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document:
        assert knowledge_base_id == knowledge_base.id
        assert document_id == document.id
        return document

    async def fake_reprocess_document(session: AsyncSession, document_arg: Document) -> Document:
        assert document_arg is document
        return document

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        document_endpoints,
        "get_document_for_knowledge_base",
        fake_get_document_for_knowledge_base,
    )
    monkeypatch.setattr(document_endpoints, "reprocess_document", fake_reprocess_document)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}/reprocess"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "document reprocessed"
    assert body["data"]["id"] == str(document.id)
    assert body["data"]["status"] == "completed"


def test_reprocess_document_returns_404_for_missing_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document_id = uuid.uuid4()

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_get_document_for_knowledge_base(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        document_endpoints,
        "get_document_for_knowledge_base",
        fake_get_document_for_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document_id}/reprocess"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found"


def test_list_documents_returns_chunk_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document = make_document(knowledge_base.id, user.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert user_id == user.id
        assert allowed_permissions == frozenset({"owner", "editor", "viewer"})
        return knowledge_base

    async def fake_list_documents_for_knowledge_base(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
    ) -> list[tuple[Document, int]]:
        assert knowledge_base_id == knowledge_base.id
        return [(document, 3)]

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        document_endpoints,
        "list_documents_for_knowledge_base",
        fake_list_documents_for_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/knowledge-bases/{knowledge_base.id}/documents")
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["filename"] == "architecture.pdf"
    assert body["data"][0]["chunk_count"] == 3


def test_delete_document_returns_no_content(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document = make_document(knowledge_base.id, user.id)
    deleted_document: Document | None = None

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert user_id == user.id
        assert allowed_permissions == frozenset({"owner", "editor"})
        return knowledge_base

    async def fake_get_document_for_knowledge_base(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document:
        assert knowledge_base_id == knowledge_base.id
        assert document_id == document.id
        return document

    async def fake_delete_document(session: AsyncSession, document_arg: Document) -> None:
        nonlocal deleted_document
        deleted_document = document_arg

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        document_endpoints,
        "get_document_for_knowledge_base",
        fake_get_document_for_knowledge_base,
    )
    monkeypatch.setattr(document_endpoints, "delete_document", fake_delete_document)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 204
    assert response.content == b""
    assert deleted_document is document


def test_delete_document_returns_404_for_missing_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document_id = uuid.uuid4()

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_get_document_for_knowledge_base(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        return None

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        document_endpoints,
        "get_document_for_knowledge_base",
        fake_get_document_for_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document_id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found"
