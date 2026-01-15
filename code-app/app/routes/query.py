from fastapi import APIRouter
from pydantic import BaseModel
from app.services.storage import get_vectorstore

router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


@router.post("/")
def query_vectorstore(request: QueryRequest):
    vectorstore = get_vectorstore()

    results = vectorstore.similarity_search_with_score(
        request.query,
        k=request.top_k
    )

    seen = set()
    formatted_results = []

    for doc, score in results:
        content = doc.page_content.strip()

        # skip empty or duplicate chunks
        if not content or content in seen:
            continue

        seen.add(content)

        formatted_results.append({
            "chunk": content,
            "score": float(score)
        })

    return {
        "query": request.query,
        "results": formatted_results
    }
