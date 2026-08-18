# Retrieval System

## Embedding Strategy

CodeSense supports two embedding backends, selected at import time in `faiss_index.py`:

### Voyage AI (Remote — Default)

- **Model**: `voyage-code-3` (1024-dimensional)
- **Used when**: `VOYAGE_API_KEY` environment variable is set
- **Input types**: `document` for indexing, `query` for search
- **Retry logic**: 6 attempts with exponential backoff (2s → 4s → 8s → 16s → 30s)
- **Rate-limit handling**: automatic retry on `RateLimitError` (30s wait per the rate window)
- **Batch size**: requests are sub-batched to 8 texts to fit the free-tier token budget
- **Code**: `app/services/remote_embeddings.py`

### BGE ONNX (Local — Fallback)

- **Model**: `BAAI/bge-small-en-v1.5` (384-dimensional)
- **Used when**: `VOYAGE_API_KEY` is not set
- Downloaded from Hugging Face on first startup
- Optimized: sequential execution, single-thread CPU, aggressive garbage collection
- Lazy-loaded in a background thread to avoid blocking startup
- **Code**: `app/services/onnx_embeddings.py`

## Hybrid Retrieval Pipeline

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

## Retrieval Components

### FAISS Vector Index (`faiss_index.py`)

- `IndexFlatIP` — inner product index (cosine sim with normalized vectors)
- Dynamically uses 1024-dim (Voyage) or 384-dim (BGE) based on embedding strategy
- On load, rebuilds the index when the stored dimension no longer matches the active embedding dimension
- Persisted to disk via pickle + FAISS write_index

### BM25+ Lexical (`bm25.py`)

- Custom implementation with smoothing (BM25+ variant)
- `k1 = 1.2`, `b = 0.75`
- Tokenization regex: `[a-zA-Z_][a-zA-Z0-9_]*`
- Persisted to disk via pickle

### Hybrid Fusion (`hybrid.py`)

- Reciprocal Rank Fusion with `k_param = 60`
- Retrieves `max(k * 2, 60)` from each sub-retriever before fusion
- Shared `_Docstore` between FAISS and BM25 for consistent document IDs
- Atomic save via temp directory + rename

### Retrieval Manager (`manager.py`)

- Singleton `RetrievalManager` managing per-repository retriever lifecycle
- LRU cache (max 5 repos) via `OrderedDict`
- Per-repo `threading.Lock` for concurrent ingest safety
- Lazy loading from disk on first access

## Re-ranking (`query.py`)

After hybrid retrieval, the system re-ranks results:

1. **Parse quality boost**: High-quality AST chunks score higher than fallback
2. **Query intent detection**: Code-related queries boost code documents
3. **Column/table intent**: Special handling for database schema queries
4. **Confidence scoring**: Label (high/medium/low) + score based on best score, average score, and gap between top results
