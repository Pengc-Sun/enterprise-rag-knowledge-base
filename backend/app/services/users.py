from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(ValueError):
    def __init__(self, email: str) -> None:
        super().__init__(f"Email is already registered: {email}")
        self.email = email


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def ensure_email_is_available(session: AsyncSession, email: str) -> None:
    existing_user = await get_user_by_email(session, email)
    if existing_user is not None:
        raise EmailAlreadyRegisteredError(email)


async def build_user_for_create(session: AsyncSession, user_create: UserCreate) -> User:
    await ensure_email_is_available(session, str(user_create.email))
    return User(
        email=str(user_create.email),
        username=user_create.username,
        hashed_password=hash_password(user_create.password),
    )

