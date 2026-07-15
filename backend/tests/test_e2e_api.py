import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import auth as auth_dependencies
from backend.app.api.v1.endpoints import auth as auth_endpoints
from backend.app.api.v1.endpoints import documents as document_endpoints
from backend.app.api.v1.endpoints import knowledge_bases as knowledge_base_endpoints
from backend.app.api.v1.endpoints import rag as rag_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.document import Document, DocumentChunk, DocumentStatus
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.models.workspace import Workspace
from backend.app.schemas.knowledge_base import KnowledgeBaseCreate
from backend.app.schemas.user import UserCreate
from backend.app.services.llms import LLMProviderName
from backend.app.services.query_rewriting import QueryRewriteResult
from backend.app.services.rag import RAGAnswer, RAGSourceCitation
from backend.app.services.rerankers import RerankedChunk


def override_db_session() -> AsyncSession:
    return cast(AsyncSession, object())


def make_user(email: str, username: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=email,
        username=username,
        hashed_password="hashed-password",
        role=UserRole.USER.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_document(
    knowledge_base_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        workspace_id=workspace_id,
        filename="travel_policy.txt",
        file_type="txt",
        file_size=95,
        file_hash="a" * 64,
        storage_path="storage/uploads/travel_policy.txt",
        status=DocumentStatus.UPLOADED.value,
        error_message=None,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


def make_chunk(document: Document) -> DocumentChunk:
    now = datetime.now(UTC)
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        knowledge_base_id=document.knowledge_base_id,
        workspace_id=document.workspace_id,
        content="The maximum meal allowance is GBP 40 per day.",
        chunk_index=0,
        page_number=1,
        section_title="Travel expenses",
        token_count=9,
        embedding=[1.0, 0.0, 0.0],
        embedding_status="embedded",
        embedding_error=None,
        chunk_metadata={},
        created_at=now,
        updated_at=now,
    )
    chunk.document = document
    return chunk


def make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        upload_dir="storage/uploads",
        max_upload_size_bytes=10 * 1024 * 1024,
        embedding_provider="deterministic",
        embedding_dimension=1536,
        embedding_model="deterministic-hash",
        embedding_api_key=None,
        embedding_base_url=None,
        retrieval_top_k=10,
        final_context_k=4,
        query_rewrite_enabled=True,
        query_rewrite_history_limit=6,
        hybrid_source_top_k=20,
        hybrid_candidate_top_k=10,
        rrf_k=60,
        reranker_provider="deterministic",
        reranker_model="deterministic-cross-encoder",
        llm_provider="deterministic",
        llm_model="deterministic-chat",
        llm_api_key=None,
        llm_base_url=None,
        llm_temperature=0.2,
        llm_max_tokens=1024,
        llm_timeout_seconds=30.0,
        llm_max_retries=3,
    )


def test_register_login_create_upload_query_and_read_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {}

    async def fake_create_user(session: AsyncSession, user_create: UserCreate) -> User:
        user = make_user(str(user_create.email), user_create.username)
        state["user"] = user
        return user

    async def fake_authenticate_user(
        session: AsyncSession, email: str, password: str
    ) -> User | None:
        user = cast(User, state["user"])
        assert email == user.email
        assert password == "secure-password"
        return user

    async def fake_get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
        user = cast(User, state["user"])
        return user if user.id == user_id else None

    async def fake_get_workspace_for_user(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: frozenset[str],
    ) -> Workspace:
        user = cast(User, state["user"])
        workspace = cast(Workspace, state["workspace"])
        assert workspace_id == workspace.id
        assert user_id == user.id
        assert "admin" in allowed_roles
        return workspace

    async def fake_create_knowledge_base(
        session: AsyncSession,
        owner_id: uuid.UUID,
        workspace_id: uuid.UUID,
        knowledge_base_create: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        user = cast(User, state["user"])
        workspace = cast(Workspace, state["workspace"])
        assert owner_id == user.id
        assert workspace_id == workspace.id
        now = datetime.now(UTC)
        knowledge_base = KnowledgeBase(
            id=uuid.uuid4(),
            name=knowledge_base_create.name,
            description=knowledge_base_create.description,
            owner_id=owner_id,
            workspace_id=workspace_id,
            visibility=KnowledgeBaseVisibility.PRIVATE.value,
            created_at=now,
            updated_at=now,
        )
        state["knowledge_base"] = knowledge_base
        return knowledge_base

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase | None:
        user = cast(User, state["user"])
        knowledge_base = cast(KnowledgeBase, state["knowledge_base"])
        assert user_id == user.id
        assert knowledge_base_id == knowledge_base.id
        return knowledge_base

    async def fake_get_knowledge_base_for_workspace(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> KnowledgeBase | None:
        knowledge_base = cast(KnowledgeBase, state["knowledge_base"])
        assert knowledge_base_id == knowledge_base.id
        assert workspace_id == knowledge_base.workspace_id
        return knowledge_base

    async def fake_create_document_from_upload(
        session: AsyncSession,
        knowledge_base: KnowledgeBase,
        current_user: User,
        upload_file: UploadFile,
        upload_dir: str,
        max_file_size_bytes: int,
    ) -> Document:
        assert upload_file.filename == "travel_policy.txt"
        assert upload_file.content_type == "text/plain"
        assert upload_dir == "storage/uploads"
        assert max_file_size_bytes == 10 * 1024 * 1024
        document = make_document(knowledge_base.id, knowledge_base.workspace_id, current_user.id)
        state["document"] = document
        return document

    async def fake_process_document_for_retrieval(
        session: AsyncSession,
        document: Document,
        settings: SimpleNamespace,
    ) -> tuple[Document, int]:
        document.status = DocumentStatus.COMPLETED.value
        state["chunk"] = make_chunk(document)
        return document, 1

    async def fake_answer_knowledge_base_question(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        question: str,
        embedding_provider: object,
        llm_provider: object,
        reranker: object,
        retrieval_config: object,
        query_rewrite_config: object,
        history: object,
        metadata_filter: object,
        user_id: uuid.UUID | None = None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> RAGAnswer:
        knowledge_base = cast(KnowledgeBase, state["knowledge_base"])
        chunk = cast(DocumentChunk, state["chunk"])
        assert knowledge_base_id == knowledge_base.id
        assert question == "What is the maximum meal allowance?"
        assert temperature == 0.2
        assert max_tokens == 1024
        return RAGAnswer(
            answer="The maximum meal allowance is GBP 40 per day.",
            model="deterministic-chat",
            provider=LLMProviderName.DETERMINISTIC,
            context_chunks=[RerankedChunk(chunk=chunk, rerank_score=0.95, rrf_score=0.1)],
            sources=[
                RAGSourceCitation(
                    document_name="travel_policy.txt",
                    page_number=1,
                    chunk_id=chunk.id,
                    original_text=chunk.content,
                    similarity_score=0.95,
                )
            ],
            query_rewrite=QueryRewriteResult(
                original_query=question,
                rewritten_query=question,
                was_rewritten=False,
            ),
        )

    monkeypatch.setattr(auth_endpoints, "create_user", fake_create_user)
    monkeypatch.setattr(auth_endpoints, "authenticate_user", fake_authenticate_user)
    monkeypatch.setattr(auth_dependencies, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(
        knowledge_base_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
    monkeypatch.setattr(
        knowledge_base_endpoints,
        "create_knowledge_base",
        fake_create_knowledge_base,
    )
    monkeypatch.setattr(
        document_endpoints,
        "get_workspace_for_user",
        fake_get_workspace_for_user,
    )
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
    monkeypatch.setattr(
        document_endpoints,
        "process_document_for_retrieval",
        fake_process_document_for_retrieval,
    )
    monkeypatch.setattr(document_endpoints, "get_settings", make_settings)
    monkeypatch.setattr(
        rag_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    monkeypatch.setattr(
        rag_endpoints,
        "answer_knowledge_base_question",
        fake_answer_knowledge_base_question,
    )
    monkeypatch.setattr(rag_endpoints, "get_settings", make_settings)
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        client = TestClient(app)
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "qa@example.com",
                "username": "qa_user",
                "password": "secure-password",
            },
        )
        assert register_response.status_code == 201
        assert register_response.json()["data"]["email"] == "qa@example.com"

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "qa@example.com", "password": "secure-password"},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        user = cast(User, state["user"])
        now = datetime.now(UTC)
        state["workspace"] = Workspace(
            id=uuid.uuid4(),
            name="Default Workspace",
            slug=f"v1-default-{str(user.id).replace('-', '')}",
            owner_id=user.id,
            status="active",
            created_at=now,
            updated_at=now,
        )
        workspace = cast(Workspace, state["workspace"])

        knowledge_base_response = client.post(
            f"/api/v1/knowledge-bases?workspace_id={workspace.id}",
            headers=headers,
            json={"name": "Travel Policy", "description": "Company travel rules"},
        )
        assert knowledge_base_response.status_code == 201
        knowledge_base_id = knowledge_base_response.json()["data"]["id"]

        upload_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents?workspace_id={workspace.id}",
            headers=headers,
            files={"file": ("travel_policy.txt", b"meal allowance is GBP 40", "text/plain")},
        )
        assert upload_response.status_code == 201
        upload_body = upload_response.json()
        assert upload_body["message"] == "document uploaded and processed"
        assert upload_body["data"]["filename"] == "travel_policy.txt"
        assert upload_body["data"]["status"] == "completed"
        assert upload_body["data"]["chunk_count"] == 1

        query_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
            headers=headers,
            json={"question": "What is the maximum meal allowance?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert query_response.status_code == 200
    query_body = query_response.json()
    assert query_body["success"] is True
    assert query_body["data"]["answer"] == "The maximum meal allowance is GBP 40 per day."
    assert query_body["data"]["sources"] == [
        {
            "document_name": "travel_policy.txt",
            "page_number": 1,
            "chunk_id": str(cast(DocumentChunk, state["chunk"]).id),
            "original_text": "The maximum meal allowance is GBP 40 per day.",
            "similarity_score": 0.95,
        }
    ]
