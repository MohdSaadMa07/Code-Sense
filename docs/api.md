# API Reference

Base URL: `http://127.0.0.1:8000` (local) or `https://code-sense-1.onrender.com` (production)

All endpoints return JSON. Authentication uses `Authorization: Bearer <jwt_token>` header.

## Authentication

### POST `/auth/google`

Google OAuth sign-in.

**Request body:**
```json
{ "credential": "<google_id_token>" }
```

**Response:**
```json
{
  "token": "jwt_token_string",
  "user": { "id": 1, "name": "...", "email": "...", "picture": "..." }
}
```

### GET `/auth/me`

Returns the current authenticated user's profile.

**Auth:** JWT required

**Response:**
```json
{ "id": 1, "name": "...", "email": "...", "picture": "..." }
```

---

## Code Ingestion

### POST `/github/ingest`

Ingest an entire GitHub repository. Fetches files, chunks, embeds, and indexes them.

**Request body:**
```json
{ "repo_url": "https://github.com/owner/repo", "max_files": 100 }
```

**Response:**
```json
{
  "repo": "owner/repo",
  "files_ingested": 85,
  "chunks_ingested": 420,
  "sample_file": "src/main.py"
}
```

### POST `/ingest/`

Upload a single file for ingestion.

**Form data:** `repository_id` (string), `file` (multipart upload)

**Response:**
```json
{ "status": "ingested", "chunks": 12 }
```

---

## Retrieval

### POST `/query/`

Hybrid semantic search over an ingested repository.

**Request body:**
```json
{ "repository_id": "owner/repo", "query": "authentication logic", "top_k": 3 }
```

**Response:**
```json
{
  "results": [
    {
      "rank": 1,
      "score": 0.89,
      "chunk": "def authenticate(...):",
      "metadata": { "path": "src/auth.py", "chunk_id": "abc123", "parse_quality": "high" }
    }
  ],
  "confidence": { "label": "high", "score": 0.85 }
}
```

### POST `/gpt/query`

RAG-powered question answering with LLM.

**Query params or JSON body:**
```json
{
  "repository_id": "owner/repo",
  "prompt": "How does the auth system work?",
  "top_k": 3,
  "include_context": true,
  "debug": false,
  "conversation_id": null
}
```

**Auth:** Optional JWT (required for conversation persistence)

**Response:**
```json
{
  "result": "The auth system uses JWT tokens...",
  "confidence": "high",
  "confidence_score": 0.92,
  "context": [{ "source": "src/auth.py", "chunk": "def authenticate(...)", "metadata": {...} }]
}
```

### GET `/symbols/`

Get all extracted code symbols organized by file.

**Query param:** `repository_id` (required)

**Response:**
```json
{
  "files": [
    { "path": "src/auth.py", "symbols": [{ "name": "authenticate", "kind": "function", "line_start": 10, "line_end": 45 }] }
  ]
}
```

---

## Architecture

### POST `/architecture/generate`

Generate a Mermaid.js architecture diagram from ingested code.

**Request body:**
```json
{ "repository_id": "owner/repo" }
```

**Response:**
```json
{
  "mermaid": "graph TD...",
  "modules_found": ["auth", "api", "database"],
  "dependencies": [["auth", "database"]],
  "layers": { "frontend": [...], "backend": [...] },
  "entry_points": ["src/main.py", "src/api/routes.py"],
  "tech": { "framework": "FastAPI", "database": "PostgreSQL", "frontend": "React" }
}
```

### POST `/architecture/clear`

Clear the vector store for a repository.

**Request body:**
```json
{ "repository_id": "owner/repo" }
```

**Response:** `{ "status": "cleared" }`

### POST `/architecture/debug`

Get debug information about the vector store state.

**Request body:**
```json
{ "repository_id": "owner/repo" }
```

**Response:**
```json
{
  "docstore_size": 420,
  "index_size": 420,
  "bm25_docs": 420,
  "faiss_index_size": 420
}
```

---

## Conversations

### GET `/conversations/`

List user's conversations (max 50, most recent first).

**Auth:** JWT required

### POST `/conversations/`

Create a new conversation.

**Auth:** JWT required

**Request body:**
```json
{ "repo_url": "https://github.com/owner/repo", "title": "New conversation" }
```

### GET `/conversations/{id}`

Get conversation with all messages.

**Auth:** JWT required

### DELETE `/conversations/{id}`

Delete a conversation and all its messages.

**Auth:** JWT required

### POST `/conversations/{id}/messages`

Add a Q&A pair to a conversation.

**Auth:** JWT required

**Request body:**
```json
{ "question": "...", "answer": "...", "context": [{ "source": "...", "chunk": "..." }] }
```

---

## Health

### GET `/health`

**Response (ready):** `{ "status": "ready" }`
**Response (loading):** 503 `{ "status": "loading" }`
