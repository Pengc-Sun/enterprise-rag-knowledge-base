import json
from pathlib import Path

import pytest

from backend.app.evaluation.retrieval_metrics import (
    EvaluationQuestion,
    RetrievalCandidate,
    RetrievalPrediction,
    compare_retrieval_strategies,
    evaluate_retrieval_strategy,
    first_relevant_rank,
    load_evaluation_questions,
    load_retrieval_predictions,
)


def make_questions() -> list[EvaluationQuestion]:
    return [
        EvaluationQuestion(
            id="rag_eval_001",
            question="What is the maximum meal allowance?",
            expected_answer="GBP 40 per day",
            expected_document="travel_policy.pdf",
            expected_page=8,
            category="travel_policy",
            difficulty="easy",
        ),
        EvaluationQuestion(
            id="rag_eval_002",
            question="What is the minimum password length?",
            expected_answer="14 characters",
            expected_document="security_handbook.pdf",
            expected_page=4,
            category="security",
            difficulty="easy",
        ),
    ]


def test_evaluate_retrieval_strategy_calculates_hit_recall_mrr_and_ndcg() -> None:
    questions = make_questions()
    predictions = [
        RetrievalPrediction(
            question_id="rag_eval_001",
            strategy="vector",
            candidates=(
                RetrievalCandidate(document_name="expense_policy.pdf", page_number=2),
                RetrievalCandidate(document_name="travel_policy.pdf", page_number=8),
            ),
        ),
        RetrievalPrediction(
            question_id="rag_eval_002",
            strategy="vector",
            candidates=(RetrievalCandidate(document_name="security_handbook.pdf", page_number=5),),
        ),
    ]

    metrics = evaluate_retrieval_strategy(
        questions=questions,
        predictions=predictions,
        strategy="vector",
        k_values=[1, 3],
    )

    assert metrics[0].k == 1
    assert metrics[0].hit_rate == 0
    assert metrics[0].recall == 0
    assert metrics[0].mrr == 0
    assert metrics[0].ndcg == 0

    assert metrics[1].k == 3
    assert metrics[1].hit_rate == 0.5
    assert metrics[1].recall == 0.5
    assert metrics[1].mrr == 0.25
    assert metrics[1].ndcg == pytest.approx(0.3154648767)


def test_compare_retrieval_strategies_orders_expected_baselines() -> None:
    questions = make_questions()
    predictions = [
        RetrievalPrediction(
            question_id="rag_eval_001",
            strategy="hybrid_reranker",
            candidates=(RetrievalCandidate(document_name="travel_policy.pdf", page_number=8),),
        ),
        RetrievalPrediction(
            question_id="rag_eval_001",
            strategy="vector",
            candidates=(RetrievalCandidate(document_name="expense_policy.pdf", page_number=2),),
        ),
        RetrievalPrediction(
            question_id="rag_eval_001",
            strategy="hybrid",
            candidates=(RetrievalCandidate(document_name="travel_policy.pdf", page_number=8),),
        ),
    ]

    metrics = compare_retrieval_strategies(
        questions=questions,
        predictions=predictions,
        k_values=[1],
    )

    assert [metric.strategy for metric in metrics] == ["vector", "hybrid", "hybrid_reranker"]
    assert [metric.hit_rate for metric in metrics] == [0, 0.5, 0.5]


def test_first_relevant_rank_can_match_document_only() -> None:
    question = make_questions()[0]
    candidates = [RetrievalCandidate(document_name="travel_policy.pdf", page_number=7)]

    assert (
        first_relevant_rank(
            question=question,
            candidates=candidates,
            require_page_match=True,
        )
        is None
    )
    assert (
        first_relevant_rank(
            question=question,
            candidates=candidates,
            require_page_match=False,
        )
        == 1
    )


def test_loaders_parse_dataset_and_prediction_jsonl(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "id": "rag_eval_001",
                "question": "Question?",
                "expected_answer": "Answer",
                "expected_document": "policy.pdf",
                "expected_page": 3,
                "category": "policy",
                "difficulty": "easy",
            }
        )
        + "\n"
    )
    predictions_path.write_text(
        json.dumps(
            {
                "question_id": "rag_eval_001",
                "strategy": "hybrid",
                "candidates": [{"document": "policy.pdf", "page": 3, "score": 0.91}],
            }
        )
        + "\n"
    )

    questions = load_evaluation_questions(dataset_path)
    predictions = load_retrieval_predictions(predictions_path)

    assert questions[0].expected_document == "policy.pdf"
    assert predictions[0].candidates[0].score == 0.91


def test_duplicate_predictions_for_same_strategy_and_question_are_rejected() -> None:
    questions = make_questions()
    predictions = [
        RetrievalPrediction(question_id="rag_eval_001", strategy="vector", candidates=()),
        RetrievalPrediction(question_id="rag_eval_001", strategy="vector", candidates=()),
    ]

    with pytest.raises(ValueError, match="duplicate prediction"):
        evaluate_retrieval_strategy(
            questions=questions,
            predictions=predictions,
            strategy="vector",
            k_values=[1],
        )
