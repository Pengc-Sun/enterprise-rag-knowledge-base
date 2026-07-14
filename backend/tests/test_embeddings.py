import json
import math

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.services.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderConfigurationError,
    EmbeddingProviderName,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderResponseError,
    EmbeddingProviderTimeoutError,
    RemoteEmbeddingProvider,
    UnsupportedEmbeddingProviderError,
    build_embedding_provider,
    create_embedding_provider,
    parse_embedding_response,
)


@pytest.mark.asyncio
async def test_deterministic_provider_embeds_documents_with_configured_dimension() -> None:
    provider = DeterministicEmbeddingProvider(dimension=8)

    embeddings = await provider.embed_documents(["alpha", "beta"])

    assert len(embeddings) == 2
    assert all(len(embedding) == 8 for embedding in embeddings)
    assert embeddings[0] != embeddings[1]
    assert math.isclose(vector_norm(embeddings[0]), 1.0)


@pytest.mark.asyncio
async def test_deterministic_provider_returns_stable_query_embedding() -> None:
    provider = DeterministicEmbeddingProvider(dimension=8)

    first_embedding = await provider.embed_query("same query")
    second_embedding = await provider.embed_query("same query")

    assert first_embedding == second_embedding


def test_build_embedding_provider_rejects_unknown_provider() -> None:
    with pytest.raises(UnsupportedEmbeddingProviderError):
        build_embedding_provider(
            provider="unknown",
            dimension=8,
            model="unused",
        )


def test_build_embedding_provider_rejects_invalid_dimension() -> None:
    with pytest.raises(EmbeddingProviderConfigurationError):
        build_embedding_provider(
            provider=EmbeddingProviderName.DETERMINISTIC.value,
            dimension=0,
            model="unused",
        )


def test_create_embedding_provider_uses_settings() -> None:
    settings = Settings(
        embedding_provider="deterministic",
        embedding_dimension=12,
        embedding_model="deterministic-hash",
    )

    provider = create_embedding_provider(settings)

    assert isinstance(provider, DeterministicEmbeddingProvider)
    assert provider.dimension == 12


def test_build_embedding_provider_creates_remote_provider() -> None:
    provider = build_embedding_provider(
        provider=EmbeddingProviderName.OPENAI.value,
        dimension=1536,
        model="text-embedding-3-small",
        api_key="secret",
        base_url="https://api.openai.com/v1",
    )

    assert isinstance(provider, RemoteEmbeddingProvider)
    assert provider.provider_name == EmbeddingProviderName.OPENAI
    assert provider.dimension == 1536
    assert provider.model == "text-embedding-3-small"
    assert provider.base_url == "https://api.openai.com/v1"


@pytest.mark.asyncio
async def test_remote_provider_requires_api_key() -> None:
    provider = RemoteEmbeddingProvider(
        provider_name=EmbeddingProviderName.QWEN,
        dimension=1024,
        model="text-embedding-v4",
        api_key=None,
    )

    with pytest.raises(EmbeddingProviderConfigurationError):
        await provider.embed_query("hello")


@pytest.mark.asyncio
async def test_remote_provider_posts_openai_compatible_embedding_request() -> None:
    captured_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["authorization"] = request.headers.get("authorization")
        captured_request["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RemoteEmbeddingProvider(
            provider_name=EmbeddingProviderName.OPENAI,
            dimension=3,
            model="text-embedding-test",
            api_key="secret",
            base_url="https://example.test/api/v1/",
            client=client,
        )

        embeddings = await provider.embed_documents(["first", "second"])

    assert captured_request == {
        "url": "https://example.test/api/v1/embeddings",
        "authorization": "Bearer secret",
        "payload": {"model": "text-embedding-test", "input": ["first", "second"]},
    }
    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


@pytest.mark.asyncio
async def test_remote_provider_returns_empty_list_for_empty_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RemoteEmbeddingProvider(
            provider_name=EmbeddingProviderName.OPENAI,
            dimension=3,
            model="text-embedding-test",
            api_key="secret",
            base_url="https://example.test/api/v1",
            client=client,
        )

        assert await provider.embed_documents([]) == []


def test_parse_embedding_response_rejects_wrong_dimension() -> None:
    with pytest.raises(EmbeddingProviderResponseError):
        parse_embedding_response(
            {"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
            expected_count=1,
            dimension=3,
        )


@pytest.mark.asyncio
async def test_remote_provider_maps_rate_limit_response() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as client:
        provider = RemoteEmbeddingProvider(
            provider_name=EmbeddingProviderName.OPENAI,
            dimension=3,
            model="text-embedding-test",
            api_key="secret",
            base_url="https://example.test/api/v1",
            client=client,
        )

        with pytest.raises(EmbeddingProviderRateLimitError):
            await provider.embed_documents(["hello"])


@pytest.mark.asyncio
async def test_remote_provider_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RemoteEmbeddingProvider(
            provider_name=EmbeddingProviderName.OPENAI,
            dimension=3,
            model="text-embedding-test",
            api_key="secret",
            base_url="https://example.test/api/v1",
            client=client,
        )

        with pytest.raises(EmbeddingProviderTimeoutError):
            await provider.embed_documents(["hello"])


def vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))
