import json
from collections.abc import AsyncIterator


async def stream_text_tokens(text: str) -> AsyncIterator[str]:
    words = text.split(" ")
    for index, word in enumerate(words):
        separator = " " if index < len(words) - 1 else ""
        yield f"{word}{separator}"


def format_sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
