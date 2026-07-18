# Demo Video Guide

This guide prepares the Day 55 project demonstration video. The target length is 2-3 minutes and the flow uses only synthetic demo data committed in `docs/demo-data/`.

## Objective

Show that the project is a complete enterprise RAG application, not only backend APIs:

- authentication works
- knowledge bases can be created
- documents can be uploaded and indexed
- chat answers are grounded in uploaded documents
- source citations are visible
- follow-up questions use conversation context
- retrieval internals and evaluation results can be inspected
- CI, Docker, and docs make the project reproducible

## Prerequisites

Start the app before recording:

```bash
make docker-up
```

Open these pages in browser tabs:

```text
Frontend: http://localhost:5173
Backend Swagger: http://localhost:8000/docs
README preview on GitHub or local repository page
```

If the frontend dev server is not running, start it separately:

```bash
cd frontend
pnpm dev
```

Demo data:

```text
docs/demo-data/travel_policy_demo.md
docs/demo-data/security_handbook_demo.md
docs/demo-data/engineering_workflow_demo.md
docs/demo-data/support_sla_demo.md
docs/demo-data/report_workflow_demo.md
```

Suggested demo account:

```text
Email: demo.user@example.com
Username: demo_user
Password: DemoPassword123
```

If the account already exists, use the login page instead of registration.

## Video Outline

Target runtime: 150 seconds.

| Time | Scene | Action | Narration |
| ---: | --- | --- | --- |
| 0:00-0:10 | Project overview | Show README title and screenshot section. | "This is an enterprise RAG knowledge base with FastAPI, React, PostgreSQL pgvector, hybrid retrieval, citations, Docker, and CI." |
| 0:10-0:25 | Login | Open frontend and sign in or register. | "The app starts with JWT authentication and protected frontend routes." |
| 0:25-0:45 | Create knowledge base | Create `Enterprise Policy Demo`. | "Each user can create private knowledge bases that isolate documents and conversations." |
| 0:45-1:05 | Upload document | Upload `travel_policy_demo.md`. | "The upload flow validates file type, stores the file, parses text, chunks content, and generates embeddings." |
| 1:05-1:15 | Wait for indexing | Show document status and chunk count. | "When processing completes, the document is ready for retrieval." |
| 1:15-1:40 | Ask question | Ask: `What is the daily meal allowance for approved business travel?` | "The chat endpoint runs query rewriting, hybrid retrieval, reranking, and grounded answer generation." |
| 1:40-1:55 | Citation display | Open source citation. | "The answer includes source citations with document name, page, chunk ID, original text, and score." |
| 1:55-2:10 | Follow-up | Ask: `What documentation is required for hotel reimbursement?` | "Conversation history is persisted and follow-up questions can use prior context." |
| 2:10-2:30 | Retrieval debug | Open Swagger `/query/debug`, show candidate scores. | "The debug endpoint exposes vector score, keyword score, RRF score, rerank score, and final rank." |
| 2:30-2:45 | Evaluation results | Show README evaluation results or `evaluations/README.md`. | "The repo includes a labelled RAG dataset and reproducible retrieval metrics for vector, hybrid, and reranked strategies." |
| 2:45-3:00 | Close | Show GitHub Actions and docs links. | "The project is packaged with Docker, CI, architecture docs, API docs, deployment docs, security notes, demo data, and release materials." |

## Exact Demo Flow

### 1. Start and open the app

Commands:

```bash
make docker-up
cd frontend
pnpm dev
```

Open:

```text
http://localhost:5173
```

### 2. Register or log in

Use the suggested demo account. If registration returns a duplicate account error, switch to login.

### 3. Create knowledge base

Create:

```text
Name: Enterprise Policy Demo
Description: Synthetic policy documents for the RAG demo.
Visibility: private
```

### 4. Upload demo documents

Start with:

```text
docs/demo-data/travel_policy_demo.md
```

Optional additional uploads:

```text
docs/demo-data/security_handbook_demo.md
docs/demo-data/engineering_workflow_demo.md
docs/demo-data/support_sla_demo.md
docs/demo-data/report_workflow_demo.md
```

Wait until status shows `completed` and chunk count is greater than zero.

### 5. Ask first question

Question:

```text
What is the daily meal allowance for approved business travel?
```

Expected answer should mention:

```text
GBP 40 per day
```

### 6. View source citation

Open the citation card or detail modal. Highlight:

- document name
- page number
- chunk ID
- original text
- similarity or rerank score

### v2.0 report workflow extension

For a longer v2.0 demo, use `docs/demo-data/report_workflow_demo.md` after the baseline RAG flow.

Suggested sequence:

1. Create a workspace from a template with analysis tasks and report sections.
2. Upload `report_workflow_demo.md`.
3. Run the template analysis tasks.
4. Approve one result and reviewer-edit another result.
5. Reject or leave one result in `needs_review`.
6. Generate draft report sections from the approved and edited results.
7. Try to reference the rejected or unreviewed result and confirm the API blocks it.
8. Reorder sections and open the Markdown report preview.

Narration:

```text
The v2.0 workflow adds human review before formal report generation. Only approved or
reviewer-edited analysis results can become report section sources, so rejected and unreviewed AI
outputs are blocked from the final report preview.
```

### 7. Ask follow-up question

Question:

```text
What documentation is required for hotel reimbursement?
```

Expected answer should mention:

```text
itemized hotel receipt and proof of payment
```

### 8. Show retrieval debug

Open Swagger:

```text
http://localhost:8000/docs
```

Use:

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/query/debug
```

Use the bearer token from the browser local storage or log in through Swagger if needed.

Request body:

```json
{
  "question": "What is the daily meal allowance for approved business travel?",
  "history": [],
  "filters": {
    "document_ids": [],
    "file_types": ["md"],
    "departments": [],
    "permissions": []
  }
}
```

Highlight candidate fields:

- `vector_score`
- `keyword_score`
- `rrf_score`
- `rerank_score`
- `final_rank`

### 9. Show evaluation results

Show `README.md` or `evaluations/README.md` where Day 54 results are documented.

Reproduction command:

```bash
.venv/bin/python scripts/run_retrieval_evaluation.py \
  --predictions evaluations/retrieval_predictions.jsonl \
  --json-output evaluations/retrieval_metrics.json
```

Metrics to mention:

| Strategy | Hit Rate@1 | MRR@1 | nDCG@1 |
| --- | ---: | ---: | ---: |
| vector | 0.750 | 0.750 | 0.750 |
| hybrid | 0.900 | 0.900 | 0.900 |
| hybrid_reranker | 1.000 | 1.000 | 1.000 |

## Narration Script

Use this script as a voice-over guide.

```text
This project is an enterprise RAG knowledge base built with FastAPI, React, PostgreSQL with pgvector, and Docker Compose.

I start by signing in to the React frontend. Authentication uses JWT access tokens and all workspace routes are protected.

Next I create a private knowledge base called Enterprise Policy Demo. Knowledge bases isolate documents, conversations, and permissions.

Now I upload a synthetic travel policy document. The backend validates the filename, MIME type, file size, and duplicate hash. It then parses the file, chunks the content, stores chunk metadata, and generates embeddings.

Once the document status is completed, I open chat and ask about the daily meal allowance. The backend rewrites follow-up queries when needed, runs hybrid vector and keyword retrieval, merges candidates with Reciprocal Rank Fusion, reranks final context, and generates a grounded answer.

The answer includes a source citation. The citation shows the document, page, chunk ID, original text, and score, so the user can verify where the answer came from.

I ask a follow-up question about hotel reimbursement. The conversation history is persisted, and the assistant answers with the required receipt and proof of payment.

For debugging, I open the retrieval debug endpoint in Swagger. This shows vector score, keyword score, RRF score, rerank score, and final rank for each candidate.

Finally, the repository includes reproducible evaluation assets. The synthetic prediction file compares vector, hybrid, and hybrid plus reranker strategies with Hit Rate, Recall, MRR, and nDCG. The project also includes Docker deployment, GitHub Actions CI, architecture docs, API docs, deployment docs, and security notes.
```

## Recording Checklist

Before recording:

- Docker services start cleanly.
- Frontend dev server opens.
- Demo account works.
- Demo knowledge base can be created.
- At least one demo document uploads successfully.
- Chat returns an answer with citations.
- Swagger opens.
- Evaluation result section is visible in README or `evaluations/README.md`.
- Browser zoom is set around 90-100 percent.
- No real secrets or personal data are visible.

After recording:

- Confirm runtime is 2-3 minutes.
- Confirm text is readable at 1080p.
- Confirm source citation is visible.
- Confirm evaluation metrics are visible.
- Confirm no `.env`, API key, JWT, or real data is shown clearly.

## Troubleshooting

If registration fails because the account already exists, use login.

If upload finishes but chat says no files are available, refresh the documents page and confirm chunk count is greater than zero.

If `/query/debug` returns `401`, copy a fresh bearer token from browser local storage or log in again.

If the frontend cannot reach the API, confirm `VITE_API_BASE_URL` points to `http://localhost:8000/api/v1` during development.

If port `8000` is already in use, do not run both Docker backend and `make dev` at the same time.

## Optional Video Artifact

When the final video is recorded, place it in a release asset rather than committing a large video file to git. A short link can be added to the README after the GitHub release is published.
