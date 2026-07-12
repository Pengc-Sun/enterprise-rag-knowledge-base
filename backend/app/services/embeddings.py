import hashlib
import math
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.core.config import Settings


class EmbeddingProviderName(StrEnum):
    DETERMINISTIC = "deterministic"
    BGE = "bge"
    QWEN = "qwen"
    OPENAI = "openai"


class EmbeddingProviderError(Exception):
    message = "Embedding provider error"


class UnsupportedEmbeddingProviderError(EmbeddingProviderError):
    message = "Unsupported embedding provider"


class EmbeddingProviderConfigurationError(EmbeddingProviderError):
    message = "Embedding provider is not configured"


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    async def embed_query(self, text: str) -> list[float]:
        embeddings = await self.embed_documents([text])
        return embeddings[0]


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int) -> None:
        validate_dimension(dimension)
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dimension:
            digest = hashlib.blake2b(
                f"{counter}:{text}".encode(),
                digest_size=64,
            ).digest()
            for index in range(0, len(digest), 2):
                raw_value = int.from_bytes(digest[index : index + 2], byteorder="big")
                values.append((raw_value / 65535.0) * 2.0 - 1.0)
                if len(values) == self.dimension:
                    break
            counter += 1

        return normalize_vector(values)


class RemoteEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        provider_name: EmbeddingProviderName,
        dimension: int,
        model: str,
        api_key: str | None,
        base_url: str | None = None,
    ) -> None:
        validate_dimension(dimension)
        if not model:
            raise EmbeddingProviderConfigurationError

        self.provider_name = provider_name
        self._dimension = dimension
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingProviderConfigurationError
        raise EmbeddingProviderError(
            f"{self.provider_name.value} embedding client is not implemented yet"
        )


def create_embedding_provider(settings: "Settings") -> EmbeddingProvider:
    return build_embedding_provider(
        provider=settings.embedding_provider,
        dimension=settings.embedding_dimension,
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
    )


def build_embedding_provider(
    provider: str,
    dimension: int,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> EmbeddingProvider:
    validate_dimension(dimension)

    try:
        provider_name = EmbeddingProviderName(provider)
    except ValueError as exc:
        raise UnsupportedEmbeddingProviderError from exc

    if provider_name == EmbeddingProviderName.DETERMINISTIC:
        return DeterministicEmbeddingProvider(dimension=dimension)

    return RemoteEmbeddingProvider(
        provider_name=provider_name,
        dimension=dimension,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def validate_dimension(dimension: int) -> None:
    if dimension <= 0:
        raise EmbeddingProviderConfigurationError


def normalize_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]
