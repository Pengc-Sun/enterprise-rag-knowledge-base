from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, cast

REQUEST_ID_HEADER = "X-Request-ID"
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class StructuredJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        event = getattr(record, "event", None)
        if event is not None:
            payload["event"] = event

        structured_fields = getattr(record, "structured_fields", None)
        if isinstance(structured_fields, dict):
            payload.update(cast(dict[str, Any], to_json_safe(structured_fields)))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(*, level: str, json_logs: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    if json_logs:
        handler.setFormatter(StructuredJSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s"
            )
        )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())


def bind_request_id(request_id: str | None = None) -> Token[str | None]:
    return request_id_context.set(request_id or generate_request_id())


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)


def get_request_id() -> str | None:
    return request_id_context.get()


def generate_request_id() -> str:
    return str(uuid.uuid4())


def log_structured(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "structured_fields": fields,
        },
    )


def to_json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_json_safe(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value
