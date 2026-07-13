# RAG Evaluation Dataset

This directory contains the labelled question set for Week 7 retrieval and answer evaluation.

## Files

- `rag_qa_dataset.jsonl`: 40 labelled RAG evaluation questions.

## JSONL Schema

Each line is a JSON object with these fields:

```json
{
  "id": "rag_eval_001",
  "category": "travel_policy",
  "difficulty": "easy",
  "question": "What is the maximum meal allowance?",
  "expected_answer": "The maximum meal allowance is GBP 40 per day.",
  "expected_document": "travel_policy.pdf",
  "expected_page": 8,
  "answer_aliases": ["GBP 40 per day"],
  "required_terms": ["meal allowance", "GBP 40"],
  "metadata_filters": {"file_types": ["pdf"]}
}
```

## Intended Use

Day 47 can use `expected_document` and `expected_page` for retrieval metrics such as Hit Rate@K, Recall@K, MRR, and nDCG. Answer checks can use `expected_answer`, `answer_aliases`, and `required_terms` for deterministic or LLM-assisted grading.

The records are synthetic enterprise policy examples and are designed to be paired with matching seed documents or fixtures in later evaluation work. Expected documents use the file types supported by the ingestion pipeline: PDF, TXT, Markdown, and DOCX.

## Retrieval Metrics

Day 47 adds reusable retrieval metrics for comparing vector-only, hybrid, and hybrid-plus-reranker runs. Prediction files are JSONL, with one row per question and strategy:

```json
{
  "question_id": "rag_eval_001",
  "strategy": "hybrid",
  "candidates": [
    {"document": "travel_policy.pdf", "page": 8, "score": 0.91},
    {"document": "expense_policy.pdf", "page": 2, "score": 0.42}
  ]
}
```

Supported strategy names include `vector`, `hybrid`, and `hybrid_reranker`. Run:

```bash
make eval-retrieval PREDICTIONS=evaluations/retrieval_predictions.jsonl
```

The evaluator reports Hit Rate@K, Recall@K, MRR@K, and nDCG@K. By default a candidate must match both `expected_document` and `expected_page`; pass `--document-only` to the script for document-level evaluation.
