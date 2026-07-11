import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import auth as auth_dependencies
from backend.app.core.security import create_access_token
from backend.app.models.user import User, UserRole


def make_user(*, is_active: bool = True) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="enterprise_user",
        hashed_password="hashed",
        role=UserRole.USER.value,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_get_current_user_returns_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    token = create_access_token(str(user.id))
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    async def fake_get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User:
        assert user_id == user.id
        return user

    monkeypatch.setattr(auth_dependencies, "get_user_by_id", fake_get_user_by_id)

    current_user = await auth_dependencies.get_current_user(
        credentials,
        cast(AsyncSession, object()),
    )

    assert current_user is user


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await auth_dependencies.get_current_user(None, cast(AsyncSession, object()))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependencies.get_current_user(credentials, cast(AsyncSession, object()))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    token = create_access_token(str(user_id))
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    async def fake_get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(auth_dependencies, "get_user_by_id", fake_get_user_by_id)

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependencies.get_current_user(credentials, cast(AsyncSession, object()))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.asyncio
async def test_get_current_active_user_rejects_inactive_user() -> None:
    user = make_user(is_active=False)

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependencies.get_current_active_user(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Inactive user"

