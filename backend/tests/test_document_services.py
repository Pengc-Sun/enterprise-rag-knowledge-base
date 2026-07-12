import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.services.documents import (
    FileTooLargeError,
    UnsupportedFileExtensionError,
    UnsupportedMimeTypeError,
    create_document_from_upload,
    sanitize_filename,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: Document | None = None
        self.committed = False
        self.refreshed = False

    def add(self, instance: object) -> None:
        self.added = instance  # type: ignore[assignment]

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        self.refreshed = instance is self.added


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="uploader@example.com",
        username="uploader",
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


def make_upload(filename: str, content_type: str, content: bytes) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_sanitize_filename_removes_path_and_unsafe_characters() -> None:
    assert sanitize_filename("../Quarter Plan (Final).PDF") == "Quarter_Plan_Final.pdf"


@pytest.mark.asyncio
async def test_create_document_from_upload_saves_file_and_document(tmp_path: Path) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    session = FakeSession()
    upload_file = make_upload("../Architecture Guide.PDF", "application/pdf", b"pdf-content")

    document = await create_document_from_upload(
        session,  # type: ignore[arg-type]
        knowledge_base,
        user,
        upload_file,
        tmp_path.as_posix(),
        1024,
    )

    assert session.added is document
    assert session.committed is True
    assert session.refreshed is True
    assert document.filename == "Architecture_Guide.pdf"
    assert document.file_type == "pdf"
    assert document.file_size == len(b"pdf-content")
    assert document.status == "uploaded"
    assert document.created_by == user.id
    assert Path(document.storage_path).read_bytes() == b"pdf-content"


@pytest.mark.asyncio
async def test_create_document_from_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    upload_file = make_upload("script.exe", "application/octet-stream", b"bad")

    with pytest.raises(UnsupportedFileExtensionError):
        await create_document_from_upload(
            FakeSession(),  # type: ignore[arg-type]
            knowledge_base,
            user,
            upload_file,
            tmp_path.as_posix(),
            1024,
        )


@pytest.mark.asyncio
async def test_create_document_from_upload_rejects_mime_type_mismatch(tmp_path: Path) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    upload_file = make_upload("report.pdf", "text/plain", b"not-a-pdf")

    with pytest.raises(UnsupportedMimeTypeError):
        await create_document_from_upload(
            FakeSession(),  # type: ignore[arg-type]
            knowledge_base,
            user,
            upload_file,
            tmp_path.as_posix(),
            1024,
        )


@pytest.mark.asyncio
async def test_create_document_from_upload_rejects_oversized_file(tmp_path: Path) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    upload_file = make_upload("large.txt", "text/plain", b"too-large")

    with pytest.raises(FileTooLargeError):
        await create_document_from_upload(
            FakeSession(),  # type: ignore[arg-type]
            knowledge_base,
            user,
            upload_file,
            tmp_path.as_posix(),
            3,
        )

    assert list(tmp_path.rglob("*")) == []
