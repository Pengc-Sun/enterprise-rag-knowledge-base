import uuid
from datetime import UTC, datetime
from typing import cast

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints import auth
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.main import app
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate
from backend.app.services.users import EmailAlreadyRegisteredError


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        username="enterprise_user",
        hashed_password="hashed",
        role=UserRole.USER.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def override_db_session() -> AsyncSession:
    return cast(AsyncSession, object())


def test_register_user_returns_created_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()

    async def fake_create_user(session: AsyncSession, user_create: UserCreate) -> User:
        return user

    monkeypatch.setattr(auth, "create_user", fake_create_user)
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "username": "enterprise_user",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "user registered"
    assert body["data"]["email"] == "user@example.com"
    assert body["data"]["username"] == "enterprise_user"
    assert "hashed_password" not in body["data"]


def test_register_user_rejects_duplicate_email(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create_user(session: AsyncSession, user_create: UserCreate) -> User:
        raise EmailAlreadyRegisteredError(str(user_create.email))

    monkeypatch.setattr(auth, "create_user", fake_create_user)
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "username": "enterprise_user",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Email is already registered"


def test_login_user_returns_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()

    async def fake_authenticate_user(session: AsyncSession, email: str, password: str) -> User:
        return user

    monkeypatch.setattr(auth, "authenticate_user", fake_authenticate_user)
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "secure-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "login successful"
    assert body["data"]["token_type"] == "bearer"

    settings = get_settings()
    payload = jwt.decode(
        body["data"]["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["sub"] == str(user.id)


def test_login_user_rejects_invalid_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_authenticate_user(
        session: AsyncSession,
        email: str,
        password: str,
    ) -> None:
        return None

    monkeypatch.setattr(auth, "authenticate_user", fake_authenticate_user)
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrong-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Invalid email or password"
