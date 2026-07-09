# Architecture

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

## Deployment Architecture

```
         Users
           │
           ▼
   Cloudflare Pages
      React SPA
           │
           │ HTTPS
           ▼
    FastAPI (Render)
           │
      ┌────┴────┐
      │         │
   FAISS    SQLite     Groq
   Index   Database    LLM API
   (disk)             (external)
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
