from backend.app.core.security import hash_password, verify_password


def test_hash_password_does_not_store_plaintext() -> None:
    password = "correct horse battery staple"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrong password", hashed_password)

