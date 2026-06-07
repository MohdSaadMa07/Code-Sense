# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.ingest import router as ingest_router
from app.routes.query import router as query_router
from app.routes.github import router as github_router
from app.routes.llama import router as llama_router
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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(github_router)
app.include_router(llama_router)
app.include_router(symbols_router)
app.include_router(architecture_router)

@app.get("/")
async def root():
    return {"message": "FastAPI + MiniLM embeddings ready!"}
