# Code-Sense

Code-Sense is a Retrieval-Augmented Generation (RAG) application built with FastAPI. It enables users to ingest local text files and GitHub repositories into a vector store and perform semantic searches or generate context-aware answers using a local Llama model.

## Features

- **FastAPI Backend**: High-performance asynchronous API.
- **File Ingestion**: Upload and process local text files.
- **GitHub Ingestion**: Ingest entire public GitHub repositories by URL.
- **Semantic Search**: Uses FAISS (Facebook AI Similarity Search) and HuggingFace embeddings (`all-MiniLM-L6-v2`) for efficient vector retrieval.
- **Local RAG**: Generates answers using a local Llama 3.2 model, ensuring data privacy and offline capability.
- **Modular Architecture**: Clean separation between routes, services, and models.
- **Structure-Aware Chunking**: Uses Python AST for `.py` files and Tree-sitter for non-Python source files before embedding.

## Project Structure

```text
/code-app
├── app/
│   ├── main.py                # Application entry point & router registration
│   ├── models/
│   │   ├── document.py        # Pydantic models for data structures
│   │   └── Llama-3.2-1B-Instruct-F16.gguf # Local LLM weights
│   ├── routes/
│   │   ├── github.py          # GitHub repository ingestion endpoints
│   │   ├── ingest.py          # Local file ingestion endpoints
│   │   ├── llama.py           # RAG query endpoints
│   │   └── query.py           # Similarity search endpoints
│   └── services/
│       ├── embeddings.py      # Embedding model initialization
│       ├── github_loader.py   # GitHub API interaction & file processing
│       ├── llama_rag.py       # RAG logic implementation
│       ├── rag.py             # Core RAG retrieval & generation logic
│       ├── storage.py         # FAISS vector store management
│       └── tree_sitter_chunker.py # Tree-sitter chunking for non-Python files
├── vectorstore/               # Local storage for FAISS index and metadata
│   ├── index.faiss
│   └── index.pkl
└── .env                       # Environment variables (e.g., API keys)
```

## Getting Started

### Prerequisites

- Python 3.10+
- [Llama-cpp-python](https://github.com/abetlen/llama-cpp-python) (for local LLM inference)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd code-app
   ```

2. **Install dependencies**:
   *(Note: Ensure you have the necessary build tools for llama-cpp-python)*
   ```bash
   pip install -r code-app/requirements.txt
   ```

3. **Environment Setup**:
   Create a `.env` file in the root directory (optional, but recommended for GitHub API stability):
   ```text
   GITHUB_TOKEN=your_github_pat  # Optional: to avoid rate limits
   ```

4. **Model Placement**:
   Ensure the Llama GGUF model is placed at:
   `code-app/app/models/Llama-3.2-1B-Instruct-F16.gguf`

### Running the Application

Start the FastAPI server using Uvicorn:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Documentation can be accessed at `http://localhost:8000/docs`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | `GET` | Health check endpoint. |
| `/ingest/` | `POST` | Upload a text file to the vector store. |
| `/query/` | `POST` | Perform a raw similarity search in the vector store (includes chunk metadata such as `path`, `chunk_type`, and line range). |
| `/github/ingest`| `POST` | Ingest files from a public GitHub repository. |
| `/llama/query` | `POST` | Perform a RAG query using the Llama model. |

## How it Works

1. **Ingestion**: Python files are chunked with `ast` by symbols; non-Python files are chunked with Tree-sitter by syntax nodes. If parsing is unavailable, fallback chunking is used. Each chunk is embedded using `all-MiniLM-L6-v2` and stored in FAISS.
2. **Retrieval**: When a query is made, the application embeds the query and finds the most similar chunks in the FAISS index.
3. **Augmentation & Generation**: The retrieved chunks are injected into a prompt as context, which is then passed to the local Llama model to generate a relevant response.

## Retrieval Accuracy Benchmark

Use the built-in harness to measure retrieval quality (`Hit@k`, `MRR@k`) from `POST /query/`.

### Benchmark case format

`code-app/benchmarks/query_eval_cases.json`

```json
[
  {
    "id": "cart-view-fn",
    "query": "where is the cart view function defined",
    "relevant_paths": ["cart/views.py"],
    "relevant_symbols": ["cart_view"],
    "relevant_terms": ["def cart_view"]
  }
]
```

At least one of `relevant_paths`, `relevant_symbols`, or `relevant_terms` should be provided per case.

### Run benchmark

```bash
python code-app/scripts/benchmark_query_accuracy.py --self-test
python code-app/scripts/benchmark_query_accuracy.py --base-url http://127.0.0.1:8000 --cases-file code-app/benchmarks/query_eval_cases.json --top-k 5
```

Interpretation:
- Higher `hit@k` means relevant chunks are found more often.
- Higher `mrr@k` means relevant chunks appear earlier in the ranked results.
