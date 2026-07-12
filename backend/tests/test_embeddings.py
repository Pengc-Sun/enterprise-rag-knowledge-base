import math

import pytest

from backend.app.core.config import Settings
from backend.app.services.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderConfigurationError,
    EmbeddingProviderError,
    EmbeddingProviderName,
    RemoteEmbeddingProvider,
    UnsupportedEmbeddingProviderError,
    build_embedding_provider,
    create_embedding_provider,
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
async def test_remote_provider_placeholder_raises_until_client_is_implemented() -> None:
    provider = RemoteEmbeddingProvider(
        provider_name=EmbeddingProviderName.BGE,
        dimension=1024,
        model="bge-large",
        api_key="secret",
    )

    with pytest.raises(EmbeddingProviderError):
        await provider.embed_documents(["hello"])


def vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))
