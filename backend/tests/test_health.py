from fastapi.testclient import TestClient

from backend.app.db.session import get_db_session
from backend.app.main import app


def test_health_check() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_api_v1_health_check() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "success"
    assert body["data"]["service"] == "Enterprise RAG Knowledge Base"


def test_not_found_uses_api_response_format() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/missing")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Not Found"
    assert body["data"] is None


class FakeSession:
    async def execute(self, statement: object) -> object:
        return object()


def override_db_session() -> FakeSession:
    return FakeSession()


def test_api_v1_database_health_check() -> None:
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        client = TestClient(app)
        response = client.get("/api/v1/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"status": "ok", "database": "postgresql"}
