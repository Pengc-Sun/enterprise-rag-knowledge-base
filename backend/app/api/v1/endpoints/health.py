from fastapi import APIRouter

from backend.app.core.config import get_settings
from backend.app.schemas.health import HealthData
from backend.app.schemas.response import APIResponse, success_response

router = APIRouter(tags=["system"])


@router.get("/health", response_model=APIResponse[HealthData])
async def health_check() -> APIResponse[HealthData]:
    settings = get_settings()
    return success_response(
        HealthData(
            status="ok",
            service=settings.app_name,
            environment=settings.app_env,
        )
    )

