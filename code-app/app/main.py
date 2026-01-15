# app/main.py
from fastapi import FastAPI
from app.routes.ingest import router as ingest_router

app = FastAPI()
app.include_router(ingest_router)

@app.get("/")
async def root():
    return {"message": "FastAPI + MiniLM embeddings ready!"}
