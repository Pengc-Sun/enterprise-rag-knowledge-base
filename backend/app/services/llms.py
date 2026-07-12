from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from backend.app.core.config import Settings


class LLMProviderName(StrEnum):
    DETERMINISTIC = "deterministic"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    OPENAI = "openai"


DEFAULT_BASE_URLS = {
    LLMProviderName.DEEPSEEK: "https://api.deepseek.com/v1",
    LLMProviderName.QWEN: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    LLMProviderName.OPENAI: "https://api.openai.com/v1",
}


class LLMProviderError(Exception):
    message = "LLM provider error"


class UnsupportedLLMProviderError(LLMProviderError):
    message = "Unsupported LLM provider"


class LLMProviderConfigurationError(LLMProviderError):
    message = "LLM provider is not configured"


class LLMProviderResponseError(LLMProviderError):
    message = "LLM provider returned an invalid response"


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider: LLMProviderName
    usage: LLMUsage | None = None


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        raise NotImplementedError


class DeterministicLLMProvider(LLMProvider):
    def __init__(self, model: str) -> None:
        validate_model(model)
        self.model = model

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        validate_messages(messages)
        user_messages = [message.content for message in messages if message.role == "user"]
        content = user_messages[-1] if user_messages else messages[-1].content
        return LLMResponse(
            content=f"Deterministic response: {content}",
            model=self.model,
            provider=LLMProviderName.DETERMINISTIC,
        )


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(
        self,
        provider_name: LLMProviderName,
        model: str,
        api_key: str | None,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        validate_model(model)
        validate_timeout(timeout_seconds)
        if provider_name == LLMProviderName.DETERMINISTIC:
            raise UnsupportedLLMProviderError

        self.provider_name = provider_name
        self.model = model
        self.api_key = api_key
        self.base_url = base_url or DEFAULT_BASE_URLS[provider_name]
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderConfigurationError
        validate_messages(messages)

        payload = build_chat_payload(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        if self._client is not None:
            data = await self._request(self._client, endpoint, payload)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                data = await self._request(client, endpoint, payload)

        return parse_chat_response(
            data,
            model=self.model,
            provider_name=self.provider_name,
        )

    async def _request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.provider_name.value} LLM request failed") from exc
        if not isinstance(data, dict):
            raise LLMProviderResponseError
        return data


def create_llm_provider(settings: "Settings") -> LLMProvider:
    return build_llm_provider(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def build_llm_provider(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> LLMProvider:
    validate_model(model)

    try:
        provider_name = LLMProviderName(provider)
    except ValueError as exc:
        raise UnsupportedLLMProviderError from exc

    if provider_name == LLMProviderName.DETERMINISTIC:
        return DeterministicLLMProvider(model=model)

    return OpenAICompatibleLLMProvider(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def build_chat_payload(
    model: str,
    messages: list[LLMMessage],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": message.role, "content": message.content} for message in messages],
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def parse_chat_response(
    data: dict[str, Any],
    model: str,
    provider_name: LLMProviderName,
) -> LLMResponse:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMProviderResponseError

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMProviderResponseError

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LLMProviderResponseError

    content = message.get("content")
    if not isinstance(content, str):
        raise LLMProviderResponseError

    response_model = data.get("model")
    usage_data = data.get("usage")
    return LLMResponse(
        content=content,
        model=response_model if isinstance(response_model, str) else model,
        provider=provider_name,
        usage=parse_usage(usage_data),
    )


def parse_usage(usage_data: object) -> LLMUsage | None:
    if not isinstance(usage_data, dict):
        return None
    return LLMUsage(
        prompt_tokens=extract_optional_int(usage_data.get("prompt_tokens")),
        completion_tokens=extract_optional_int(usage_data.get("completion_tokens")),
        total_tokens=extract_optional_int(usage_data.get("total_tokens")),
    )


def extract_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def validate_messages(messages: list[LLMMessage]) -> None:
    if not messages:
        raise LLMProviderConfigurationError
    if any(not message.role or not message.content for message in messages):
        raise LLMProviderConfigurationError


def validate_model(model: str) -> None:
    if not model:
        raise LLMProviderConfigurationError


def validate_timeout(timeout_seconds: float) -> None:
    if timeout_seconds <= 0:
        raise LLMProviderConfigurationError
