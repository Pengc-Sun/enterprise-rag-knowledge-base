import hashlib
import math
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from backend.app.core.config import Settings


class EmbeddingProviderName(StrEnum):
    DETERMINISTIC = "deterministic"
    BGE = "bge"
    QWEN = "qwen"
    OPENAI = "openai"


DEFAULT_BASE_URLS = {
    EmbeddingProviderName.OPENAI: "https://api.openai.com/v1",
    EmbeddingProviderName.QWEN: "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


class EmbeddingProviderError(Exception):
    message = "Embedding provider error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class UnsupportedEmbeddingProviderError(EmbeddingProviderError):
    message = "Unsupported embedding provider"


class EmbeddingProviderConfigurationError(EmbeddingProviderError):
    message = "Embedding provider is not configured"


class EmbeddingProviderResponseError(EmbeddingProviderError):
    message = "Embedding provider returned an invalid response"


class EmbeddingProviderTimeoutError(EmbeddingProviderError):
    message = "Embedding provider request timed out"


class EmbeddingProviderRateLimitError(EmbeddingProviderError):
    message = "Embedding provider rate limit exceeded"


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
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        validate_dimension(dimension)
        validate_timeout(timeout_seconds)
        if not model:
            raise EmbeddingProviderConfigurationError

        self.provider_name = provider_name
        self._dimension = dimension
        self.model = model
        self.api_key = api_key
        self.base_url = base_url or DEFAULT_BASE_URLS.get(provider_name)
        self.timeout_seconds = timeout_seconds
        self._client = client

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingProviderConfigurationError
        if not self.base_url:
            raise EmbeddingProviderConfigurationError
        if not texts:
            return []

        endpoint = f"{self.base_url.rstrip('/')}/embeddings"
        payload: dict[str, object] = {"model": self.model, "input": texts}

        if self._client is not None:
            data = await self._request(self._client, endpoint, payload)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                data = await self._request(client, endpoint, payload)

        return parse_embedding_response(data, expected_count=len(texts), dimension=self.dimension)

    async def _request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if response.status_code == 429:
                raise EmbeddingProviderRateLimitError
            if 500 <= response.status_code < 600:
                raise EmbeddingProviderError(f"{self.provider_name.value} embedding request failed")
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise EmbeddingProviderTimeoutError from exc
        except EmbeddingProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            raise EmbeddingProviderError(
                f"{self.provider_name.value} embedding request failed"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(
                f"{self.provider_name.value} embedding request failed"
            ) from exc

        if not isinstance(data, dict):
            raise EmbeddingProviderResponseError
        return data


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


def parse_embedding_response(
    data: dict[str, Any],
    *,
    expected_count: int,
    dimension: int,
) -> list[list[float]]:
    items = data.get("data")
    if not isinstance(items, list) or len(items) != expected_count:
        raise EmbeddingProviderResponseError

    indexed_items = sorted(enumerate(items), key=embedding_item_sort_key)
    embeddings: list[list[float]] = []
    for _, item in indexed_items:
        if not isinstance(item, dict):
            raise EmbeddingProviderResponseError
        raw_embedding = item.get("embedding")
        if not isinstance(raw_embedding, list):
            raise EmbeddingProviderResponseError
        embedding: list[float] = []
        for value in raw_embedding:
            if not isinstance(value, int | float):
                raise EmbeddingProviderResponseError
            embedding.append(float(value))
        if len(embedding) != dimension:
            raise EmbeddingProviderResponseError
        embeddings.append(embedding)

    return embeddings


def embedding_item_sort_key(item: tuple[int, object]) -> tuple[int, int]:
    position, value = item
    if isinstance(value, dict) and isinstance(value.get("index"), int):
        return (int(value["index"]), position)
    return (position, position)


def validate_dimension(dimension: int) -> None:
    if dimension <= 0:
        raise EmbeddingProviderConfigurationError


def validate_timeout(timeout_seconds: float) -> None:
    if timeout_seconds <= 0:
        raise EmbeddingProviderConfigurationError


def normalize_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]
