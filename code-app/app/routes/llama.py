from fastapi import APIRouter
from app.services.rag import rag_query  # your LLaMA query function

router = APIRouter(prefix="/llama", tags=["LLaMA"])

@router.post("/query")
def query_llama(prompt: str):
    result = rag_query(prompt)
    return {"result": result}
