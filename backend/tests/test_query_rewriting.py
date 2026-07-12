from backend.app.core.config import Settings
from backend.app.services.query_rewriting import (
    QueryMessageRole,
    QueryRewriteConfig,
    QueryRewriteMessage,
    create_query_rewrite_config,
    find_previous_user_question,
    is_follow_up_question,
    rewrite_query,
)


def test_create_query_rewrite_config_uses_settings() -> None:
    settings = Settings(query_rewrite_enabled=False, query_rewrite_history_limit=3)

    config = create_query_rewrite_config(settings)

    assert config.enabled is False
    assert config.history_limit == 3


def test_query_rewrite_config_rejects_invalid_history_limit() -> None:
    try:
        QueryRewriteConfig(history_limit=0)
    except ValueError as exc:
        assert str(exc) == "query_rewrite_history_limit must be positive"
    else:
        raise AssertionError("expected ValueError")


def test_find_previous_user_question_ignores_assistant_messages() -> None:
    history = [
        QueryRewriteMessage(role=QueryMessageRole.USER, content="What is the travel policy?"),
        QueryRewriteMessage(role=QueryMessageRole.ASSISTANT, content="It covers travel."),
    ]

    assert find_previous_user_question(history) == "What is the travel policy?"


def test_is_follow_up_question_detects_short_contextual_questions() -> None:
    assert is_follow_up_question("What about London?") is True
    assert is_follow_up_question("Does it apply there?") is True
    assert is_follow_up_question("What is the complete travel policy?") is False


def test_rewrite_query_rewrites_follow_up_to_standalone_query() -> None:
    result = rewrite_query(
        "What about London?",
        [QueryRewriteMessage(role=QueryMessageRole.USER, content="What is the travel policy?")],
    )

    assert result.original_query == "What about London?"
    assert result.rewritten_query == "What is the travel policy about London?"
    assert result.was_rewritten is True


def test_rewrite_query_leaves_standalone_question_unchanged() -> None:
    result = rewrite_query(
        "What is the London travel policy?",
        [QueryRewriteMessage(role=QueryMessageRole.USER, content="What is the travel policy?")],
    )

    assert result.rewritten_query == "What is the London travel policy?"
    assert result.was_rewritten is False


def test_rewrite_query_respects_disabled_config() -> None:
    result = rewrite_query(
        "What about London?",
        [QueryRewriteMessage(role=QueryMessageRole.USER, content="What is the travel policy?")],
        QueryRewriteConfig(enabled=False),
    )

    assert result.rewritten_query == "What about London?"
    assert result.was_rewritten is False
