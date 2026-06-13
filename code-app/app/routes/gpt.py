import re
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.services.gpt_rag import rag_query
from app.database import get_db
from app.deps import get_optional_user
from app.models import User, Conversation, Message

router = APIRouter(prefix="/gpt", tags=["GPT"])


class LlamaQueryRequest(BaseModel):
    prompt: Optional[str] = None
    top_k: Optional[int] = None
    include_context: Optional[bool] = None
    debug: Optional[bool] = None
    conversation_id: Optional[int] = None


# ---------------------------
# Confidence (heuristic)
# ---------------------------
def _detect_failure(answer: str) -> bool:
    bad = ["i don't know", "cannot answer", "not relevant", "insufficient"]
    return any(p in answer.lower() for p in bad)


def _compute_confidence(answer: str, chunks) -> tuple:
    if not answer:
        return "low", 0.0

    if _detect_failure(answer):
        return "low", 0.2

    if not chunks:
        return "medium", 0.5

    context_text = "\n\n".join(c.get("chunk", "")[:600] for c in chunks if c.get("chunk"))
    context_lower = context_text.lower()
    answer_lower = answer.lower()

    words = [w for w in answer_lower.split() if len(w) > 3]
    if not words:
        return "low", 0.3

    hits = sum(1 for w in words if w in context_lower)
    ratio = hits / len(words)

    if ratio >= 0.3:
        return "high", min(0.95, 0.5 + ratio * 0.5)
    elif ratio >= 0.1:
        return "medium", 0.4 + ratio * 0.5
    else:
        return "low", max(0.15, ratio)


# ---------------------------
# Endpoint
# ---------------------------
@router.post("/query")
def query_gpt(
    prompt: Optional[str] = Query(None),
    top_k: int = Query(3),
    include_context: bool = Query(False),
    debug: bool = Query(False),
    conversation_id: Optional[int] = Query(None),
    payload: Optional[LlamaQueryRequest] = Body(None),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    try:
        if prompt is None and payload and payload.prompt:
            prompt = payload.prompt
        if payload and payload.top_k is not None:
            top_k = payload.top_k
        if payload and payload.include_context is not None:
            include_context = payload.include_context
        if payload and payload.debug is not None:
            debug = payload.debug
        if payload and payload.conversation_id is not None:
            conversation_id = payload.conversation_id

        if not prompt:
            raise ValueError("'prompt' is required in query params or JSON body")

        rag_result = rag_query(query=prompt, top_k=top_k)

        answer = rag_result.get("llm_answer", "")
        chunks = rag_result.get("retrieved_chunks", [])

        confidence_label, confidence_score = _compute_confidence(answer, chunks)

        if confidence_label == "low":
            answer = answer + "\n\nLow confidence (may be partially inferred from context)"

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
                "confidence": {"label": confidence_label, "score": confidence_score},
                "num_chunks": len(chunks),
            }

        if user and conversation_id:
            conv = db.query(Conversation).filter(
                Conversation.id == conversation_id, Conversation.user_id == user.id
            ).first()
            if conv:
                q_msg = Message(conversation_id=conv.id, role="user", content=prompt)
                ctx_snapshot = [{"source": c.get("source"), "score": c.get("score")} for c in chunks] if chunks else None
                a_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=rag_result.get("llm_answer", answer),
                    metadata_={"context": ctx_snapshot} if ctx_snapshot else None,
                )
                db.add(q_msg)
                db.add(a_msg)
                if conv.title == "New conversation":
                    conv.title = prompt[:60]
                db.commit()

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
