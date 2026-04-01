from fastapi import APIRouter, Query, HTTPException
from app.services.llama_rag import rag_query

router = APIRouter(prefix="/llama", tags=["LLaMA"])


@router.post("/query")
async def query_llama(
    prompt: str = Query(..., description="The question to ask LLaMA"),
    top_k: int = Query(3, description="Number of context chunks to retrieve"),
    include_context: bool = Query(False, description="Include retrieved context in response"),
):
    """
    Query LLaMA with retrieved context from the vector store.
    Supports both query parameters and JSON body.
    """
    try:
        rag_result = rag_query(query=prompt, top_k=top_k)

        response = {"result": rag_result["llm_answer"]}

        if include_context:
            # Uses chunks already deduped inside rag_query — no raw similarity_search here
            response["context"] = rag_result["retrieved_chunks"]

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLaMA query failed: {str(e)}")