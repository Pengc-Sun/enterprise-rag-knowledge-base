import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.services.llms import LLMProviderName
from backend.app.services.query_rewriting import QueryMessageRole


class RAGQueryHistoryMessage(BaseModel):
    role: QueryMessageRole
    content: str = Field(min_length=1, max_length=4000)


class RAGMetadataFilter(BaseModel):
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    file_types: list[str] = Field(default_factory=list, max_length=20)
    created_after: datetime | None = None
    created_before: datetime | None = None
    departments: list[str] = Field(default_factory=list, max_length=20)
    permissions: list[str] = Field(default_factory=list, max_length=20)


class RAGQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[RAGQueryHistoryMessage] = Field(default_factory=list, max_length=20)
    filters: RAGMetadataFilter = Field(default_factory=RAGMetadataFilter)


class RAGSourceCitationRead(BaseModel):
    document_name: str
    page_number: int
    chunk_id: uuid.UUID
    original_text: str
    similarity_score: float


class RAGQueryResponse(BaseModel):
    answer: str
    rewritten_question: str
    question_was_rewritten: bool
    model: str
    provider: LLMProviderName
    context_chunk_count: int
    context_chunk_ids: list[uuid.UUID]
    sources: list[RAGSourceCitationRead]


class RAGRetrievalDebugCandidateRead(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    chunk_index: int
    page_number: int
    section_title: str | None
    content_preview: str
    vector_rank: int | None
    keyword_rank: int | None
    vector_score: float | None
    keyword_score: float | None
    rrf_score: float
    rerank_score: float
    final_rank: int


class RAGRetrievalDebugResponse(BaseModel):
    original_question: str
    rewritten_question: str
    question_was_rewritten: bool
    candidate_count: int
    candidates: list[RAGRetrievalDebugCandidateRead]
