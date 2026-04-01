from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.storage import store_documents
from langchain_core.documents import Document


router = APIRouter(prefix="/ingest", tags=["Ingest"])


@router.post("/")
async def ingest_file(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be UTF-8 encoded text.",
        ) from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="Uploaded file has no ingestible text content.")

    documents = [
        Document(
            page_content=text,
            metadata={"filename": file.filename} if file.filename else {},
        )
    ]

    try:
        chunks_ingested = store_documents(documents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return {"status": "success", "chunks_ingested": chunks_ingested}
