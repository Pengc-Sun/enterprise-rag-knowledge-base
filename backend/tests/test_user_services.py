import uuid
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate
from backend.app.services.users import (
    EmailAlreadyRegisteredError,
    UsernameAlreadyRegisteredError,
    authenticate_user,
    build_user_for_create,
    get_user_by_id,
)


class FakeResult:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def scalar_one_or_none(self) -> User | None:
        return self.user


class FakeSession:
    def __init__(self, users: list[User | None] | None = None) -> None:
        self.users = users or [None]

    async def execute(self, statement: object) -> FakeResult:
        if len(self.users) > 1:
            return FakeResult(self.users.pop(0))
        return FakeResult(self.users[0])


@pytest.mark.asyncio
async def test_build_user_for_create_hashes_password() -> None:
    session = cast(AsyncSession, FakeSession())
    user_create = UserCreate(
        email="new@example.com",
        username="new_user",
        password="secure-password",
    )

    user = await build_user_for_create(session, user_create)

    assert user.email == "new@example.com"
    assert user.username == "new_user"
    assert user.hashed_password != "secure-password"


@pytest.mark.asyncio
async def test_build_user_for_create_rejects_duplicate_email() -> None:
    existing_user = User(
        id=uuid.uuid4(),
        email="taken@example.com",
        username="taken_user",
        hashed_password="hashed",
    )
    session = cast(AsyncSession, FakeSession([existing_user]))
    user_create = UserCreate(
        email="taken@example.com",
        username="new_user",
        password="secure-password",
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        await build_user_for_create(session, user_create)


@pytest.mark.asyncio
async def test_build_user_for_create_rejects_duplicate_username() -> None:
    existing_user = User(
        id=uuid.uuid4(),
        email="existing@example.com",
        username="taken_user",
        hashed_password="hashed",
    )
    session = cast(AsyncSession, FakeSession([None, existing_user]))
    user_create = UserCreate(
        email="new@example.com",
        username="taken_user",
        password="secure-password",
    )

    with pytest.raises(UsernameAlreadyRegisteredError):
        await build_user_for_create(session, user_create)


@pytest.mark.asyncio
async def test_authenticate_user_returns_user_for_valid_password() -> None:
    existing_user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="user",
        hashed_password=hash_password("secure-password"),
    )
    session = cast(AsyncSession, FakeSession([existing_user]))

    user = await authenticate_user(session, "user@example.com", "secure-password")

    assert user is existing_user


@pytest.mark.asyncio
async def test_authenticate_user_rejects_invalid_password() -> None:
    existing_user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="user",
        hashed_password=hash_password("secure-password"),
    )
    session = cast(AsyncSession, FakeSession([existing_user]))

    user = await authenticate_user(session, "user@example.com", "wrong-password")

    assert user is None


@pytest.mark.asyncio
async def test_get_user_by_id_returns_user() -> None:
    existing_user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="user",
        hashed_password="hashed",
    )
    session = cast(AsyncSession, FakeSession([existing_user]))

    user = await get_user_by_id(session, existing_user.id)

    assert user is existing_user
