# Evaluation Guide

This document explains the current RAG evaluation assets and retrieval metric workflow.

## Evaluation Goals

The evaluation layer is designed to answer practical questions about retrieval quality:

- Does the expected document appear in the retrieved candidates?
- Does the expected page appear in the retrieved candidates?
- Does hybrid retrieval outperform vector-only retrieval?
- Does reranking improve candidate ordering?
- Can results be reproduced in CI or local development?

## Files

```text
evaluations/rag_qa_dataset.jsonl              Labelled synthetic enterprise questions
evaluations/retrieval_predictions.jsonl       Example prediction rows
scripts/run_retrieval_evaluation.py           CLI for retrieval metrics
backend/app/evaluation/retrieval_metrics.py   Metric implementation
backend/tests/test_retrieval_evaluation_metrics.py
```

## Dataset Schema

Each dataset row is JSONL:

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

The current dataset contains 40 labelled synthetic enterprise questions. The expected documents are designed to reflect supported upload formats: PDF, DOCX, TXT, Markdown, and `.markdown`.

## Prediction Schema

Prediction rows are JSONL and contain one question result for one retrieval strategy:

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

Supported strategy names include:

- `vector`
- `vector_only`
- `hybrid`
- `hybrid_reranker`
- `hybrid+reranker`

The evaluator sorts these strategies in a stable order so comparison tables are easy to read.

## Metrics

The evaluator reports metrics for configurable K values, defaulting to `1`, `3`, `5`, and `10`.

| Metric | Meaning |
| --- | --- |
| Hit Rate@K | Share of questions where at least one relevant candidate appears in the top K. |
| Recall@K | Current implementation is equivalent to Hit Rate@K because each question has one expected document/page target. |
| MRR@K | Mean reciprocal rank of the first relevant candidate inside top K. |
| nDCG@K | Rank-sensitive gain for the first relevant candidate inside top K. |

By default, a candidate is relevant only when both document name and page number match the expected values. Document-only matching is available for broader checks.

## Running Evaluation

Run the default prediction file:

```bash
make eval-retrieval PREDICTIONS=evaluations/retrieval_predictions.jsonl
```

Run a custom prediction file:

```bash
make eval-retrieval PREDICTIONS=tmp/my_predictions.jsonl
```

Run document-only matching directly through the script:

```bash
.venv/bin/python scripts/run_retrieval_evaluation.py   --predictions evaluations/retrieval_predictions.jsonl   --document-only
```

Write machine-readable JSON output:

```bash
.venv/bin/python scripts/run_retrieval_evaluation.py   --predictions evaluations/retrieval_predictions.jsonl   --json-output evaluations/retrieval_metrics.json
```

## Reading Results

The script prints a Markdown table:

```text
| Strategy | Questions | Predicted | K | Hit Rate | Recall | MRR | nDCG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
```

Interpretation guidelines:

- Higher Hit Rate@K means more questions find the expected source.
- Higher MRR means relevant evidence appears earlier.
- Higher nDCG means the rank distribution improved.
- A strategy with high Hit Rate@10 but low MRR may need reranking or better prompt context selection.

## Retrieval Debug Endpoint

The API also exposes retrieval diagnostics:

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/query/debug
```

This endpoint returns candidate-level retrieval data:

- vector rank and score
- keyword rank and score
- RRF score
- rerank score
- final rank
- chunk/document metadata

Use this endpoint to investigate why a specific evaluation question failed.

## RAG Reliability Signals

The RAG service emits structured logs for each query:

- `user_id`
- `knowledge_base_id`
- query text after rewriting
- retrieved chunk IDs
- retrieval latency
- rerank latency
- LLM latency
- total latency
- token usage
- status
- error details

LLM provider failures are normalized into API responses:

- persistent rate limit: HTTP `429`, code `rate_limited`
- persistent timeout: HTTP `504`, code `gateway_timeout`
- other provider errors: HTTP `400`, code `bad_request`

These fields make failed evaluations easier to correlate with logs through `request_id`.

## Recommended Evaluation Workflow

1. Load or create representative documents.
2. Upload documents into a knowledge base.
3. Run the retrieval strategy being evaluated.
4. Export ranked candidates into the prediction JSONL schema.
5. Run `make eval-retrieval`.
6. Inspect low-scoring questions through `/query/debug`.
7. Compare vector, hybrid, and hybrid-plus-reranker strategies.
8. Record the metric table and any caveats in release notes.

## Current Limitations

- The bundled dataset is synthetic and should not be treated as a real production benchmark.
- The current metric implementation assumes one expected document/page target per question.
- Answer correctness is represented in the dataset through expected answers, aliases, and required terms, but the current automated CLI focuses on retrieval metrics.
- Evaluation depends on prediction files being generated consistently by the retrieval pipeline under test.
