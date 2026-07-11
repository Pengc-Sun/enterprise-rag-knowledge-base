import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.app.api.dependencies.auth import get_current_active_user
from backend.app.main import app
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


def test_read_current_user_returns_authenticated_user() -> None:
    user = make_user()

    def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user

    try:
        client = TestClient(app)
        response = client.get("/api/v1/users/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "user@example.com"
    assert body["data"]["username"] == "enterprise_user"


def test_read_current_user_requires_token() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Could not validate credentials"

