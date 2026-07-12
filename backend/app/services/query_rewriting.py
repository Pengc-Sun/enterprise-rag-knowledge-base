from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.core.config import Settings


class QueryMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class QueryRewriteMessage:
    role: QueryMessageRole
    content: str


@dataclass(frozen=True)
class QueryRewriteResult:
    original_query: str
    rewritten_query: str
    was_rewritten: bool


@dataclass(frozen=True)
class QueryRewriteConfig:
    enabled: bool = True
    history_limit: int = 6

    def __post_init__(self) -> None:
        if self.history_limit <= 0:
            raise ValueError("query_rewrite_history_limit must be positive")


FOLLOW_UP_PREFIXES = (
    "what about",
    "how about",
    "and ",
    "what if",
    "for ",
    "in ",
    "does it",
    "is it",
    "are they",
    "can i",
    "can we",
)
FOLLOW_UP_REFERENCES = {"it", "that", "this", "they", "them", "there", "those"}


def create_query_rewrite_config(settings: "Settings") -> QueryRewriteConfig:
    return QueryRewriteConfig(
        enabled=settings.query_rewrite_enabled,
        history_limit=settings.query_rewrite_history_limit,
    )


def rewrite_query(
    question: str,
    history: list[QueryRewriteMessage],
    config: QueryRewriteConfig | None = None,
) -> QueryRewriteResult:
    effective_config = config or QueryRewriteConfig()
    normalized_question = normalize_question(question)
    if not effective_config.enabled:
        return QueryRewriteResult(question, normalized_question, was_rewritten=False)

    recent_history = history[-effective_config.history_limit :]
    previous_user_question = find_previous_user_question(recent_history)
    if previous_user_question is None or not is_follow_up_question(normalized_question):
        return QueryRewriteResult(question, normalized_question, was_rewritten=False)

    rewritten_query = build_standalone_query(previous_user_question, normalized_question)
    return QueryRewriteResult(
        original_query=question,
        rewritten_query=rewritten_query,
        was_rewritten=rewritten_query != normalized_question,
    )


def normalize_question(question: str) -> str:
    return " ".join(question.split())


def find_previous_user_question(history: list[QueryRewriteMessage]) -> str | None:
    for message in reversed(history):
        if message.role == QueryMessageRole.USER and normalize_question(message.content):
            return normalize_question(message.content)
    return None


def is_follow_up_question(question: str) -> bool:
    lowered_question = question.lower().strip()
    if not lowered_question:
        return False
    if lowered_question.startswith(FOLLOW_UP_PREFIXES):
        return True
    tokens = [token.strip("?.,!;:").lower() for token in lowered_question.split()]
    return len(tokens) <= 8 and any(token in FOLLOW_UP_REFERENCES for token in tokens)


def build_standalone_query(previous_question: str, follow_up_question: str) -> str:
    previous = previous_question.rstrip(" ?")
    follow_up = follow_up_question.rstrip(" ?")
    lowered_follow_up = follow_up.lower()

    for prefix in ("what about", "how about"):
        if lowered_follow_up.startswith(prefix):
            detail = follow_up[len(prefix) :].strip()
            return f"{previous} about {detail}?" if detail else f"{previous}?"

    for prefix in ("for", "in"):
        if lowered_follow_up.startswith(f"{prefix} "):
            return f"{previous} {follow_up}?"

    if lowered_follow_up.startswith("and "):
        return f"{previous}; {follow_up}?"

    return f"{previous}; follow-up: {follow_up}?"
