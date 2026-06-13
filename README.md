# CodeSense

RAG-powered code analysis tool. Ingest any GitHub repository, search semantically, generate architecture diagrams, and ask questions grounded in your actual codebase.

## Features

- **Connect Repo** — Fetches files from any public GitHub repo via API
- **Deep Search** — Semantic vector search using all-MiniLM-L6-v2 embeddings via FAISS
- **Ask Codebase** — LLM-powered Q&A (Groq, `gpt-oss-120b`) grounded in retrieved code context
- **Architecture** — Auto-generated Mermaid module diagram with layers, route domains, and dependency edges
- **Conversation History** — Optional Google OAuth sign-in to persist Q&A per repo

## Screenshots

<img width="1917" height="847" alt="image" src="https://github.com/user-attachments/assets/08c9a708-5319-4f2e-bfee-e58e37f85558" />

### Connect Repo
<img width="1917" height="847" alt="image" src="https://github.com/user-attachments/assets/0a189809-eb46-4c10-ae81-f64d90b4e7e0" />

Paste a GitHub URL, set max files, and ingest. Stats show repo name, files fetched, chunks generated, and a sample file path.

### Deep Search
<img width="1917" height="847" alt="image" src="https://github.com/user-attachments/assets/2f248ea7-fcd6-4e81-ba4d-4c0441b1d2ac" />

Enter a semantic query. Results display ranked chunks with similarity score, file path, and highlighted code content.

### Ask Codebase
<img width="1917" height="862" alt="image" src="https://github.com/user-attachments/assets/43b63adf-996e-45eb-8cd9-2f2ced888b54" />

Type a question against the ingested code. The answer box shows LLM response with confidence badge (high/medium/low) and expandable context sources.

### Architecture
<img width="1031" height="827" alt="image" src="https://github.com/user-attachments/assets/2fa48603-4461-401f-84f6-f296bf36f230" />

Mermaid flow diagram grouped by Frontend/Backend/External layers. Module cards show route summaries. Entry points and tech stack breakdown listed below the diagram.


## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + react-markdown |
| Backend | FastAPI (Python 3.10) |
| Vector Store | FAISS (local, via `sentence-transformers/all-MiniLM-L6-v2`) |
| LLM | Groq API (`openai/gpt-oss-120b`) |
| Auth | Google OAuth (Google Identity Services) |
| Database | SQLite (via SQLAlchemy) |
| Chunking | Python AST + tree-sitter (graceful fallback to character split) |

## Environment Variables

Create two `.env` files:

**Root `.env`** (backend — loaded by `load_dotenv`):
```
GROQ_API_KEY=gsk_your_groq_key
GOOGLE_CLIENT_ID=your_google_oauth_client_id
JWT_SECRET=a_random_secret_string
GITHUB_TOKEN=github_pat_your_token   # Optional: Contents:Read scope for higher API rate limit
```

**`frontend/.env`** (React — must be prefixed `REACT_APP_`):
```
REACT_APP_GOOGLE_CLIENT_ID=your_google_oauth_client_id
```

> If `GITHUB_TOKEN` is not set, the GitHub API falls back to anonymous (60 req/hr limit).

## Local Development

### Backend

```bash
cd code-app
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
```

The frontend dev server proxies API calls to `http://127.0.0.1:8000` automatically (checked via `window.location.hostname === 'localhost'`).

## Deployment (Split Architecture)

Frontend and backend are deployed separately for zero cold-start on the UI.

### Backend — Render

1. Push your repo to GitHub
2. Create a new **Web Service** on Render (or use `render.yaml`)
3. Set:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r code-app/requirements.txt`
   - **Start Command:** `cd code-app && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables from `.env`
5. Deploy — your API will be at `https://codesense-api.onrender.com`

### Frontend — Cloudflare Pages (free)

1. Go to **Cloudflare Dashboard > Workers & Pages > Create > Pages > Connect to Git**
2. Select your repo
3. Set:
   - **Build command:** `cd frontend && npm ci && npm run build`
   - **Build output directory:** `frontend/build`
   - **Environment variable:** `REACT_APP_API_URL = https://codesense-api.onrender.com`
4. Deploy — your frontend will be at `https://codesense.pages.dev`

The frontend is globally distributed via Cloudflare's CDN with no spin-down or cold start.

### Docker (single-service deploy)

For a single-service deploy (Render or Railway):

```bash
docker build -t codesense .
docker run -p 8000:8000 --env-file .env codesense
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/github/ingest` | Ingest a GitHub repo (`repo_url`, `max_files`) |
| POST | `/query/` | Semantic search (`query`, `top_k`) |
| POST | `/gpt/query` | LLM Q&A (`prompt`, `top_k`, `include_context`, `conversation_id`) |
| POST | `/architecture/generate` | Generate module architecture diagram + metadata |
| POST | `/architecture/clear` | Clear the FAISS vectorstore |
| POST | `/auth/google` | Sign in with Google credential |
| GET | `/auth/me` | Get current user profile (requires auth) |
| GET | `/conversations/` | List conversations (requires auth) |
| POST | `/conversations/` | Create conversation (requires auth) |
| DELETE | `/conversations/{id}` | Delete conversation (requires auth) |

## Project Structure

```
code-app/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── database.py                # SQLAlchemy engine + migrations
│   ├── models.py                  # User, Conversation, Message tables
│   ├── deps.py                    # JWT helpers, auth dependencies
│   ├── routes/
│   │   ├── ingest.py              # File upload ingest (legacy)
│   │   ├── github.py              # GitHub repo ingest
│   │   ├── query.py               # Semantic search
│   │   ├── gpt.py                 # LLM Q&A
│   │   ├── architecture.py        # Architecture diagram generation
│   │   ├── auth.py                # Google OAuth
│   │   ├── conversations.py       # Conversation CRUD
│   │   └── tree.py                # Symbol/module listing
│   └── services/
│       ├── storage.py             # FAISS vectorstore (load/save/embed)
│       ├── github_loader.py       # GitHub API file fetcher
│       ├── gpt_rag.py             # Groq / OpenAI client + RAG prompt
│       ├── ast_chunker.py         # Python AST chunking
│       └── tree_sitter_chunker.py # tree-sitter chunking for JS/TS/etc.
├── requirements.txt
└── vectorstore/                   # FAISS index (gitignored, created at runtime)

frontend/
├── public/
├── src/
│   ├── App.js                     # Main app component
│   ├── App.css                    # Styles (dark cyber theme)
│   ├── AuthContext.js             # Google OAuth integration
│   └── index.js                   # React entry point
├── package.json
└── .env

Dockerfile                          # Multi-stage production build
render.yaml                         # Render.com deployment config
```
