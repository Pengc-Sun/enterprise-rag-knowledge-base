from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password, verify_password
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(ValueError):
    def __init__(self, email: str) -> None:
        super().__init__(f"Email is already registered: {email}")
        self.email = email


class UsernameAlreadyRegisteredError(ValueError):
    def __init__(self, username: str) -> None:
        super().__init__(f"Username is already registered: {username}")
        self.username = username


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def ensure_email_is_available(session: AsyncSession, email: str) -> None:
    existing_user = await get_user_by_email(session, email)
    if existing_user is not None:
        raise EmailAlreadyRegisteredError(email)


async def ensure_username_is_available(session: AsyncSession, username: str) -> None:
    existing_user = await get_user_by_username(session, username)
    if existing_user is not None:
        raise UsernameAlreadyRegisteredError(username)


async def build_user_for_create(session: AsyncSession, user_create: UserCreate) -> User:
    await ensure_email_is_available(session, str(user_create.email))
    await ensure_username_is_available(session, user_create.username)
    return User(
        email=str(user_create.email),
        username=user_create.username,
        hashed_password=hash_password(user_create.password),
    )


async def create_user(session: AsyncSession, user_create: UserCreate) -> User:
    user = await build_user_for_create(session, user_create)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
