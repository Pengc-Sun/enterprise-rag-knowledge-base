import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.api.v1.endpoints import rag as rag_endpoints
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.document import Document, DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseVisibility
from backend.app.models.user import User, UserRole
from backend.app.services.embeddings import EmbeddingProviderConfigurationError
from backend.app.services.llms import LLMProviderName
from backend.app.services.rag import RAGAnswer, RAGSourceCitation
from backend.app.services.retrieval import RetrievedChunk


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


def make_chunk(knowledge_base_id: uuid.UUID) -> DocumentChunk:
    now = datetime.now(UTC)
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base_id,
        filename="architecture.md",
        file_type="md",
        file_size=128,
        file_hash="a" * 64,
        storage_path="storage/uploads/architecture.md",
        status="completed",
        error_message=None,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        knowledge_base_id=knowledge_base_id,
        content="context body",
        chunk_index=0,
        page_number=1,
        section_title=None,
        token_count=2,
        embedding=[1.0, 0.0, 0.0],
        embedding_status="embedded",
        embedding_error=None,
        chunk_metadata={},
        created_at=now,
        updated_at=now,
    )
    chunk.document = document
    return chunk


def override_db_session() -> AsyncSession:
    return cast(AsyncSession, object())


def set_overrides(user: User) -> None:
    def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_db_session


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_query_knowledge_base_returns_rag_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)
    chunk = make_chunk(knowledge_base.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        assert knowledge_base_id == knowledge_base.id
        assert user_id == user.id
        assert "viewer" in allowed_permissions
        return knowledge_base

    async def fake_answer_knowledge_base_question(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        question: str,
        embedding_provider: object,
        llm_provider: object,
        retrieval_config: object,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> RAGAnswer:
        assert knowledge_base_id == knowledge_base.id
        assert question == "How does RAG work?"
        assert temperature == 0.2
        assert max_tokens == 1024
        return RAGAnswer(
            answer="Use retrieval then generation.",
            model="deterministic-chat",
            provider=LLMProviderName.DETERMINISTIC,
            context_chunks=[RetrievedChunk(chunk=chunk, similarity_score=0.9)],
            sources=[
                RAGSourceCitation(
                    document_name="architecture.md",
                    page_number=1,
                    chunk_id=chunk.id,
                    original_text="context body",
                    similarity_score=0.9,
                )
            ],
        )

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
    monkeypatch.setattr(
        rag_endpoints,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="deterministic",
            embedding_dimension=1536,
            embedding_model="deterministic-hash",
            embedding_api_key=None,
            embedding_base_url=None,
            retrieval_top_k=10,
            final_context_k=4,
            llm_provider="deterministic",
            llm_model="deterministic-chat",
            llm_api_key=None,
            llm_base_url=None,
            llm_temperature=0.2,
            llm_max_tokens=1024,
            llm_timeout_seconds=30.0,
        ),
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/query",
            json={"question": "How does RAG work?"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["answer"] == "Use retrieval then generation."
    assert body["data"]["provider"] == "deterministic"
    assert body["data"]["context_chunk_count"] == 1
    assert body["data"]["context_chunk_ids"] == [str(chunk.id)]
    assert body["data"]["sources"] == [
        {
            "document_name": "architecture.md",
            "page_number": 1,
            "chunk_id": str(chunk.id),
            "original_text": "context body",
            "similarity_score": 0.9,
        }
    ]


def test_query_knowledge_base_requires_read_permission(monkeypatch: pytest.MonkeyPatch) -> None:
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
        rag_endpoints,
        "get_knowledge_base_for_user",
        fake_get_knowledge_base_for_user,
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
            json={"question": "How does RAG work?"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json()["message"] == "Knowledge base not found"


def test_query_knowledge_base_returns_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    knowledge_base = make_knowledge_base(user.id)

    async def fake_get_knowledge_base_for_user(
        session: AsyncSession,
        knowledge_base_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_permissions: frozenset[str],
    ) -> KnowledgeBase:
        return knowledge_base

    async def fake_answer_knowledge_base_question(*args: object, **kwargs: object) -> RAGAnswer:
        raise EmbeddingProviderConfigurationError

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
    monkeypatch.setattr(
        rag_endpoints,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="deterministic",
            embedding_dimension=1536,
            embedding_model="deterministic-hash",
            embedding_api_key=None,
            embedding_base_url=None,
            retrieval_top_k=10,
            final_context_k=4,
            llm_provider="deterministic",
            llm_model="deterministic-chat",
            llm_api_key=None,
            llm_base_url=None,
            llm_temperature=0.2,
            llm_max_tokens=1024,
            llm_timeout_seconds=30.0,
        ),
    )
    set_overrides(user)

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base.id}/query",
            json={"question": "How does RAG work?"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json()["message"] == "Embedding provider is not configured"
