import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from backend.app.models.document import DocumentChunk
from backend.app.services.retrieval import HybridRetrievedChunk

if TYPE_CHECKING:
    from backend.app.core.config import Settings


class RerankerProviderName(StrEnum):
    DETERMINISTIC = "deterministic"
    CROSS_ENCODER = "cross_encoder"


class RerankerError(Exception):
    message = "Reranker error"


class UnsupportedRerankerProviderError(RerankerError):
    message = "Unsupported reranker provider"


class RerankerConfigurationError(RerankerError):
    message = "Reranker is not configured"


@dataclass(frozen=True)
class RerankedChunk:
    chunk: DocumentChunk
    rerank_score: float
    rrf_score: float
    vector_score: float | None = None
    keyword_score: float | None = None


class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[HybridRetrievedChunk],
        limit: int,
    ) -> list[RerankedChunk]:
        raise NotImplementedError


class DeterministicCrossEncoderReranker(Reranker):
    def __init__(self, model: str) -> None:
        validate_model(model)
        self.model = model

    async def rerank(
        self,
        query: str,
        candidates: list[HybridRetrievedChunk],
        limit: int,
    ) -> list[RerankedChunk]:
        validate_limit(limit)
        query_terms = tokenize(query)
        reranked = [self._score_candidate(query_terms, candidate) for candidate in candidates]
        return sorted(
            reranked,
            key=lambda item: (-item.rerank_score, -item.rrf_score, item.chunk.chunk_index),
        )[:limit]

    def _score_candidate(
        self,
        query_terms: set[str],
        candidate: HybridRetrievedChunk,
    ) -> RerankedChunk:
        chunk_terms = tokenize(candidate.chunk.content)
        if candidate.chunk.section_title:
            chunk_terms |= tokenize(candidate.chunk.section_title)
        overlap_score = len(query_terms & chunk_terms) / max(len(query_terms), 1)
        rerank_score = overlap_score + candidate.rrf_score
        return RerankedChunk(
            chunk=candidate.chunk,
            rerank_score=rerank_score,
            rrf_score=candidate.rrf_score,
            vector_score=candidate.vector_score,
            keyword_score=candidate.keyword_score,
        )


def create_reranker(settings: "Settings") -> Reranker:
    return build_reranker(
        provider=settings.reranker_provider,
        model=settings.reranker_model,
    )


def build_reranker(provider: str, model: str) -> Reranker:
    validate_model(model)
    try:
        provider_name = RerankerProviderName(provider)
    except ValueError as exc:
        raise UnsupportedRerankerProviderError from exc

    if provider_name in {
        RerankerProviderName.DETERMINISTIC,
        RerankerProviderName.CROSS_ENCODER,
    }:
        return DeterministicCrossEncoderReranker(model=model)

    raise UnsupportedRerankerProviderError


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def validate_limit(limit: int) -> None:
    if limit <= 0:
        raise RerankerConfigurationError


def validate_model(model: str) -> None:
    if not model:
        raise RerankerConfigurationError
