from typing import cast

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.schemas.response import APIResponse


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, StarletteHTTPException):
        message = str(exc.detail)
        status_code = exc.status_code
    else:
        message = "Internal server error"
        status_code = 500

    response = APIResponse[None](success=False, message=message, data=None)
    return JSONResponse(status_code=status_code, content=response.model_dump())


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    validation_error = cast(RequestValidationError, exc)
    response = APIResponse[dict[str, object]](
        success=False,
        message="Validation error",
        data={"errors": validation_error.errors()},
    )
    return JSONResponse(status_code=422, content=response.model_dump())
