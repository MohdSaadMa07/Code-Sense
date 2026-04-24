from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel
from app.services.llama_rag import rag_query

router = APIRouter(prefix="/llama", tags=["LLaMA"])


class LlamaQueryRequest(BaseModel):
    prompt: Optional[str] = None
    top_k: Optional[int] = None
    include_context: Optional[bool] = None
    debug: Optional[bool] = None


# ---------------------------
# Confidence Helpers
# ---------------------------
def _detect_failure(answer: str) -> bool:
    bad_phrases = [
    "i don't know",
    "cannot answer"
]
    answer_lower = answer.lower()
    return any(p in answer_lower for p in bad_phrases)


def _keyword_overlap(answer: str, chunks) -> float:
    if not chunks:
        return 0.0

    context_text = " ".join(
        c.get("chunk", "").lower() for c in chunks
    )
    words = [w for w in answer.lower().split() if len(w) > 3]

    if not words:
        return 0.0

    matches = sum(1 for w in words if w in context_text)
    return matches / len(words)


def _compute_llm_confidence(answer: str, chunks):
    if not answer:
        return "low", 0.0

    # Failure detection
    if _detect_failure(answer):
        return "low", 0.2

    overlap = _keyword_overlap(answer, chunks)

    # Heuristic thresholds
    if overlap > 0.35:
        return "high", 0.9
    elif overlap > 0.2:
        return "medium", 0.65
    else:
        return "low", 0.4


def _fallback_from_context(chunks):
    if not chunks:
        return "No relevant context found."

    snippets = []
    for c in chunks[:2]:
        text = c.get("chunk", "")
        snippets.append(text[:200])

    return "LLM uncertain. Relevant context:\n\n" + "\n\n---\n\n".join(snippets)


# ---------------------------
# Endpoint
# ---------------------------
@router.post("/query")
async def query_llama(
    prompt: Optional[str] = Query(None, description="The question to ask LLaMA"),
    top_k: int = Query(3, description="Number of context chunks to retrieve"),
    include_context: bool = Query(False, description="Include retrieved context in response"),
    debug: bool = Query(False, description="Return debug info"),
    payload: Optional[LlamaQueryRequest] = Body(None),
):
    try:
        # Accept either query parameters or JSON body for compatibility.
        if prompt is None and payload and payload.prompt:
            prompt = payload.prompt
        if payload and payload.top_k is not None:
            top_k = payload.top_k
        if payload and payload.include_context is not None:
            include_context = payload.include_context
        if payload and payload.debug is not None:
            debug = payload.debug

        if not prompt:
            raise ValueError("'prompt' is required in query params or JSON body")

        rag_result = rag_query(query=prompt, top_k=top_k)

        answer = rag_result.get("llm_answer", "")
        chunks = rag_result.get("retrieved_chunks", [])

        # ---------------------------
        # Confidence
        # ---------------------------
        confidence_label, confidence_score = _compute_llm_confidence(answer, chunks)

        # ---------------------------
        # Fallback if weak answer
        # ---------------------------
        if confidence_label == "low":
                answer = answer + "\n\n⚠ Low confidence (may be partially inferred from context)"

        # ---------------------------
        # Response
        # ---------------------------
        response = {
            "result": answer,
            "confidence": confidence_label,
            "confidence_score": confidence_score,
        }

        if "accuracy_scores" in rag_result:
            response["accuracy_scores"] = rag_result["accuracy_scores"]

        if include_context:
            response["context"] = chunks

        if debug:
            response["debug"] = {
                "raw_answer": rag_result.get("llm_answer"),
                "overlap_score": _keyword_overlap(answer, chunks),
                "num_chunks": len(chunks),
            }

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLaMA query failed: {str(e)}")