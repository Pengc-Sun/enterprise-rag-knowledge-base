from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.v1.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.exceptions import http_exception_handler, validation_exception_handler
from backend.app.core.logging import configure_logging
from backend.app.db.session import dispose_db_engine
from backend.app.middleware.request_logging import RequestLoggingMiddleware
from backend.app.schemas.health import HealthData
from backend.app.schemas.response import APIResponse, success_response

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_json)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_db_engine()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.add_exception_handler(Exception, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.get("/health", tags=["system"], response_model=APIResponse[HealthData])
async def root_health_check() -> APIResponse[HealthData]:
    return success_response(
        HealthData(
            status="ok",
            service=settings.app_name,
            environment=settings.app_env,
        )
    )
