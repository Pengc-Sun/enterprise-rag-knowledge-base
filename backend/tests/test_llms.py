import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.services.llms import (
    DeterministicLLMProvider,
    LLMMessage,
    LLMProviderConfigurationError,
    LLMProviderError,
    LLMProviderName,
    LLMProviderRateLimitError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
    LLMUsage,
    OpenAICompatibleLLMProvider,
    UnsupportedLLMProviderError,
    build_chat_payload,
    build_llm_provider,
    create_llm_provider,
    parse_chat_response,
)


@pytest.mark.asyncio
async def test_deterministic_llm_provider_returns_last_user_message() -> None:
    provider = DeterministicLLMProvider(model="deterministic-chat")

    response = await provider.generate(
        [
            LLMMessage(role="system", content="Answer briefly."),
            LLMMessage(role="user", content="What is RAG?"),
        ]
    )

    assert response.content == "Deterministic response: What is RAG?"
    assert response.model == "deterministic-chat"
    assert response.provider == LLMProviderName.DETERMINISTIC


def test_build_llm_provider_rejects_unknown_provider() -> None:
    with pytest.raises(UnsupportedLLMProviderError):
        build_llm_provider(provider="unknown", model="chat-model")


def test_build_llm_provider_rejects_empty_model() -> None:
    with pytest.raises(LLMProviderConfigurationError):
        build_llm_provider(provider=LLMProviderName.DETERMINISTIC.value, model="")


def test_create_llm_provider_uses_settings() -> None:
    settings = Settings(
        llm_provider="deterministic",
        llm_model="local-test-model",
    )

    provider = create_llm_provider(settings)

    assert isinstance(provider, DeterministicLLMProvider)
    assert provider.model == "local-test-model"


def test_build_llm_provider_creates_openai_compatible_provider() -> None:
    provider = build_llm_provider(
        provider=LLMProviderName.DEEPSEEK.value,
        model="deepseek-chat",
        api_key="secret",
    )

    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.provider_name == LLMProviderName.DEEPSEEK
    assert provider.model == "deepseek-chat"
    assert provider.base_url == "https://api.deepseek.com/v1"


def test_build_chat_payload_includes_optional_generation_parameters() -> None:
    payload = build_chat_payload(
        model="qwen-plus",
        messages=[LLMMessage(role="user", content="hello")],
        temperature=0.1,
        max_tokens=256,
    )

    assert payload == {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": "hello"}],
        "temperature": 0.1,
        "max_tokens": 256,
    }


@pytest.mark.asyncio
async def test_openai_compatible_provider_posts_chat_completion_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "model": "openai-test-model",
                "choices": [{"message": {"content": "answer text"}}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLLMProvider(
        provider_name=LLMProviderName.OPENAI,
        model="gpt-test",
        api_key="secret",
        base_url="https://example.test/v1",
        client=client,
    )

    try:
        response = await provider.generate(
            [LLMMessage(role="user", content="hello")],
            temperature=0.2,
            max_tokens=128,
        )
    finally:
        await client.aclose()

    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert '"model":"gpt-test"' in str(captured["payload"])
    assert '"temperature":0.2' in str(captured["payload"])
    assert response.content == "answer text"
    assert response.model == "openai-test-model"
    assert response.provider == LLMProviderName.OPENAI
    assert response.usage == LLMUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5)


@pytest.mark.asyncio
async def test_openai_compatible_provider_requires_api_key() -> None:
    provider = OpenAICompatibleLLMProvider(
        provider_name=LLMProviderName.QWEN,
        model="qwen-plus",
        api_key=None,
    )

    with pytest.raises(LLMProviderConfigurationError):
        await provider.generate([LLMMessage(role="user", content="hello")])


@pytest.mark.asyncio
async def test_openai_compatible_provider_wraps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "failed"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLLMProvider(
        provider_name=LLMProviderName.OPENAI,
        model="gpt-test",
        api_key="secret",
        client=client,
    )

    try:
        with pytest.raises(LLMProviderError):
            await provider.generate([LLMMessage(role="user", content="hello")])
    finally:
        await client.aclose()


def test_parse_chat_response_rejects_invalid_payload() -> None:
    with pytest.raises(LLMProviderResponseError):
        parse_chat_response({}, model="gpt-test", provider_name=LLMProviderName.OPENAI)


@pytest.mark.asyncio
async def test_openai_compatible_provider_retries_transient_server_errors() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(
            200,
            json={"model": "gpt-test", "choices": [{"message": {"content": "ok"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLLMProvider(
        provider_name=LLMProviderName.OPENAI,
        model="gpt-test",
        api_key="secret",
        client=client,
        max_retries=2,
        retry_backoff_seconds=0,
    )

    try:
        response = await provider.generate([LLMMessage(role="user", content="hello")])
    finally:
        await client.aclose()

    assert attempts == 2
    assert response.content == "ok"


@pytest.mark.asyncio
async def test_openai_compatible_provider_reports_rate_limit_after_retries() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"error": "rate limited"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLLMProvider(
        provider_name=LLMProviderName.OPENAI,
        model="gpt-test",
        api_key="secret",
        client=client,
        max_retries=2,
        retry_backoff_seconds=0,
    )

    try:
        with pytest.raises(LLMProviderRateLimitError):
            await provider.generate([LLMMessage(role="user", content="hello")])
    finally:
        await client.aclose()

    assert attempts == 2


@pytest.mark.asyncio
async def test_openai_compatible_provider_reports_timeout_after_retries() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLLMProvider(
        provider_name=LLMProviderName.OPENAI,
        model="gpt-test",
        api_key="secret",
        client=client,
        max_retries=2,
        retry_backoff_seconds=0,
    )

    try:
        with pytest.raises(LLMProviderTimeoutError):
            await provider.generate([LLMMessage(role="user", content="hello")])
    finally:
        await client.aclose()

    assert attempts == 2
