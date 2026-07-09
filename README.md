<p align="center">
  <img src="assets/logo.png" width="80" alt="CodeSense">
</p>

<h1 align="center">CodeSense</h1>

<p align="center">
  <b>AI-powered code intelligence platform that understands GitHub repositories.</b>
</p>

<p align="center">
  <a href="https://code-sense.pages.dev">Live Demo</a> ·
  <a href="https://github.com/MohdSaadMa07/Code-Sense">GitHub</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react" alt="React">
  <img src="https://img.shields.io/badge/FAISS-Vector_Search-FF6F00" alt="FAISS">
  <img src="https://img.shields.io/badge/RAG-Groq_LLM-1DA1F2" alt="RAG">
  <img src="https://img.shields.io/badge/ONNX-BGE_384dim-005FFF" alt="ONNX">
  <img src="https://img.shields.io/badge/tree--sitter-20%2B_Languages-4EC820" alt="tree-sitter">
  <img src="https://img.shields.io/badge/Cloudflare_Pages-Deployed-F38020?logo=cloudflare" alt="Cloudflare">
  <img src="https://img.shields.io/badge/Render-Deployed-46E3B7?logo=render" alt="Render">
</p>

---

Connect any GitHub repository and instantly get:

- 🔍 **Semantic search** across your entire codebase
- 🏗️ **Automatic architecture diagrams** generated from code structure
- 💬 **AI-powered codebase Q&A** grounded in your actual source
- 🌳 **Symbol-level code exploration** across 20+ languages

Built with FastAPI, React, FAISS, BM25, ONNX Runtime, and Groq RAG.

## Why CodeSense?

Modern codebases are difficult to understand because:

- Documentation becomes outdated the moment it's written
- Large repositories require hours of manual exploration
- Onboarding into unfamiliar systems is slow and painful
- Finding the right code by keyword search misses semantic context

CodeSense solves this by creating an **AI intelligence layer** over repositories:

- **Hybrid retrieval** (semantic + lexical) finds code by meaning, not just keywords
- **AST-based parsing** understands code structure at the symbol level
- **RAG-based reasoning** answers questions using actual source code as context
- **Automated architecture discovery** reverse-engineers system diagrams from imports and routes

## Screenshots

### Repository Analysis

![Dashboard](assets/dashboard.png)

### AI Codebase Chat

![Chat](assets/chat.png)

## Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&style=for-the-badge" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&style=for-the-badge" alt="React">
  <img src="https://img.shields.io/badge/FAISS-Vector_Search-FF6F00?style=for-the-badge" alt="FAISS">
  <img src="https://img.shields.io/badge/BM25-Lexical_Search-4EC820?style=for-the-badge" alt="BM25">
  <img src="https://img.shields.io/badge/Groq-LLM_RAG-1DA1F2?style=for-the-badge" alt="Groq">
  <img src="https://img.shields.io/badge/ONNX-BGE_Embeddings-005FFF?style=for-the-badge" alt="ONNX">
  <img src="https://img.shields.io/badge/tree--sitter-20%2B_Languages-4EC820?style=for-the-badge" alt="tree-sitter">
</p>

### Backend

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI (Python 3.12) |
| Database | SQLAlchemy + SQLite / PostgreSQL |
| Auth | Google OAuth 2.0 + JWT (HS256) |
| LLM | Groq — `openai/gpt-oss-120b` |
| Embeddings | Jina AI v3 (1024-dim) or BGE ONNX (384-dim) |
| Vector Search | FAISS `IndexFlatIP` |
| Lexical Search | BM25+ (k1=1.2, b=0.75) |
| Fusion | Reciprocal Rank Fusion (k=60) |
| Code Parsing | tree-sitter (20+ lang) + Python `ast` |
| Chunking | AST-aware, chunk size 3000, overlap 50 |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | React 19 |
| Markdown | react-markdown 10 + remark-gfm 4 |
| Diagrams | Mermaid.js 10 |
| Auth | Google Identity Services |
| Styling | Custom CSS (dark cyber/neon theme) |
| Hosting | Cloudflare Pages |

## Features

- **Semantic Search** — Hybrid FAISS + BM25 retrieval with Reciprocal Rank Fusion, re-ranked by parse quality and query intent. Search your entire repo by meaning.
- **Architecture Generation** — Scans route definitions, classifies endpoints into 22 functional domains, detects layers (frontend/backend), identifies tech stack, builds dependency graphs, and renders Mermaid.js diagrams.
- **AI Q&A** — Retrieval-Augmented Generation pipeline using Groq LLM. Retrieved code chunks are injected as context for grounded answers with confidence scoring.
- **Multi-Language Parsing** — Tree-sitter AST extraction for Python, JavaScript, TypeScript, Rust, Go, Java, Ruby, PHP, C, C++, and more. Python files also get built-in `ast` module analysis for symbol boundaries.
- **Smart Indexing** — Deterministic chunk IDs (SHA1), noise filtering, parse quality metadata, and per-repo thread-safe ingestion with atomic saves.

## Performance

| Metric | Value |
|---|---:|
| Supported languages | 20+ |
| Embedding dimensions | 384 / 1024 |
| Maximum indexed files per repo | 500 |
| Retrieval methods | FAISS + BM25 + RRF |
| RRF fusion parameter | k=60 |
| Cache size (in-memory repos) | 5 (LRU) |
| Index persistence | Disk (atomic save) |

## Architecture Overview

```
Frontend (React 19 · Cloudflare Pages)
        │
        ▼ HTTP/JSON
Backend (FastAPI · Render)
        │
   ┌────┴────┐
   │         │
 FAISS     BM25     Groq LLM
Index    Index      (RAG)
```

Deployment: FastAPI on Render.com, React SPA on Cloudflare Pages.

Full architecture, ingestion pipeline, and RAG details → [docs/architecture.md](docs/architecture.md)

## Documentation

- [Architecture & Pipelines](docs/architecture.md) — Full system architecture, ingestion flow, RAG flow, deployment topology
- [Retrieval System](docs/retrieval.md) — Embedding strategies, hybrid search pipeline, re-ranking, confidence scoring
- [API Reference](docs/api.md) — Complete endpoint documentation with request/response examples

## Directory Structure

```
code-app/
├── code-app/
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint
│   │   ├── database.py             # SQLAlchemy setup
│   │   ├── deps.py                 # JWT dependencies
│   │   ├── models.py               # ORM: User, Conversation, Message
│   │   ├── routes/                 # API endpoints (8 modules)
│   │   ├── services/               # Business logic
│   │   │   ├── retrieval/          # FAISS, BM25, Manager, Cache
│   │   │   ├── ast_chunker.py      # Python AST chunking
│   │   │   ├── tree_sitter_chunker.py  # Multi-lang chunking
│   │   │   ├── github_loader.py    # GitHub API fetcher
│   │   │   ├── gpt_rag.py          # RAG pipeline
│   │   │   ├── onnx_embeddings.py  # Local BGE ONNX
│   │   │   ├── remote_embeddings.py # Jina API
│   │   │   └── storage.py          # Ingestion pipeline
│   │   └── data/                   # SQLite (gitignored)
│   ├── requirements.txt
│   └── vectorstore/                # FAISS/BM25 indices
├── frontend/
│   ├── src/
│   │   ├── App.js                  # Main component
│   │   ├── App.css                 # Full stylesheet
│   │   └── AuthContext.js          # Google OAuth
│   └── package.json
├── docs/                           # Detailed documentation
│   ├── architecture.md
│   ├── retrieval.md
│   └── api.md
└── README.md
```

## Roadmap

- [x] Hybrid semantic search (FAISS + BM25 + RRF)
- [x] Multi-language code parsing (20+ languages)
- [x] AI codebase Q&A (RAG with Groq)
- [x] Automatic architecture diagram generation
- [x] Google OAuth + JWT authentication
- [x] Conversation history persistence
- [ ] Incremental repository updates (re-index without full re-ingest)
- [ ] GitHub App integration (auto-index on push)
- [ ] Multi-user workspace support
- [ ] VS Code extension
- [ ] Self-hosted LLM support (Ollama)

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for LLM queries |
| `JWT_SECRET` | Yes | Secret for JWT signing (HS256) |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `GITHUB_TOKEN` | Recommended | GitHub API token (higher rate limits) |
| `JINA_API_KEY` | Optional | Jina AI embeddings (falls back to local ONNX) |
| `DATABASE_URL` | Optional | PostgreSQL connection string (default: SQLite) |

### Local Development

```bash
# Backend
cd code-app
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm start
```

### Production Deployment

| Platform | Service | Details |
|----------|---------|---------|
| **Render.com** | FastAPI backend | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Cloudflare Pages** | React SPA | `npm run build`, output `build/`, `_redirects` for SPA routing |

## Security

- JWT tokens expire after 30 days
- Google OAuth token validation via Google's tokeninfo endpoint with audience verification
- CORS restricted to `localhost:3000` and `*.code-sense.pages.dev`
- Per-repository thread locks prevent concurrent index corruption
- Atomic index saves (write to temp, rename on success)
- `.env` files are gitignored — never commit secrets
