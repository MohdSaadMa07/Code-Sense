from fastapi import APIRouter, UploadFile, File
from app.services.storage import store_documents
from langchain_core.documents import Document  # Fixed: from langchain-core
from langchain_text_splitters import RecursiveCharacterTextSplitter  # Fixed: separate package


router = APIRouter(prefix="/ingest", tags=["Ingest"])


@router.post("/")
async def ingest_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8")
        chunks = split_text(text)  
        documents = [Document(page_content=chunk) for chunk in chunks]

        chunks_ingested = store_documents(documents)

        return {"status": "success", "chunks_ingested": chunks_ingested}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(  # Now works
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return splitter.split_text(text)
