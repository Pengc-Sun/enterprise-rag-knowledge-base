import pytest
from pydantic import ValidationError

from backend.app.schemas.user import UserCreate


def test_user_create_schema_accepts_valid_user() -> None:
    user_create = UserCreate(
        email="user@example.com",
        username="enterprise_user",
        password="secure-password",
    )

    assert str(user_create.email) == "user@example.com"
    assert user_create.username == "enterprise_user"


def test_user_create_schema_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="user@example.com",
            username="enterprise_user",
            password="short",
        )

