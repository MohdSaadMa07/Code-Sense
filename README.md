
# CodeSense

Semantic code search engine for any GitHub repository. Ingests codebases into a vector index and lets you query them with natural language.

## Setup

Set these **Secrets** in your HF Space settings:

- `GROQ_API_KEY` – for LLM-powered answers
- `JWT_SECRET` – JWT signing key
- `GOOGLE_CLIENT_ID` – Google OAuth client ID
- `GITHUB_TOKEN` – GitHub API token (higher rate limits)
- `JINA_API_KEY` – for embeddings (optional if using local model)

## Usage

The frontend is served at `https://code-sense.pages.dev` (Cloudflare Pages). The API is this Space.
