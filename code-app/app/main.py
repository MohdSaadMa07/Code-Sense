# app/main.py
from fastapi import FastAPI
from app.routes.ingest import router as ingest_router
from app.routes.query import router as query_router
from app.routes.github import router as github_router
from app.routes.llama import router as llama_router

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(github_router)
app.include_router(llama_router)

@app.get("/")
async def root():
    return {"message": "FastAPI + MiniLM embeddings ready!"}
