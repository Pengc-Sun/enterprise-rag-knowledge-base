from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.v1.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.exceptions import http_exception_handler, validation_exception_handler
from backend.app.schemas.health import HealthData
from backend.app.schemas.response import APIResponse, success_response

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)

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
