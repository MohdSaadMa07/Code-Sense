from fastapi import FastAPI
from app.routes.ingest import router as ingest_router

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(ingest_router, prefix="/ingest", tags=["Ingest"])
