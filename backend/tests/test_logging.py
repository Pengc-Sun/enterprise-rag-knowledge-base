import json
import logging

from fastapi.testclient import TestClient

from backend.app.core.logging import StructuredJSONFormatter, bind_request_id, reset_request_id
from backend.app.main import app


def test_structured_json_formatter_includes_request_context_and_extra_fields() -> None:
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="event message",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.event = "rag_query_completed"
    record.structured_fields = {
        "knowledge_base_id": "kb-1",
        "status": "success",
        "retrieved_chunk_ids": ["chunk-1"],
    }

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "event message"
    assert payload["request_id"] == "req-123"
    assert payload["event"] == "rag_query_completed"
    assert payload["knowledge_base_id"] == "kb-1"
    assert payload["retrieved_chunk_ids"] == ["chunk-1"]


def test_bind_request_id_sets_and_resets_context() -> None:
    token = bind_request_id("req-abc")
    try:
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=20,
            msg="message",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-abc"
        payload = json.loads(formatter.format(record))
        assert payload["request_id"] == "req-abc"
    finally:
        reset_request_id(token)


def test_request_logging_middleware_returns_request_id_header() -> None:
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
