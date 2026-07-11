from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.schemas.health import DatabaseHealthData, HealthData
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


@router.get("/health/database", response_model=APIResponse[DatabaseHealthData])
async def database_health_check(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[DatabaseHealthData]:
    await session.execute(text("SELECT 1"))
    return success_response(DatabaseHealthData(status="ok", database="postgresql"))
