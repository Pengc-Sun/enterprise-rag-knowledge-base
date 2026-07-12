import uuid

from pydantic import BaseModel, Field

from backend.app.services.llms import LLMProviderName


class RAGQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class RAGQueryResponse(BaseModel):
    answer: str
    model: str
    provider: LLMProviderName
    context_chunk_count: int
    context_chunk_ids: list[uuid.UUID]
