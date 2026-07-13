from datetime import UTC, datetime, timedelta

import jwt

from backend.app.core.config import get_settings
from backend.app.core.security import create_access_token, hash_password, verify_password


def test_hash_password_does_not_store_plaintext() -> None:
    password = "correct horse battery staple"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrong password", hashed_password)


def test_create_access_token_contains_subject() -> None:
    settings = get_settings()

    token = create_access_token("user-id", expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    assert payload["sub"] == "user-id"


def test_create_access_token_uses_custom_expiration_delta() -> None:
    settings = get_settings()
    before = datetime.now(UTC)

    token = create_access_token("user-id", expires_delta=timedelta(seconds=30))
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    after = datetime.now(UTC)
    expires_at = datetime.fromtimestamp(payload["exp"], UTC)
    assert before + timedelta(seconds=29) <= expires_at <= after + timedelta(seconds=31)
