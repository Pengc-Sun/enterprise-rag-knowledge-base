import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from backend.app.models.document import Document, DocumentStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.services import documents as document_services
from backend.app.services.document_chunkers import TextChunk
from backend.app.services.document_parsers import DocumentParsingError, ParsedDocument, ParsedPage
from backend.app.services.documents import (
    DuplicateDocumentError,
    FileTooLargeError,
    UnsupportedFileExtensionError,
    UnsupportedMimeTypeError,
    create_document_from_upload,
    reprocess_document,
    sanitize_filename,
)


class FakeScalarResult:
    def __init__(self, document: Document | None) -> None:
        self.document = document

    def scalar_one_or_none(self) -> Document | None:
        return self.document


class FakeSession:
    def __init__(self, duplicate_document: Document | None = None) -> None:
        self.added: Document | None = None
        self.duplicate_document = duplicate_document
        self.committed = False
        self.commit_count = 0
        self.refreshed = False

    async def execute(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult(self.duplicate_document)

    def add(self, instance: object) -> None:
        self.added = instance  # type: ignore[assignment]

    async def commit(self) -> None:
        self.committed = True
        self.commit_count += 1

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
        workspace_id=uuid.uuid4(),
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
    assert document.workspace_id == knowledge_base.workspace_id
    assert Path(document.storage_path).read_bytes() == b"pdf-content"


@pytest.mark.asyncio
async def test_create_document_from_upload_rejects_duplicate_file_hash(tmp_path: Path) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    duplicate_document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base.id,
        workspace_id=knowledge_base.workspace_id,
        filename="existing.txt",
        file_type="txt",
        file_size=len(b"same content"),
        file_hash="a636bd7cd42060a4d07fa1bfbcc010eb7794c2ba721e1e3e4c20335a15b66eaf",
        storage_path="storage/uploads/existing.txt",
        status=DocumentStatus.UPLOADED.value,
        created_by=user.id,
    )
    session = FakeSession(duplicate_document=duplicate_document)
    upload_file = make_upload("new.txt", "text/plain", b"same content")

    with pytest.raises(DuplicateDocumentError):
        await create_document_from_upload(
            session,  # type: ignore[arg-type]
            knowledge_base,
            user,
            upload_file,
            tmp_path.as_posix(),
            1024,
        )

    assert session.added is None
    assert session.committed is False
    assert list(tmp_path.rglob("*")) == []


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


@pytest.mark.asyncio
async def test_reprocess_document_marks_completed_and_replaces_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base.id,
        workspace_id=knowledge_base.workspace_id,
        filename="notes.txt",
        file_type="txt",
        file_size=11,
        file_hash="hash",
        storage_path="storage/uploads/notes.txt",
        status=DocumentStatus.UPLOADED.value,
        created_by=user.id,
    )
    session = FakeSession()
    parsed_document = ParsedDocument(
        document_id=str(document.id),
        file_type="txt",
        pages=[ParsedPage(page_number=1, text="hello world")],
        headings=[],
    )
    text_chunks = [
        TextChunk(
            document_id=str(document.id),
            content="hello world",
            chunk_index=0,
            page_number=1,
            section_title=None,
            token_count=2,
        )
    ]
    replaced = False

    def fake_parse_document(document_to_parse: Document) -> ParsedDocument:
        assert document_to_parse is document
        return parsed_document

    def fake_chunk_document(parsed: ParsedDocument, config: object = None) -> list[TextChunk]:
        assert parsed is parsed_document
        return text_chunks

    async def fake_replace_document_chunks(
        session_arg: object,
        document_arg: Document,
        chunks_arg: list[TextChunk],
    ) -> list[object]:
        nonlocal replaced
        assert session_arg is session
        assert document_arg is document
        assert chunks_arg == text_chunks
        replaced = True
        return []

    monkeypatch.setattr(document_services, "parse_document", fake_parse_document)
    monkeypatch.setattr(document_services, "chunk_document", fake_chunk_document)
    monkeypatch.setattr(document_services, "replace_document_chunks", fake_replace_document_chunks)

    processed_document = await reprocess_document(session, document)  # type: ignore[arg-type]

    assert processed_document is document
    assert document.status == DocumentStatus.COMPLETED.value
    assert document.error_message is None
    assert replaced is True
    assert session.commit_count == 3


@pytest.mark.asyncio
async def test_reprocess_document_marks_failed_on_parser_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base.id,
        workspace_id=knowledge_base.workspace_id,
        filename="bad.txt",
        file_type="txt",
        file_size=3,
        file_hash="hash",
        storage_path="storage/uploads/bad.txt",
        status=DocumentStatus.UPLOADED.value,
        created_by=user.id,
    )
    session = FakeSession()

    def fake_parse_document(document_to_parse: Document) -> ParsedDocument:
        raise DocumentParsingError

    monkeypatch.setattr(document_services, "parse_document", fake_parse_document)

    with pytest.raises(DocumentParsingError):
        await reprocess_document(session, document)  # type: ignore[arg-type]

    assert document.status == DocumentStatus.FAILED.value
    assert document.error_message == DocumentParsingError.message
    assert session.commit_count == 2
