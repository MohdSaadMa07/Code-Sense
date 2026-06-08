import json
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.routes.ingest import router as ingest_router
from app.routes.query import router as query_router, search_query
from app.routes.github import router as github_router
from app.routes.gpt import router as gpt_router
from app.routes.tree import router as symbols_router
from app.routes.architecture import router as architecture_router, generate_architecture
from app.services.github_loader import parse_github_repo, collect_repo_files
from app.services.storage import store_documents, clear_vectorstore
from app.services.gpt_rag import rag_query
from langchain_core.documents import Document
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(APP_DIR / ".env", override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(github_router)
app.include_router(gpt_router)
app.include_router(symbols_router)
app.include_router(architecture_router)

FRONTEND_BUILD = Path(__file__).resolve().parents[2] / "frontend" / "build"
HAS_FRONTEND = FRONTEND_BUILD.is_dir()

if HAS_FRONTEND:
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD / "static"), check_dir=False), name="static")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_BUILD), check_dir=False), name="assets")


@app.get("/")
async def root(
    action: Optional[str] = Query(None),
    prompt: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    question: Optional[str] = Query(None),
    top_k: int = Query(3),
    repo_url: Optional[str] = Query(None),
    max_files: int = Query(500),
    include_context: bool = Query(False),
):
    q = prompt or question or query

    if action == "query" or (not action and q):
        try:
            result = rag_query(query=q, top_k=top_k)
            resp = {
                "result": result.get("llm_answer", ""),
                "confidence": "high" if result.get("llm_answer") else "low",
                "confidence_score": 0.8 if result.get("llm_answer") else 0.0,
            }
            if include_context:
                resp["context"] = result.get("retrieved_chunks", [])
            return resp
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"Query failed: {str(e)}"})

    if action == "search" or (not action and query):
        try:
            return search_query(query=query or q, top_k=top_k)
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"Search failed: {str(e)}"})

    if action == "ingest" or (not action and repo_url):
        try:
            owner, repo = parse_github_repo(repo_url)
            files = collect_repo_files(owner, repo, max_files=max_files)
            if not files:
                return JSONResponse(status_code=503, content={"detail": "No files fetched from GitHub"})
            documents = [
                Document(page_content=f.get("content", ""), metadata={"path": f.get("path", "")})
                for f in files if f.get("content", "").strip()
            ]
            stored = store_documents(documents)
            return {"status": "success", "repo": f"{owner}/{repo}", "files_ingested": len(files), "chunks_ingested": stored}
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"Ingest failed: {str(e)}"})

    if action == "architecture":
        try:
            return generate_architecture()
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"Architecture failed: {str(e)}"})

    if action == "clear":
        clear_vectorstore()
        return {"status": "cleared"}

    if action == "status":
        return {"status": "ok"}

    if HAS_FRONTEND:
        return FileResponse(str(FRONTEND_BUILD / "index.html"))
    return {"message": "FastAPI + MiniLM embeddings ready!"}


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    if full_path.startswith("api/") or full_path.startswith("architecture/") or full_path.startswith("github/") or full_path.startswith("gpt/") or full_path.startswith("ingest/") or full_path.startswith("query/"):
        return {"detail": "Not Found"}
    if HAS_FRONTEND:
        return FileResponse(str(FRONTEND_BUILD / "index.html"))
    return {"message": "FastAPI + MiniLM embeddings ready!"}
