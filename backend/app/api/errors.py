from fastapi import HTTPException, status

from backend.app.services.llms import (
    LLMProviderError,
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
)


def provider_exception_to_http(exc: Exception, fallback_message: str) -> HTTPException:
    message = getattr(exc, "message", fallback_message)
    if isinstance(exc, LLMProviderRateLimitError):
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
    if isinstance(exc, LLMProviderTimeoutError):
        return HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=message)
    if isinstance(exc, LLMProviderError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
