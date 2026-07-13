from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.logging import (
    REQUEST_ID_HEADER,
    bind_request_id,
    get_request_id,
    log_structured,
    reset_request_id,
)

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER)
        token = bind_request_id(request_id)
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = get_request_id() or ""
            return response
        except Exception as exc:
            log_request(
                request=request,
                status_code=status_code,
                started_at=started_at,
                error=str(exc),
            )
            raise
        finally:
            if request.scope.get("type") == "http":
                if "response" in locals():
                    log_request(
                        request=request,
                        status_code=status_code,
                        started_at=started_at,
                        error=None,
                    )
                reset_request_id(token)


def log_request(
    *,
    request: Request,
    status_code: int,
    started_at: float,
    error: str | None,
) -> None:
    total_latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    log_structured(
        logger,
        logging.ERROR if error else logging.INFO,
        "http_request_completed",
        method=request.method,
        path=request.url.path,
        status=status_code,
        total_latency_ms=total_latency_ms,
        error=error,
    )
