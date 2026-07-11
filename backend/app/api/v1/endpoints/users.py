from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.response import APIResponse, success_response
from backend.app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=APIResponse[UserRead])
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> APIResponse[UserRead]:
    return success_response(UserRead.model_validate(current_user))
