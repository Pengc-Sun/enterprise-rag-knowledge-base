import uuid
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.schemas.user import UserCreate
from backend.app.services.users import EmailAlreadyRegisteredError, build_user_for_create


class FakeResult:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def scalar_one_or_none(self) -> User | None:
        return self.user


class FakeSession:
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    async def execute(self, statement: object) -> FakeResult:
        return FakeResult(self.user)


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
    session = cast(AsyncSession, FakeSession(existing_user))
    user_create = UserCreate(
        email="taken@example.com",
        username="new_user",
        password="secure-password",
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        await build_user_for_create(session, user_create)
