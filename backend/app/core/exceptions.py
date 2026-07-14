from typing import Any, cast

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.logging import get_request_id
from backend.app.schemas.response import APIResponse


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, StarletteHTTPException):
        message = str(exc.detail)
        status_code = exc.status_code
        error_code = error_code_for_status(status_code)
    else:
        message = "Internal server error"
        status_code = 500
        error_code = "internal_server_error"

    return build_error_response(
        status_code=status_code,
        message=message,
        error_code=error_code,
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    validation_error = cast(RequestValidationError, exc)
    return build_error_response(
        status_code=422,
        message="Validation error",
        error_code="validation_error",
        details={"errors": jsonable_encoder(validation_error.errors())},
    )


def build_error_response(
    *,
    status_code: int,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    response = APIResponse[dict[str, object]](
        success=False,
        message=message,
        data={
            "error": {
                "code": error_code,
                "status_code": status_code,
                "request_id": get_request_id(),
                "details": details or {},
            }
        },
    )
    return JSONResponse(status_code=status_code, content=response.model_dump())


def error_code_for_status(status_code: int) -> str:
    codes = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_server_error",
        502: "bad_gateway",
        503: "service_unavailable",
        504: "gateway_timeout",
    }
    return codes.get(status_code, f"http_{status_code}")
