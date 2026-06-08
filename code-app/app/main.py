# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes.ingest import router as ingest_router
from app.routes.query import router as query_router
from app.routes.github import router as github_router
from app.routes.gpt import router as gpt_router
from app.routes.tree import router as symbols_router
from app.routes.architecture import router as architecture_router

from pathlib import Path
from dotenv import load_dotenv

# Load env from both common locations; app/.env overrides root if both exist.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(APP_DIR / ".env", override=True)

app = FastAPI()

# Allow local frontend apps to call the API.
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

# Serve built React frontend
FRONTEND_BUILD = Path(__file__).resolve().parents[2] / "frontend" / "build"
if FRONTEND_BUILD.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD / "static"), check_dir=False), name="static")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_BUILD), check_dir=False), name="assets")

    @app.get("/")
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str = ""):
        if full_path.startswith("api/") or full_path.startswith("architecture/") or full_path.startswith("github/") or full_path.startswith("gpt/") or full_path.startswith("ingest/") or full_path.startswith("query/"):
            return {"detail": "Not Found"}
        return FileResponse(str(FRONTEND_BUILD / "index.html"))
else:
    @app.get("/")
    async def root():
        return {"message": "FastAPI + MiniLM embeddings ready!"}
