import uuid
from collections.abc import Callable
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
from backend.app.models.audit import AuditAction, AuditResourceType
from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import Workspace
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


def make_workspace(owner_id: uuid.UUID) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid.uuid4(),
        name="Policy Workspace",
        slug=f"policy-{str(owner_id).replace('-', '')}",
        owner_id=owner_id,
        status="active",
        created_at=now,
        updated_at=now,
    )


def make_knowledge_base(owner_id: uuid.UUID, workspace_id: uuid.UUID) -> KnowledgeBase:
    now = datetime.now(UTC)
    return KnowledgeBase(
        id=uuid.uuid4(),
        name="Engineering Handbook",
        description="Internal docs",
        owner_id=owner_id,
        workspace_id=workspace_id,
        visibility=KnowledgeBaseVisibility.PRIVATE.value,
        created_at=now,
        updated_at=now,
    )


def make_document(
    knowledge_base_id: uuid.UUID,
    workspace_id: uuid.UUID,
    created_by: uuid.UUID,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        workspace_id=workspace_id,
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


def patch_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    records: list[dict[str, object]],
) -> None:
    async def fake_create_audit_log(
        session: AsyncSession,
        *,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: AuditAction,
        resource_type: AuditResourceType,
        resource_id: uuid.UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        records.append(
            {
                "workspace_id": workspace_id,
                "actor_user_id": actor_user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "metadata": metadata or {},
            }
        )

    monkeypatch.setattr(document_endpoints, "create_audit_log", fake_create_audit_log)


def assert_read_roles(roles: frozenset[str]) -> None:
    assert "viewer" in roles


def assert_write_roles(roles: frozenset[str]) -> None:
    assert "admin" in roles
    assert "viewer" not in roles


def patch_workspace_access(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workspace: Workspace | None,
    expected_roles: Callable[[frozenset[str]], None] | None = None,
) -> None:
    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace | None:
        if workspace is not None:
            assert workspace_id == workspace.id
            assert user_id == workspace.owner_id
        if expected_roles is not None:
            expected_roles(allowed_roles)
        return workspace

    monkeypatch.setattr(document_endpoints, "get_workspace_for_user", fake_get_workspace_for_user)


def patch_knowledge_base(
    monkeypatch: pytest.MonkeyPatch,
    *,
    knowledge_base: KnowledgeBase | None,
) -> None:
    async def fake_get_knowledge_base_for_workspace(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> KnowledgeBase | None:
        if knowledge_base is not None:
            assert knowledge_base_id == knowledge_base.id
            assert workspace_id == knowledge_base.workspace_id
        return knowledge_base

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_workspace",
        fake_get_knowledge_base_for_workspace,
    )


def patch_document(
    monkeypatch: pytest.MonkeyPatch,
    *,
    document: Document | None,
) -> None:
    async def fake_get_document_for_workspace_knowledge_base(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document | None:
        if document is not None:
            assert workspace_id == document.workspace_id
            assert knowledge_base_id == document.knowledge_base_id
            assert document_id == document.id
        return document

    monkeypatch.setattr(
        document_endpoints,
        "get_document_for_workspace_knowledge_base",
        fake_get_document_for_workspace_knowledge_base,
    )


def patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        document_endpoints,
        "get_settings",
        lambda: SimpleNamespace(
            upload_dir="storage/uploads",
            max_upload_size_bytes=10 * 1024 * 1024,
            embedding_batch_size=32,
            embedding_max_retries=3,
        ),
    )


def test_upload_document_returns_created_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document = make_document(knowledge_base.id, workspace.id, user.id)
    audit_logs: list[dict[str, object]] = []

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)

    async def fake_create_document_from_upload(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
        current_user: User,
        upload_file: UploadFile,
        upload_dir: str,
        max_file_size_bytes: int,
    ) -> Document:
        assert current_user is user
        assert knowledge_base.workspace_id == workspace.id
        assert upload_file.filename == "architecture.pdf"
        assert upload_file.content_type == "application/pdf"
        assert upload_dir == "storage/uploads"
        assert max_file_size_bytes == 10 * 1024 * 1024
        return document

    async def fake_process_document_for_retrieval(
        session: AsyncSession,
        document_arg: Document,
        settings: SimpleNamespace,
    ) -> tuple[Document, int]:
        assert document_arg is document
        document.status = "completed"
        return document, 2

    monkeypatch.setattr(
        document_endpoints,
        "create_document_from_upload",
        fake_create_document_from_upload,
    )
    monkeypatch.setattr(
        document_endpoints,
        "process_document_for_retrieval",
        fake_process_document_for_retrieval,
    )
    patch_settings(monkeypatch)
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents?workspace_id={workspace.id}",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "document uploaded and processed"
    assert body["data"]["workspace_id"] == str(workspace.id)
    assert body["data"]["filename"] == "architecture.pdf"
    assert body["data"]["status"] == "completed"
    assert body["data"]["chunk_count"] == 2
    assert audit_logs[0]["action"] == AuditAction.DOCUMENT_UPLOADED
    assert audit_logs[0]["resource_id"] == document.id
    assert audit_logs[0]["metadata"] == {
        "knowledge_base_id": str(knowledge_base.id),
        "filename": "architecture.pdf",
        "status": "completed",
        "chunk_count": 2,
    }


def test_upload_workspace_document_route(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document = make_document(knowledge_base.id, workspace.id, user.id)
    audit_logs: list[dict[str, object]] = []

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)

    async def fake_create_document_from_upload(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
        current_user: User,
        upload_file: UploadFile,
        upload_dir: str,
        max_file_size_bytes: int,
    ) -> Document:
        return document

    async def fake_process_document_for_retrieval(
        session: AsyncSession,
        document_arg: Document,
        settings: SimpleNamespace,
    ) -> tuple[Document, int]:
        return document_arg, 1

    monkeypatch.setattr(
        document_endpoints,
        "create_document_from_upload",
        fake_create_document_from_upload,
    )
    monkeypatch.setattr(
        document_endpoints,
        "process_document_for_retrieval",
        fake_process_document_for_retrieval,
    )
    patch_settings(monkeypatch)
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/knowledge-bases/{knowledge_base.id}/documents",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    assert response.json()["data"]["workspace_id"] == str(workspace.id)
    assert audit_logs[0]["action"] == AuditAction.DOCUMENT_UPLOADED


def test_upload_document_without_workspace_id_returns_422() -> None:
    user = make_user()
    knowledge_base_id = uuid.uuid4()
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 422


def test_upload_document_requires_workspace_write_role(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base_id = uuid.uuid4()

    patch_workspace_access(monkeypatch, workspace=None)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents?workspace_id={workspace.id}",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found"


def test_upload_document_rejects_knowledge_base_from_another_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    other_workspace = make_workspace(user.id)
    other_knowledge_base = make_knowledge_base(user.id, other_workspace.id)

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)

    async def fake_get_knowledge_base_for_workspace(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> None:
        assert knowledge_base_id == other_knowledge_base.id
        assert workspace_id == workspace.id
        return None

    async def fake_create_document_from_upload(*args: object, **kwargs: object) -> Document:
        raise AssertionError("cross-workspace upload must stop before document creation")

    monkeypatch.setattr(
        document_endpoints,
        "get_knowledge_base_for_workspace",
        fake_get_knowledge_base_for_workspace,
    )
    monkeypatch.setattr(
        document_endpoints,
        "create_document_from_upload",
        fake_create_document_from_upload,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workspaces/{workspace.id}/knowledge-bases/"
            f"{other_knowledge_base.id}/documents",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Knowledge base not found"


def test_upload_document_rejects_duplicate_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)

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
        "create_document_from_upload",
        fake_create_document_from_upload,
    )
    patch_settings(monkeypatch)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents?workspace_id={workspace.id}",
            files={"file": ("architecture.pdf", b"content", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 409
    assert response.json()["message"] == "Document already exists"


def test_list_documents_returns_chunk_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document = make_document(knowledge_base.id, workspace.id, user.id)

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_read_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)

    async def fake_list_documents_for_workspace_knowledge_base(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> list[tuple[Document, int]]:
        assert workspace_id == workspace.id
        assert knowledge_base_id == knowledge_base.id
        return [(document, 3)]

    monkeypatch.setattr(
        document_endpoints,
        "list_documents_for_workspace_knowledge_base",
        fake_list_documents_for_workspace_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["workspace_id"] == str(workspace.id)
    assert body["data"][0]["filename"] == "architecture.pdf"
    assert body["data"][0]["chunk_count"] == 3


def test_read_document_returns_document_in_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document = make_document(knowledge_base.id, workspace.id, user.id)

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_read_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)
    patch_document(monkeypatch, document=document)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}"
            f"?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(document.id)


def test_reprocess_document_returns_processed_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document = make_document(knowledge_base.id, workspace.id, user.id)
    document.status = "completed"
    audit_logs: list[dict[str, object]] = []

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)
    patch_document(monkeypatch, document=document)

    async def fake_process_document_for_retrieval(
        session: AsyncSession,
        document_arg: Document,
        settings: SimpleNamespace,
    ) -> tuple[Document, int]:
        assert document_arg is document
        return document, 4

    monkeypatch.setattr(
        document_endpoints,
        "process_document_for_retrieval",
        fake_process_document_for_retrieval,
    )
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}/reprocess"
            f"?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "document reprocessed"
    assert body["data"]["id"] == str(document.id)
    assert body["data"]["status"] == "completed"
    assert body["data"]["chunk_count"] == 4
    assert audit_logs[0]["action"] == AuditAction.DOCUMENT_REPROCESSED
    assert audit_logs[0]["metadata"] == {
        "knowledge_base_id": str(knowledge_base.id),
        "filename": "architecture.pdf",
        "status": "completed",
        "chunk_count": 4,
    }


def test_reprocess_document_returns_404_for_cross_workspace_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document_id = uuid.uuid4()

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)
    patch_document(monkeypatch, document=None)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document_id}/reprocess"
            f"?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found"


def test_read_document_returns_404_for_cross_workspace_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    other_document = make_document(knowledge_base.id, uuid.uuid4(), user.id)

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_read_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)

    async def fake_get_document_for_workspace_knowledge_base(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        assert workspace_id == workspace.id
        assert knowledge_base_id == knowledge_base.id
        assert document_id == other_document.id
        return None

    monkeypatch.setattr(
        document_endpoints,
        "get_document_for_workspace_knowledge_base",
        fake_get_document_for_workspace_knowledge_base,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/workspaces/{workspace.id}/knowledge-bases/"
            f"{knowledge_base.id}/documents/{other_document.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found"


def test_delete_document_returns_no_content(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document = make_document(knowledge_base.id, workspace.id, user.id)
    deleted_document: Document | None = None
    audit_logs: list[dict[str, object]] = []

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)
    patch_document(monkeypatch, document=document)

    async def fake_delete_document(session: AsyncSession, document_arg: Document) -> None:
        nonlocal deleted_document
        deleted_document = document_arg

    monkeypatch.setattr(document_endpoints, "delete_document", fake_delete_document)
    patch_audit_log(monkeypatch, audit_logs)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}"
            f"?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 204
    assert response.content == b""
    assert deleted_document is document
    assert audit_logs[0]["action"] == AuditAction.DOCUMENT_DELETED
    assert audit_logs[0]["resource_id"] == document.id


def test_delete_document_returns_404_for_missing_document(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    workspace = make_workspace(user.id)
    knowledge_base = make_knowledge_base(user.id, workspace.id)
    document_id = uuid.uuid4()

    patch_workspace_access(monkeypatch, workspace=workspace, expected_roles=assert_write_roles)
    patch_knowledge_base(monkeypatch, knowledge_base=knowledge_base)
    patch_document(monkeypatch, document=None)
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.delete(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document_id}"
            f"?workspace_id={workspace.id}"
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found"
