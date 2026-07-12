import json

import pytest

from backend.app.services.streaming import format_sse_event, stream_text_tokens


def test_format_sse_event_serializes_json_payload() -> None:
    event = format_sse_event("token", {"token": "hello"})

    assert event.startswith("event: token\n")
    assert event.endswith("\n\n")
    payload = event.split("data: ", maxsplit=1)[1].strip()
    assert json.loads(payload) == {"token": "hello"}


@pytest.mark.asyncio
async def test_stream_text_tokens_preserves_spaces_between_words() -> None:
    tokens = [token async for token in stream_text_tokens("hello streaming world")]

    assert tokens == ["hello ", "streaming ", "world"]
