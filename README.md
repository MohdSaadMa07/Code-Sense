# CodeSense

Semantic code search engine with AI-powered architecture analysis and conversational Q&A for any GitHub repository.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React 19)                   │
│  Cloudflare Pages · Google OAuth · Mermaid.js Diagrams  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (JSON)
┌──────────────────────▼──────────────────────────────────┐
│                FastAPI Backend (Python 3.12)             │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │                   Routes                          │   │
│  │  /auth  /ingest  /query  /gpt  /github           │   │
│  │  /symbols  /architecture  /conversations         │   │
│  └───────────┬──────────────────────────────────────┘   │
│              │                                          │
│  ┌───────────▼──────────────────────────────────────┐   │
│  │               Services                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │   │
│  │  │ ONNX/BGE │ │ Jina v3  │ │  Groq GPT-OSS    │  │   │
│  │  │Embeddings│ │Embeddings│ │  120B (RAG)      │  │   │
│  │  │(384-dim) │ │(1024-dim)│ │                  │  │   │
│  │  └────┬─────┘ └────┬─────┘ └──────────────────┘  │   │
│  │       │            │                              │   │
│  │  ┌────▼────────────▼──────────────────────────┐   │   │
│  │  │          Retrieval Layer                    │   │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │   │   │
│  │  │  │  FAISS   │  │   BM25   │  │   RRF    │  │   │   │
│  │  │  │(Vector)  │  │(Lexical) │  │  Fusion  │  │   │   │
│  │  │  └──────────┘  └──────────┘  └──────────┘  │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  │                                                         │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │  SQLite / PostgreSQL (Users, Conversations)  │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI (Python 3.12) |
| Database | SQLAlchemy + SQLite (dev) / PostgreSQL (prod) |
| Auth | Google OAuth 2.0 + JWT (python-jose, HS256) |
| LLM | Groq API — `openai/gpt-oss-120b` |
| Embeddings (remote) | Jina AI — `jina-embeddings-v3` (1024-dim) |
| Embeddings (local) | ONNX Runtime — `BAAI/bge-small-en-v1.5` (384-dim) |
| Vector Search | FAISS `IndexFlatIP` (inner product) |
| Lexical Search | BM25+ (custom impl, k1=1.2, b=0.75) |
| Fusion | Reciprocal Rank Fusion (RRF, k=60) |
| Code Parsing | tree-sitter (20+ languages) + Python `ast` |
| ASGI Server | uvicorn |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 19 |
| Markdown | react-markdown 10 + remark-gfm 4 |
| Diagrams | Mermaid.js 10 (loaded from CDN) |
| Auth | Google Identity Services (GSI) |
| Styling | Custom CSS (cyber/neon theme) |
| Hosting | Cloudflare Pages |

## Features

### Semantic Search
Hybrid retrieval combining dense vector search (FAISS inner product) and lexical search (BM25+) fused via Reciprocal Rank Fusion. Results are re-ranked with a scoring function that accounts for parse quality and query intent (code vs. natural language).

### Architecture Generation
Scans the ingested docstore for route definitions across multiple frameworks (FastAPI, Express, Django, React Router, etc.), classifies endpoints into 22 functional domains, detects frontend/backend layers, identifies the tech stack from config files, builds dependency edges via import analysis, and generates Mermaid.js diagrams.

### AI Q&A
Retrieval-Augmented Generation (RAG) pipeline: hybrid search retrieves relevant code chunks, which are injected into a strict prompt for the Groq-hosted LLM. Answers include confidence scoring based on lexical grounding (overlap with retrieved context). Full conversation history is persisted per user.

### Multi-Language Parsing
Code chunking via tree-sitter for 20+ languages (Python, JavaScript, TypeScript, JSX, Rust, Go, Java, Ruby, PHP, C, C++, etc.) with recursive AST node extraction. Python files additionally use the built-in `ast` module for symbol extraction (class/function boundaries).

### Smart Indexing
Deterministic chunk IDs via SHA1 of (path + content). Noise filtering drops content under 25 chars, markdown images/badges, lock files, and minified assets. Parse quality metadata (high/medium/low) is attached per chunk for downstream scoring.

## Directory Structure

```
code-app/
├── code-app/
│   ├── app/
│   │   ├── main.py                    # FastAPI entrypoint, CORS, startup
│   │   ├── database.py                # SQLAlchemy engine (SQLite/Postgres)
│   │   ├── deps.py                    # JWT auth dependencies
│   │   ├── models.py                  # ORM: User, Conversation, Message
│   │   ├── routes/
│   │   │   ├── auth.py                # Google OAuth
│   │   │   ├── conversations.py       # Conversation CRUD
│   │   │   ├── github.py              # Repo ingestion
│   │   │   ├── ingest.py              # File upload ingestion
│   │   │   ├── query.py               # Semantic search
│   │   │   ├── gpt.py                 # RAG Q&A
│   │   │   ├── tree.py                # Symbol tree
│   │   │   └── architecture.py        # Architecture diagrams
│   │   ├── services/
│   │   │   ├── ast_chunker.py         # Python AST chunker
│   │   │   ├── tree_sitter_chunker.py # Multi-lang tree-sitter chunker
│   │   │   ├── github_loader.py       # GitHub API file fetcher
│   │   │   ├── gpt_rag.py             # RAG pipeline (Groq)
│   │   │   ├── onnx_embeddings.py     # Local BGE ONNX embeddings
│   │   │   ├── remote_embeddings.py   # Jina API embeddings
│   │   │   ├── storage.py             # Ingestion pipeline
│   │   │   └── retrieval/
│   │   │       ├── manager.py         # Singleton retrieval manager
│   │   │       ├── hybrid.py          # Hybrid BM25 + FAISS
│   │   │       ├── faiss_index.py     # FAISS vector index
│   │   │       ├── bm25.py            # BM25 lexical retriever
│   │   │       ├── cache.py           # LRU cache (max 5 repos)
│   │   │       └── locks.py           # Per-repo thread locks
│   │   └── data/                      # SQLite database (gitignored)
│   ├── requirements.txt
│   └── vectorstore/                   # FAISS/BM25 on-disk indices
└── frontend/
    ├── public/
    │   ├── index.html
    │   └── _redirects                 # Cloudflare SPA rule
    ├── src/
    │   ├── App.js                     # Main React component
    │   ├── App.css                    # Full application styles
    │   ├── AuthContext.js             # Google OAuth context
    │   └── index.js                   # Entry point
    └── package.json
```

## API Reference

### Authentication
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/auth/google` | Google OAuth sign-in | Public |
| GET | `/auth/me` | Current user profile | JWT |

### Code Ingestion
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/github/ingest` | Ingest a GitHub repo | Public |
| POST | `/ingest/` | Upload a single file | Public |

### Retrieval
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/query/` | Hybrid semantic search | Public |
| POST | `/gpt/query` | RAG-powered Q&A | Optional JWT |
| GET | `/symbols/` | Extracted code symbols | Public |

### Architecture
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/architecture/generate` | Generate Mermaid diagram | Public |
| POST | `/architecture/clear` | Clear vector store | Public |
| POST | `/architecture/debug` | Index debug stats | Public |

### Conversations
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/conversations/` | List conversations | JWT |
| POST | `/conversations/` | Create conversation | JWT |
| GET | `/conversations/{id}` | Get conversation + messages | JWT |
| DELETE | `/conversations/{id}` | Delete conversation | JWT |
| POST | `/conversations/{id}/messages` | Add Q&A pair | JWT |

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns 200 when model ready, 503 otherwise |

## Embedding Strategy

CodeSense supports two embedding backends, selected at import time:

### Jina AI (Remote — Default)
- Model: `jina-embeddings-v3` (1024-dimensional)
- Used when `JINA_API_KEY` is set
- Retry logic: 5 attempts with exponential backoff (2s → 4s → 8s → 16s → 32s)
- Rate-limit handling: automatic retry on HTTP 429

### BGE ONNX (Local — Fallback)
- Model: `BAAI/bge-small-en-v1.5` (384-dimensional)
- Used when `JINA_API_KEY` is not set
- Downloaded from Hugging Face on first startup
- Optimized: sequential execution, single-thread CPU, aggressive GC
- Lazy-loaded in a background thread to avoid blocking startup

## Retrieval Pipeline

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│         FAISS IndexFlatIP           │
│  (dense vector, inner product)      │
│  Returns k*2 candidates             │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│          BM25+ (Lexical)            │
│  tokenizes via [a-zA-Z_][a-zA-Z0-9_]* │
│  k1=1.2, b=0.75                     │
│  Returns k*2 candidates             │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Reciprocal Rank Fusion (RRF)      │
│   score = 1 / (k + rank)  k=60      │
│   Merges & deduplicates             │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Re-ranking                  │
│  Adjusts scores by parse quality    │
│  (high/medium/low)                  │
│  Boosts code docs for code queries  │
│  Returns top_k results              │
└─────────────────────────────────────┘
```

## Ingestion Pipeline

```
GitHub URL
    │
    ▼
┌────────────────────────────────────────┐
│  GitHub Contents API                   │
│  Recursive tree walk (max 500 files)   │
│  Parallel download (3 threads)         │
│  Filter: 17 extensions, skip lock/min  │
└────────────────┬───────────────────────┘
                 │
┌────────────────▼───────────────────────┐
│  Micro-batch processing (batch=5)      │
│  1.5s delay between batches            │
└────────────────┬───────────────────────┘
                 │
┌────────────────▼───────────────────────┐
│  Chunking                              │
│  ├── Python files: AST-based parsing   │
│  ├── Other code: tree-sitter AST       │
│  └── Unsupported: character split      │
│  Chunk size: 3000, overlap: 50         │
└────────────────┬───────────────────────┘
                 │
┌────────────────▼───────────────────────┐
│  Filtering & Enrichment                │
│  ├── Drop noise (<25 chars, images)    │
│  ├── Deduplicate by SHA1(content+path) │
│  ├── Attach parse quality metadata     │
│  └── Chunk ID: sha1(path+content)      │
└────────────────┬───────────────────────┘
                 │
┌────────────────▼───────────────────────┐
│  Embedding & Indexing (batch=10)       │
│  ├── Generate embeddings (Jina/BGE)    │
│  ├── Add to FAISS index                │
│  └── Index into BM25 corpus            │
│  Atomic save via temp dir + rename     │
└────────────────────────────────────────┘
```

## RAG Pipeline

```
User Question
    │
    ▼
┌──────────────────────────────────────┐
│  Hybrid Retrieval (top_k=3, k*=4)    │
│  FAISS + BM25 + RRF fusion          │
└────────────────┬─────────────────────┘
                 │
┌────────────────▼─────────────────────┐
│  Context Assembly                    │
│  ┌─────────────────────────────────┐ │
│  │ [FILE]: path/to/file.py        │ │
│  │ ```python                      │ │
│  │ def function_name(...):        │ │
│  │     ...                        │ │
│  │ ```                            │ │
│  └─────────────────────────────────┘ │
└────────────────┬─────────────────────┘
                 │
┌────────────────▼─────────────────────┐
│  LLM Query (Groq GPT-OSS-120B)       │
│  Prompt: "Answer from context only.  │
│  If unsure, say 'I don't know'."     │
│  max_tokens: 2048                    │
└────────────────┬─────────────────────┘
                 │
┌────────────────▼─────────────────────┐
│  Confidence Scoring                  │
│  Lexical grounding check:            │
│  ≥2 long words from answer found     │
│  in context → high confidence        │
│  Otherwise → medium/low              │
└──────────────────────────────────────┘
```

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for LLM queries |
| `JWT_SECRET` | Yes | Secret for JWT signing (HS256) |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `GITHUB_TOKEN` | Recommended | GitHub API token (increases rate limit) |
| `JINA_API_KEY` | Optional | Jina AI embeddings (falls back to local ONNX if unset) |
| `DATABASE_URL` | Optional | PostgreSQL connection string (uses SQLite by default) |

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

The app is deployed on Render.com (backend) and Cloudflare Pages (frontend).

**Render.com** (FastAPI):
- Service type: Web Service
- Build command: `pip install -r code-app/requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Cloudflare Pages** (React SPA):
- Build command: `npm run build`
- Output directory: `build`
- `_redirects` file: `/* /index.html 200` (SPA routing)

## Security

- JWT tokens expire after 30 days
- Google OAuth token validation via Google's tokeninfo endpoint with audience claim verification
- CORS restricted to `localhost:3000` and `*.code-sense.pages.dev`
- `.env` files are gitignored (do not commit secrets)
- Per-repository thread locks prevent concurrent index corruption
- Atomic index saves (write to temp directory, rename on success)
