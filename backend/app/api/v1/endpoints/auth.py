from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db_session
from backend.app.schemas.auth import AccessToken, LoginRequest
from backend.app.schemas.response import APIResponse, success_response
from backend.app.schemas.user import UserCreate, UserRead
from backend.app.services.users import (
    EmailAlreadyRegisteredError,
    UsernameAlreadyRegisteredError,
    authenticate_user,
    create_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=APIResponse[UserRead], status_code=status.HTTP_201_CREATED)
async def register_user(
    user_create: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[UserRead]:
    try:
        user = await create_user(session, user_create)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc
    except UsernameAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already registered",
        ) from exc

    return success_response(UserRead.model_validate(user), message="user registered")


@router.post("/login", response_model=APIResponse[AccessToken])
async def login_user(
    login_request: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> APIResponse[AccessToken]:
    user = await authenticate_user(session, str(login_request.email), login_request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(subject=str(user.id))
    return success_response(AccessToken(access_token=access_token), message="login successful")
