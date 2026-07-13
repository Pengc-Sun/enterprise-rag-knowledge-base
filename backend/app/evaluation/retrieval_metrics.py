import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluationQuestion:
    id: str
    question: str
    expected_answer: str
    expected_document: str
    expected_page: int
    category: str
    difficulty: str


@dataclass(frozen=True)
class RetrievalCandidate:
    document_name: str
    page_number: int
    score: float | None = None


@dataclass(frozen=True)
class RetrievalPrediction:
    question_id: str
    strategy: str
    candidates: tuple[RetrievalCandidate, ...]


@dataclass(frozen=True)
class RetrievalMetrics:
    strategy: str
    question_count: int
    predicted_count: int
    k: int
    hit_rate: float
    recall: float
    mrr: float
    ndcg: float

    def to_dict(self) -> dict[str, str | int | float]:
        return asdict(self)


def load_evaluation_questions(path: Path) -> list[EvaluationQuestion]:
    return [parse_evaluation_question(item) for item in load_jsonl(path)]


def load_retrieval_predictions(path: Path) -> list[RetrievalPrediction]:
    return [parse_retrieval_prediction(item) for item in load_jsonl(path)]


def load_jsonl(path: Path) -> list[Mapping[str, object]]:
    records: list[Mapping[str, object]] = []
    with path.open() as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            records.append(value)
    return records


def parse_evaluation_question(data: Mapping[str, object]) -> EvaluationQuestion:
    return EvaluationQuestion(
        id=require_string(data, "id"),
        question=require_string(data, "question"),
        expected_answer=require_string(data, "expected_answer"),
        expected_document=require_string(data, "expected_document"),
        expected_page=require_int(data, "expected_page"),
        category=require_string(data, "category"),
        difficulty=require_string(data, "difficulty"),
    )


def parse_retrieval_prediction(data: Mapping[str, object]) -> RetrievalPrediction:
    candidates_value = data.get("candidates")
    if not isinstance(candidates_value, list):
        raise ValueError("prediction candidates must be a list")

    return RetrievalPrediction(
        question_id=require_string(data, "question_id"),
        strategy=require_string(data, "strategy"),
        candidates=tuple(parse_retrieval_candidate(candidate) for candidate in candidates_value),
    )


def parse_retrieval_candidate(data: object) -> RetrievalCandidate:
    if not isinstance(data, dict):
        raise ValueError("candidate must be a JSON object")

    score_value = data.get("score")
    if score_value is not None and not isinstance(score_value, int | float):
        raise ValueError("candidate score must be numeric when provided")

    return RetrievalCandidate(
        document_name=require_string(data, "document"),
        page_number=require_int(data, "page"),
        score=float(score_value) if score_value is not None else None,
    )


def evaluate_retrieval_strategy(
    questions: Sequence[EvaluationQuestion],
    predictions: Sequence[RetrievalPrediction],
    *,
    strategy: str,
    k_values: Iterable[int],
    require_page_match: bool = True,
) -> list[RetrievalMetrics]:
    prediction_by_question_id = index_predictions(predictions, strategy=strategy)
    sorted_k_values = sorted(set(k_values))
    if not sorted_k_values:
        raise ValueError("k_values must not be empty")
    if any(k <= 0 for k in sorted_k_values):
        raise ValueError("k_values must be positive")

    metrics: list[RetrievalMetrics] = []
    for k in sorted_k_values:
        hit_total = 0.0
        recall_total = 0.0
        reciprocal_rank_total = 0.0
        ndcg_total = 0.0

        for question in questions:
            prediction = prediction_by_question_id.get(question.id)
            candidates = prediction.candidates if prediction is not None else ()
            rank = first_relevant_rank(
                question=question,
                candidates=candidates[:k],
                require_page_match=require_page_match,
            )
            if rank is None:
                continue

            hit_total += 1.0
            recall_total += 1.0
            reciprocal_rank_total += 1.0 / rank
            ndcg_total += 1.0 / math.log2(rank + 1)

        question_count = len(questions)
        metrics.append(
            RetrievalMetrics(
                strategy=strategy,
                question_count=question_count,
                predicted_count=len(prediction_by_question_id),
                k=k,
                hit_rate=average(hit_total, question_count),
                recall=average(recall_total, question_count),
                mrr=average(reciprocal_rank_total, question_count),
                ndcg=average(ndcg_total, question_count),
            )
        )

    return metrics


def compare_retrieval_strategies(
    questions: Sequence[EvaluationQuestion],
    predictions: Sequence[RetrievalPrediction],
    *,
    k_values: Iterable[int],
    require_page_match: bool = True,
) -> list[RetrievalMetrics]:
    strategies = sorted({prediction.strategy for prediction in predictions}, key=strategy_sort_key)
    results: list[RetrievalMetrics] = []
    for strategy in strategies:
        results.extend(
            evaluate_retrieval_strategy(
                questions=questions,
                predictions=predictions,
                strategy=strategy,
                k_values=k_values,
                require_page_match=require_page_match,
            )
        )
    return results


def index_predictions(
    predictions: Sequence[RetrievalPrediction],
    *,
    strategy: str,
) -> dict[str, RetrievalPrediction]:
    indexed: dict[str, RetrievalPrediction] = {}
    for prediction in predictions:
        if prediction.strategy != strategy:
            continue
        if prediction.question_id in indexed:
            raise ValueError(
                f"duplicate prediction for strategy={strategy!r} "
                f"question_id={prediction.question_id!r}"
            )
        indexed[prediction.question_id] = prediction
    return indexed


def first_relevant_rank(
    *,
    question: EvaluationQuestion,
    candidates: Sequence[RetrievalCandidate],
    require_page_match: bool,
) -> int | None:
    for rank, candidate in enumerate(candidates, start=1):
        if is_relevant_candidate(
            question=question,
            candidate=candidate,
            require_page_match=require_page_match,
        ):
            return rank
    return None


def is_relevant_candidate(
    *,
    question: EvaluationQuestion,
    candidate: RetrievalCandidate,
    require_page_match: bool,
) -> bool:
    expected_document = Path(question.expected_document).name.casefold()
    candidate_document = Path(candidate.document_name).name.casefold()
    if candidate_document != expected_document:
        return False
    if require_page_match and candidate.page_number != question.expected_page:
        return False
    return True


def average(total: float, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return total / denominator


def strategy_sort_key(strategy: str) -> tuple[int, str]:
    preferred_order = {
        "vector": 0,
        "vector_only": 0,
        "hybrid": 1,
        "hybrid_reranker": 2,
        "hybrid+reranker": 2,
    }
    return (preferred_order.get(strategy, 100), strategy)


def require_string(data: Mapping[str, object], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def require_int(data: Mapping[str, object], field: str) -> int:
    value = data.get(field)
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def group_metrics_by_strategy(
    metrics: Sequence[RetrievalMetrics],
) -> dict[str, list[RetrievalMetrics]]:
    grouped: defaultdict[str, list[RetrievalMetrics]] = defaultdict(list)
    for metric in metrics:
        grouped[metric.strategy].append(metric)
    return dict(grouped)
