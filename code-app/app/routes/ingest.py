from fastapi import APIRouter, UploadFile, File
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.storage import store_documents

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/")
async def ingest_file(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )

    chunks = splitter.split_text(text)

    store_documents(chunks)

    return {
        "status": "success",
        "chunks_stored": len(chunks)
    }
