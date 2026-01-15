# app/main.py
from fastapi import FastAPI
from app.routes.ingest import router as ingest_router
from app.routes.query import router as query_router

app = FastAPI()
app.include_router(ingest_router)
app.include_router(query_router)

@app.get("/")
async def root():
    return {"message": "FastAPI + MiniLM embeddings ready!"}
