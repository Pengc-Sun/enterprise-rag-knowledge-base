#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from backend.app.evaluation.retrieval_metrics import (
    RetrievalMetrics,
    compare_retrieval_strategies,
    load_evaluation_questions,
    load_retrieval_predictions,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval predictions against labelled RAG questions."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluations/rag_qa_dataset.jsonl"),
        help="JSONL evaluation dataset path.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="JSONL predictions with question_id, strategy, and ranked candidates.",
    )
    parser.add_argument(
        "--k",
        type=int,
        nargs="+",
        default=[1, 3, 5, 10],
        help="K values for Hit Rate, Recall, MRR, and nDCG.",
    )
    parser.add_argument(
        "--document-only",
        action="store_true",
        help="Match only the expected document name and ignore expected_page.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path to write metric rows as JSON.",
    )
    args = parser.parse_args()

    questions = load_evaluation_questions(args.dataset)
    predictions = load_retrieval_predictions(args.predictions)
    metrics = compare_retrieval_strategies(
        questions=questions,
        predictions=predictions,
        k_values=args.k,
        require_page_match=not args.document_only,
    )

    print(format_markdown_table(metrics))
    if args.json_output is not None:
        args.json_output.write_text(json.dumps([metric.to_dict() for metric in metrics], indent=2))

    return 0


def format_markdown_table(metrics: list[RetrievalMetrics]) -> str:
    rows = [
        "| Strategy | Questions | Predicted | K | Hit Rate | Recall | MRR | nDCG |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for metric in metrics:
        rows.append(
            f"| {metric.strategy} | {metric.question_count} | {metric.predicted_count} | "
            f"{metric.k} | {metric.hit_rate:.3f} | {metric.recall:.3f} | "
            f"{metric.mrr:.3f} | {metric.ndcg:.3f} |"
        )
    return "\n".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
