# Enterprise RAG Knowledge Base  
## 8-Week Development Roadmap

> Project name: **Enterprise RAG Knowledge Base**  
> Repository name: `enterprise-rag-knowledge-base`  
> Development cycle: 8 weeks  
> Main objective: Build an enterprise-grade RAG knowledge base system that can be added to a CV, demonstrated in interviews, deployed with Docker, and published as a complete GitHub project.

---

# 1. Project Overview

This project is an enterprise-oriented Retrieval-Augmented Generation system. Users can upload internal documents and ask questions based on the uploaded content.

The final system should support:

- User registration and login
- Multiple knowledge bases
- PDF, DOCX, TXT, and Markdown document uploads
- Document parsing and text chunking
- Embedding generation
- PostgreSQL + pgvector storage
- Vector search
- Full-text search
- Hybrid retrieval
- Reranking
- Multi-turn conversation
- Streaming responses
- Source citation
- Role-based access control
- Docker deployment
- Automated testing
- GitHub Actions
- Evaluation dataset and retrieval metrics

---

# 2. Recommended Technology Stack

| Module | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | Flutter or React |
| Database | PostgreSQL |
| Vector Database | pgvector |
| Cache | Redis |
| ORM | SQLAlchemy 2.0 |
| Migration | Alembic |
| Authentication | JWT |
| Embedding | BGE-M3, Qwen Embedding, or OpenAI Embedding |
| Reranker | BGE Reranker |
| LLM | DeepSeek, Qwen, or OpenAI |
| Testing | Pytest |
| Code Quality | Ruff, mypy |
| Deployment | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| API Documentation | Swagger / OpenAPI |

---

# 3. Final System Architecture

```text
┌────────────────────────────────────────────┐
│               Flutter / React              │
│                                            │
│ Login | Knowledge Base | Upload | Chat     │
└────────────────────┬───────────────────────┘
                     │ HTTP / SSE
                     ▼
┌────────────────────────────────────────────┐
│                  FastAPI                   │
│                                            │
│ Auth | Users | Documents | Retrieval | Chat│
└──────────┬───────────────┬─────────────────┘
           │               │
           ▼               ▼
     PostgreSQL       Document Pipeline
     Users/RBAC       Parse → Chunk → Embed
           │               │
           └───────┬───────┘
                   ▼
         PostgreSQL + pgvector
                   │
         Vector + Full-text Search
                   │
                   ▼
                Reranker
                   │
                   ▼
        DeepSeek / Qwen / OpenAI
                   │
                   ▼
        Answer + Source Citations
```

---

# 4. Version Planning

## V0.1 — Minimum Viable RAG

- Upload PDF
- Parse PDF text
- Split text into chunks
- Generate embeddings
- Store vectors in pgvector
- Retrieve relevant chunks
- Generate an answer using an LLM
- Return source references
- Test APIs using Swagger

## V0.5 — CV-Ready Version

- Support PDF, DOCX, TXT, and Markdown
- User login and JWT authentication
- Multiple knowledge bases
- Document processing status
- Multi-turn chat
- Streaming output
- Hybrid search
- Reranking
- Page-level citations
- Docker Compose deployment
- Unit tests and integration tests

## V1.0 — Enterprise Showcase Version

- RBAC permissions
- Knowledge base membership
- Incremental indexing
- Duplicate document detection
- Redis cache
- Background document processing
- Evaluation dataset
- Retrieval metrics
- Structured logging
- GitHub Actions
- Demo video
- Complete README
- GitHub Release

---

# 5. Eight-Week Development Roadmap

---

# Week 1 — Project Initialization and Backend Foundation

## Weekly Goal

Build a stable project skeleton and development environment.

## Main Tasks

- Create GitHub repository
- Initialize FastAPI project
- Configure PostgreSQL
- Configure SQLAlchemy
- Configure Alembic
- Add Docker Compose
- Add project configuration management
- Create health-check API
- Add basic test framework
- Add Ruff and mypy

## Suggested Daily Plan

### Day 1 — Repository Setup

- Create GitHub repository
- Create local project folder
- Initialize Git
- Add `.gitignore`
- Add `README.md`
- Add `LICENSE`
- Add `.env.example`
- Create initial project directory structure

Suggested commit:

```text
chore: initialize enterprise RAG project structure
```

### Day 2 — FastAPI Foundation

- Create FastAPI entrypoint
- Add API version prefix
- Add health-check endpoint
- Configure CORS
- Configure global API response format

Suggested commit:

```text
feat: add FastAPI application entrypoint and health check
```

### Day 3 — Database Integration

- Install PostgreSQL driver
- Configure SQLAlchemy async engine
- Create database session dependency
- Test database connection

Suggested commit:

```text
feat: configure PostgreSQL and SQLAlchemy
```

### Day 4 — Alembic Migration

- Initialize Alembic
- Configure database URL
- Create first migration
- Test migration upgrade and downgrade

Suggested commit:

```text
feat: add Alembic database migrations
```

### Day 5 — Docker Environment

- Create backend Dockerfile
- Create `docker-compose.yml`
- Add PostgreSQL service
- Add pgvector image
- Add backend service
- Verify one-command startup

Suggested commit:

```text
feat: add Docker Compose development environment
```

### Day 6 — Testing and Code Quality

- Add Pytest
- Add Ruff
- Add mypy
- Add health-check test
- Add project scripts

Suggested commit:

```text
test: add health check tests and code quality tools
```

### Day 7 — Weekly Review

- Clean directory structure
- Update README
- Verify Docker startup
- Verify Swagger documentation
- Create Week 1 development log

## Week 1 Acceptance Criteria

- `docker compose up --build` starts successfully
- PostgreSQL is connected
- Swagger is available
- `/health` returns success
- Pytest runs successfully
- Ruff and mypy can be executed

---

# Week 2 — Authentication and Knowledge Base Management

## Weekly Goal

Implement user authentication, JWT, knowledge base CRUD, and permission foundations.

## Database Tables

### users

```text
id
email
username
hashed_password
role
is_active
created_at
updated_at
```

### knowledge_bases

```text
id
name
description
owner_id
visibility
created_at
updated_at
```

### knowledge_base_members

```text
id
knowledge_base_id
user_id
permission
```

## Suggested Roles

- `admin`
- `owner`
- `editor`
- `viewer`

## Suggested Daily Plan

### Day 8 — User Model

- Create User model
- Create request and response schemas
- Add password hashing
- Add email uniqueness validation

Suggested commit:

```text
feat: add user model and password hashing
```

### Day 9 — Registration and Login

- Add registration endpoint
- Add login endpoint
- Generate JWT access token
- Validate user credentials

Suggested commit:

```text
feat: implement user registration and login
```

### Day 10 — Current User Dependency

- Create authenticated user dependency
- Add `/users/me`
- Add inactive user checks
- Add unauthorized error handling

Suggested commit:

```text
feat: add current user authentication dependency
```

### Day 11 — Knowledge Base Model

- Create knowledge base model
- Add owner relationship
- Add visibility field
- Create database migration

Suggested commit:

```text
feat: add knowledge base data model
```

### Day 12 — Knowledge Base CRUD

- Create knowledge base
- List user knowledge bases
- Read knowledge base details
- Update knowledge base
- Delete knowledge base

Suggested commit:

```text
feat: add knowledge base CRUD APIs
```

### Day 13 — Permission System

- Add knowledge base membership table
- Add owner, editor, and viewer permissions
- Prevent unauthorized access
- Write permission tests

Suggested commit:

```text
feat: implement role-based knowledge base access
```

### Day 14 — Weekly Review

- Test complete registration and login flow
- Test permission isolation
- Update API documentation
- Update README

## Week 2 Acceptance Criteria

- Users can register and log in
- JWT authentication works
- Users can create knowledge bases
- Users cannot access unauthorized knowledge bases
- Permission tests pass

---

# Week 3 — Document Upload, Parsing, and Chunking

## Weekly Goal

Build a complete document ingestion pipeline.

## Supported File Types

Initial version:

- PDF
- DOCX
- TXT
- Markdown

Future expansion:

- PPTX
- XLSX
- HTML

## Document Processing Status

```text
UPLOADED
PARSING
CHUNKING
EMBEDDING
COMPLETED
FAILED
```

## Suggested Daily Plan

### Day 15 — Document Model

Create document fields:

```text
id
knowledge_base_id
filename
file_type
file_size
file_hash
storage_path
status
error_message
created_by
created_at
updated_at
```

Suggested commit:

```text
feat: add document model and processing status
```

### Day 16 — File Upload API

- Add multipart upload endpoint
- Validate file extension
- Validate MIME type
- Add file-size limit
- Sanitize filename
- Save files securely

Suggested commit:

```text
feat: add secure document upload API
```

### Day 17 — PDF and TXT Parsing

- Implement PDF parser
- Implement TXT parser
- Preserve page numbers
- Handle parser exceptions

Suggested commit:

```text
feat: support PDF and TXT document parsing
```

### Day 18 — DOCX and Markdown Parsing

- Implement DOCX parser
- Implement Markdown parser
- Extract headings
- Normalize text

Suggested commit:

```text
feat: support DOCX and Markdown parsing
```

### Day 19 — Text Chunking

Implement:

- Recursive chunking
- Token-aware chunk size
- Chunk overlap
- Section-aware splitting

Recommended parameters:

```text
chunk_size: 600–800 tokens
chunk_overlap: 80–120 tokens
```

Suggested commit:

```text
feat: implement recursive and section-aware chunking
```

### Day 20 — Chunk Storage and Metadata

Store:

```text
document_id
knowledge_base_id
content
chunk_index
page_number
section_title
token_count
metadata
```

Suggested commit:

```text
feat: preserve document chunk metadata
```

### Day 21 — Duplicate Detection and Review

- Calculate SHA-256 hash
- Prevent duplicate uploads
- Add reprocessing endpoint
- Test all parsers
- Update README

Suggested commit:

```text
feat: add document deduplication and reprocessing
```

## Week 3 Acceptance Criteria

- Four file types can be uploaded
- Text is parsed correctly
- Chunks are stored in the database
- Page and section metadata are preserved
- Duplicate documents are detected
- Invalid files are rejected safely

---

# Week 4 — Embedding, pgvector, and Basic RAG

## Weekly Goal

Complete the full RAG pipeline.

## Suggested Daily Plan

### Day 22 — pgvector Setup

- Enable pgvector extension
- Add vector column to chunks
- Configure vector dimension
- Create vector index

Suggested commit:

```text
feat: add pgvector database support
```

### Day 23 — Embedding Provider Abstraction

Create a common interface:

```python
class EmbeddingProvider:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_query(self, text: str) -> list[float]:
        ...
```

Suggested implementations:

- BGE
- Qwen
- OpenAI

Suggested commit:

```text
feat: implement configurable embedding providers
```

### Day 24 — Batch Embedding

- Embed chunks in batches
- Add retry mechanism
- Track embedding status
- Record failures

Suggested commit:

```text
feat: add batch document embedding pipeline
```

### Day 25 — Vector Retrieval

- Embed user query
- Run vector similarity search
- Filter by knowledge base
- Return Top-K chunks

Suggested parameters:

```text
retrieval_top_k = 10
final_context_k = 4
```

Suggested commit:

```text
feat: implement vector similarity retrieval
```

### Day 26 — LLM Provider Abstraction

Create a common LLM interface.

Suggested providers:

- DeepSeek
- Qwen
- OpenAI

Suggested commit:

```text
feat: add configurable LLM provider abstraction
```

### Day 27 — Basic RAG Query API

Pipeline:

```text
Question
→ Query Embedding
→ Vector Search
→ Context Construction
→ LLM Generation
→ Answer
```

Suggested commit:

```text
feat: implement basic RAG question answering
```

### Day 28 — Source Citation

Return:

- Document name
- Page number
- Chunk ID
- Original text
- Similarity score

Suggested commit:

```text
feat: add source citations to RAG responses
```

## Week 4 Acceptance Criteria

- User can upload a document
- Document is embedded and indexed
- User can ask a question
- System retrieves relevant chunks
- LLM answers based on retrieved context
- Source citations are returned
- Insufficient context produces a safe response

---

# Week 5 — Hybrid Search, Reranking, and Quality Optimization

## Weekly Goal

Upgrade the project from a basic RAG demo to a CV-ready retrieval system.

## Suggested Daily Plan

### Day 29 — Full-Text Search

- Configure PostgreSQL full-text search
- Add searchable text field
- Add keyword retrieval
- Test code, policy number, and product model searches

Suggested commit:

```text
feat: add PostgreSQL full-text search
```

### Day 30 — Hybrid Retrieval

Combine:

```text
Vector Search
+
Keyword Search
```

Suggested commit:

```text
feat: implement hybrid vector and keyword retrieval
```

### Day 31 — Reciprocal Rank Fusion

Implement RRF:

```text
Vector Top 20
+
Keyword Top 20
→ RRF
→ Candidate Top 10
```

Suggested commit:

```text
feat: add reciprocal rank fusion
```

### Day 32 — Reranker Integration

Pipeline:

```text
Candidate Chunks
→ Cross-Encoder Reranker
→ Final Top 4
```

Suggested commit:

```text
feat: integrate cross-encoder reranking
```

### Day 33 — Query Rewriting

Support follow-up questions:

```text
User: What is the travel policy?
User: What about London?
```

Rewrite to a standalone query.

Suggested commit:

```text
feat: add follow-up query rewriting
```

### Day 34 — Metadata Filtering

Support filtering by:

- Knowledge base
- Document
- File type
- Date
- Department
- Permission

Suggested commit:

```text
feat: support retrieval metadata filtering
```

### Day 35 — Retrieval Debug Endpoint

Return:

- Vector score
- Keyword score
- RRF score
- Rerank score
- Final order

Suggested commit:

```text
feat: add retrieval debugging endpoint
```

## Week 5 Acceptance Criteria

- Hybrid retrieval works
- RRF combines candidate results
- Reranker changes final ranking
- Follow-up questions are rewritten
- Retrieval results can be inspected
- Permission filtering applies before generation

---

# Week 6 — Multi-Turn Chat, Streaming, and Frontend

## Weekly Goal

Build the user-facing product experience.

## Database Tables

### conversations

```text
id
user_id
knowledge_base_id
title
created_at
updated_at
```

### messages

```text
id
conversation_id
role
content
sources
token_usage
latency_ms
created_at
```

## Suggested Daily Plan

### Day 36 — Conversation Model

- Create conversation table
- Create message table
- Add conversation CRUD

Suggested commit:

```text
feat: add conversation and message persistence
```

### Day 37 — Multi-Turn Context

- Store message history
- Limit context length
- Build standalone queries
- Track conversation state

Suggested commit:

```text
feat: implement multi-turn conversation context
```

### Day 38 — Streaming API

- Implement Server-Sent Events
- Stream generated tokens
- Add cancel handling
- Handle stream exceptions

Suggested commit:

```text
feat: implement SSE streaming chat responses
```

### Day 39 — Frontend Authentication

- Create login page
- Create registration page
- Store token securely
- Add route protection

Suggested commit:

```text
feat: build frontend authentication flow
```

### Day 40 — Knowledge Base Interface

- Knowledge base list
- Create knowledge base
- Knowledge base details
- Delete and edit actions

Suggested commit:

```text
feat: build knowledge base management interface
```

### Day 41 — Document Management Interface

Display:

- Filename
- File size
- Processing status
- Chunk count
- Upload time
- Error message
- Reprocess action
- Delete action

Suggested commit:

```text
feat: build document upload and status interface
```

### Day 42 — Chat Interface

Add:

- Conversation list
- New conversation
- Streaming messages
- Copy answer
- Stop generation
- Source cards
- Open citation details

Suggested commit:

```text
feat: build streaming chat interface with citations
```

## Week 6 Acceptance Criteria

- User can log in through the frontend
- User can create knowledge bases
- User can upload and manage documents
- User can chat with documents
- Answers stream in real time
- Source citations are visible
- Conversation history is stored

---

# Week 7 — Testing, Evaluation, Logging, and Reliability

## Weekly Goal

Make the project measurable, reproducible, and reliable.

## Suggested Daily Plan

### Day 43 — Unit Tests

Create tests for:

- Chunker
- File parsers
- Authentication
- Permissions
- Prompt builder
- Retrieval
- Reranking

Suggested commit:

```text
test: add core unit tests
```

### Day 44 — Integration Tests

Test:

```text
Upload
→ Parse
→ Chunk
→ Embed
→ Retrieve
→ Generate
```

Suggested commit:

```text
test: add document ingestion integration tests
```

### Day 45 — End-to-End API Tests

Test:

```text
Register
→ Login
→ Create Knowledge Base
→ Upload Document
→ Ask Question
→ Read Sources
```

Suggested commit:

```text
test: add end-to-end RAG API tests
```

### Day 46 — Evaluation Dataset

Prepare 30–50 labelled questions.

Example:

```json
{
  "question": "What is the maximum meal allowance?",
  "expected_answer": "£40 per day",
  "expected_document": "travel_policy.pdf",
  "expected_page": 8
}
```

Suggested commit:

```text
feat: add RAG evaluation dataset
```

### Day 47 — Retrieval Metrics

Calculate:

- Hit Rate@K
- Recall@K
- MRR
- nDCG

Compare:

- Vector only
- Hybrid search
- Hybrid + reranker

Suggested commit:

```text
feat: add retrieval evaluation metrics
```

### Day 48 — Structured Logging

Record:

```text
request_id
user_id
knowledge_base_id
query
retrieved_chunk_ids
retrieval_latency
rerank_latency
llm_latency
total_latency
token_usage
status
error
```

Suggested commit:

```text
feat: add structured logging and request tracing
```

### Day 49 — Error Handling and Review

- Standardize API error responses
- Add retry logic
- Add timeout handling
- Add rate-limit handling
- Update evaluation documentation

Suggested commit:

```text
refactor: standardize API errors and reliability handling
```

## Week 7 Acceptance Criteria

- Core modules have tests
- End-to-end flow is covered
- Evaluation dataset exists
- Retrieval metrics can be reproduced
- Logs include latency and errors
- API errors have a unified format

---

# Week 8 — CI/CD, Documentation, Deployment, and GitHub Release

## Weekly Goal

Package the project as a professional GitHub portfolio project.

## Suggested Daily Plan

### Day 50 — Production Docker Setup

- Optimize backend Dockerfile
- Add frontend Dockerfile
- Add production Docker Compose
- Add Nginx if needed
- Verify clean deployment

Suggested commit:

```text
build: add production Docker deployment
```

### Day 51 — GitHub Actions

Create workflows for:

- Backend tests
- Ruff
- mypy
- Frontend tests
- Docker build

Suggested commit:

```text
ci: add automated test and build workflows
```

### Day 52 — README

Add:

- Project overview
- Key features
- Architecture
- RAG pipeline
- Technology stack
- Quick start
- Environment variables
- API guide
- Evaluation results
- Screenshots
- Limitations
- Roadmap

Suggested commit:

```text
docs: complete project README
```

### Day 53 — Documentation

Create:

```text
docs/architecture.md
docs/api.md
docs/deployment.md
docs/evaluation.md
docs/security.md
```

Suggested commit:

```text
docs: add architecture deployment and evaluation guides
```

### Day 54 — Screenshots and Demo Data

Prepare:

- Architecture diagram
- RAG pipeline diagram
- Login page
- Knowledge base page
- Upload page
- Chat page
- Citation display
- Swagger page
- GitHub Actions page
- Evaluation results

Suggested commit:

```text
docs: add screenshots and synthetic demo data
```

### Day 55 — Demo Video

Record a 2–3 minute video showing:

1. Login
2. Create knowledge base
3. Upload document
4. Wait for indexing
5. Ask a question
6. View source citation
7. Ask a follow-up question
8. Show retrieval debug page
9. Show evaluation results

Suggested commit:

```text
docs: add project demonstration materials
```

### Day 56 — V1.0 Release

- Run all tests
- Scan for secrets
- Update changelog
- Create Git tag
- Push tag
- Publish GitHub Release
- Add repository topics
- Add project to CV

Suggested commands:

```bash
git switch main
git pull origin main
git tag -a v1.0.0 -m "Enterprise RAG Knowledge Base v1.0.0"
git push origin v1.0.0
```

Suggested commit before release:

```text
chore: prepare v1.0.0 release
```

## Week 8 Acceptance Criteria

- Docker deployment works
- GitHub Actions passes
- README is complete
- Screenshots are included
- Evaluation results are documented
- Demo video is available
- V1.0.0 release is published
- Repository is ready for CV and interviews

---

# 6. Recommended Repository Structure

```text
enterprise-rag-knowledge-base/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── knowledge_bases.py
│   │   │       ├── documents.py
│   │   │       ├── retrieval.py
│   │   │       └── chat.py
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── rag/
│   │   │   ├── chunking/
│   │   │   ├── embeddings/
│   │   │   ├── loaders/
│   │   │   ├── retrieval/
│   │   │   ├── reranking/
│   │   │   ├── generation/
│   │   │   └── evaluation/
│   │   ├── workers/
│   │   └── main.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── alembic/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic.ini
│
├── frontend/
│   ├── lib/
│   ├── test/
│   ├── Dockerfile
│   └── pubspec.yaml
│
├── evaluation/
│   ├── datasets/
│   ├── results/
│   └── run_evaluation.py
│
├── sample_data/
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── deployment.md
│   ├── evaluation.md
│   ├── security.md
│   └── images/
│
├── .github/
│   ├── workflows/
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.prod.yml
├── CONTRIBUTING.md
├── LICENSE
├── SECURITY.md
├── CHANGELOG.md
└── README.md
```

---

# 7. Git Branch Strategy

Recommended:

```text
main
└── develop
    ├── feature/auth
    ├── feature/document-upload
    ├── feature/vector-retrieval
    ├── feature/hybrid-search
    ├── feature/reranker
    └── feature/streaming-chat
```

For a solo project, a simpler structure is acceptable:

```text
main
└── feature/xxx
```

Example:

```bash
git switch -c feature/document-upload
git add .
git commit -m "feat: add document upload and validation"
git push -u origin feature/document-upload
```

---

# 8. Commit Message Convention

Use Conventional Commits.

| Type | Purpose |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `test` | Tests |
| `refactor` | Code refactoring |
| `perf` | Performance improvement |
| `chore` | Maintenance |
| `ci` | CI/CD |
| `build` | Build and dependency changes |

Good examples:

```text
feat: add hybrid vector and keyword retrieval
feat: implement source citation generation
fix: prevent cross-knowledge-base retrieval
test: add document ingestion integration tests
docs: add local deployment instructions
refactor: extract embedding provider interface
perf: batch embedding requests
ci: add backend test workflow
```

Avoid:

```text
update
final version
修改代码
test
bug fixed
完成
```

---

# 9. GitHub Publication Process

## Step 1 — Initialize Locally

```bash
mkdir enterprise-rag-knowledge-base
cd enterprise-rag-knowledge-base
git init
git branch -M main
```

## Step 2 — Create Initial Files

```bash
touch README.md
touch .gitignore
touch .env.example
touch LICENSE
```

## Step 3 — First Commit

```bash
git add .
git commit -m "chore: initialize enterprise RAG project"
```

## Step 4 — Create GitHub Repository

Repository name:

```text
enterprise-rag-knowledge-base
```

Suggested description:

```text
An enterprise-grade RAG knowledge base with hybrid retrieval,
reranking, citations, RBAC, streaming responses, and Docker deployment.
```

## Step 5 — Connect Remote Repository

HTTPS:

```bash
git remote add origin https://github.com/YOUR_USERNAME/enterprise-rag-knowledge-base.git
```

SSH:

```bash
git remote add origin git@github.com:YOUR_USERNAME/enterprise-rag-knowledge-base.git
```

## Step 6 — Push Main Branch

```bash
git push -u origin main
```

---

# 10. Security Checklist

Never upload:

- `.env`
- API keys
- Database passwords
- JWT secret keys
- Private documents
- Real user data
- Large model files
- Personal access tokens

Required controls:

- File extension whitelist
- MIME validation
- File-size limit
- Filename sanitization
- Permission filtering
- Knowledge base data isolation
- Secret management
- Safe error messages
- Rate limiting
- Upload directory protection

---

# 11. Final README Structure

```markdown
# Enterprise RAG Knowledge Base

## Overview

## Key Features

## System Architecture

## RAG Pipeline

## Technology Stack

## Project Structure

## Quick Start

## Environment Variables

## API Documentation

## Evaluation Results

## Screenshots

## Security Considerations

## Known Limitations

## Roadmap

## License
```

---

# 12. Final GitHub Checklist

## Code

- [ ] Repository can be cloned
- [ ] Docker Compose starts successfully
- [ ] Database migration works
- [ ] API documentation opens
- [ ] Tests pass
- [ ] No hard-coded absolute paths
- [ ] No unused code
- [ ] No private configuration files

## Security

- [ ] `.env` is not committed
- [ ] No API key is exposed
- [ ] No real user data is included
- [ ] File upload restrictions exist
- [ ] Permission filtering works
- [ ] JWT secret is configurable

## Documentation

- [ ] README is complete
- [ ] Architecture diagram exists
- [ ] RAG pipeline diagram exists
- [ ] Installation steps are clear
- [ ] Evaluation method is documented
- [ ] Screenshots are included
- [ ] Known limitations are included
- [ ] License is included

## Presentation

- [ ] Demo video exists
- [ ] GitHub Actions passes
- [ ] Commit history is clear
- [ ] V1.0.0 Release exists
- [ ] Repository topics are configured
- [ ] Project description is complete

---

# 13. Recommended GitHub Topics

```text
rag
llm
fastapi
pgvector
postgresql
hybrid-search
reranking
knowledge-base
deepseek
qwen
flutter
docker
artificial-intelligence
```

---

# 14. CV Description Template

## Enterprise RAG Knowledge Base System

- Designed and developed an enterprise knowledge base platform using FastAPI, PostgreSQL, and pgvector, supporting PDF, DOCX, TXT, and Markdown ingestion.
- Implemented document parsing, recursive chunking, embedding generation, vector indexing, and metadata-aware retrieval.
- Built hybrid search using vector retrieval and PostgreSQL full-text search, followed by cross-encoder reranking.
- Integrated configurable LLM providers including DeepSeek, Qwen, and OpenAI, supporting multi-turn conversations, query rewriting, streaming responses, and source citations.
- Designed JWT authentication, RBAC permissions, and multi-knowledge-base data isolation.
- Containerized the system using Docker Compose and implemented automated testing and code quality checks through GitHub Actions.
- Evaluated retrieval quality using a labelled question set and metrics including Hit Rate@K, MRR, Recall@K, and nDCG.

Only add numerical improvements after running a reproducible evaluation.

Example:

```text
Improved Hit Rate@5 from 72% to 88% by combining hybrid retrieval
with cross-encoder reranking on a 50-question labelled evaluation set.
```

---

# 15. Development Priority

Follow this order:

```text
FastAPI and Database
        ↓
Authentication and Knowledge Bases
        ↓
Document Parsing and Chunking
        ↓
Embedding and pgvector
        ↓
Basic RAG
        ↓
Source Citations
        ↓
Hybrid Retrieval
        ↓
Reranking
        ↓
Multi-Turn Chat
        ↓
Streaming Responses
        ↓
Frontend
        ↓
Testing and Evaluation
        ↓
Docker and GitHub Actions
        ↓
README, Demo Video, and Release
```

Do not add Agent, MCP, or multi-agent workflows before the RAG retrieval quality and project engineering foundation are stable.

---

# 16. Final Deliverables

At the end of the eight weeks, the repository should contain:

- Complete backend source code
- Complete frontend source code
- Docker Compose deployment
- Database migrations
- Unit, integration, and end-to-end tests
- RAG evaluation dataset
- Retrieval evaluation results
- Architecture documentation
- API documentation
- Deployment documentation
- Security documentation
- Synthetic demo documents
- Screenshots
- Demo video
- GitHub Actions workflows
- V1.0.0 Release
- CV-ready project description

