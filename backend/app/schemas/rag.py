import uuid

from pydantic import BaseModel, Field

from backend.app.services.llms import LLMProviderName
from backend.app.services.query_rewriting import QueryMessageRole


class RAGQueryHistoryMessage(BaseModel):
    role: QueryMessageRole
    content: str = Field(min_length=1, max_length=4000)


class RAGQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[RAGQueryHistoryMessage] = Field(default_factory=list, max_length=20)


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
