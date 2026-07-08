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
from app.routes.auth import router as auth_router
from app.routes.conversations import router as conversations_router
from app.database import init_db
from app.models import User, Conversation, Message

import gc
import threading
from pathlib import Path
from dotenv import load_dotenv
from fastapi.responses import JSONResponse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(APP_DIR / ".env", override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://code-sense.pages.dev"],
    allow_origin_regex=r"https://[a-z0-9-]+\.code-sense\.pages\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(github_router)
app.include_router(gpt_router)
app.include_router(symbols_router)
app.include_router(architecture_router)
app.include_router(auth_router)
app.include_router(conversations_router)

_model_ready = threading.Event()


@app.get("/health")
def health():
    if _model_ready.is_set():
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "loading"})


@app.on_event("startup")
def _start_model_download():
    from app.services.onnx_embeddings import _ensure_model
    def _warmup():
        try:
            _ensure_model()
        except Exception:
            pass
        finally:
            _model_ready.set()
            gc.collect()
    t = threading.Thread(target=_warmup, daemon=True)
    t.start()

FRONTEND_BUILD = Path(__file__).resolve().parents[2] / "frontend" / "build"
if FRONTEND_BUILD.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD / "static"), check_dir=False), name="static")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_BUILD), check_dir=False), name="assets")

    @app.get("/")
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str = ""):
        if any(full_path.startswith(p) for p in ("api/", "architecture/", "github/", "gpt/", "ingest/", "query/", "auth/", "conversations/")):
            return {"detail": "Not Found"}
        return FileResponse(str(FRONTEND_BUILD / "index.html"))
else:
    @app.get("/")
    async def root():
        return {"message": "FastAPI + MiniLM embeddings ready!"}
