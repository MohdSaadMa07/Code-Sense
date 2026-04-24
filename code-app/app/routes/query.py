from fastapi import APIRouter
from pydantic import BaseModel
from app.services.storage import get_vectorstore

router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


# ---------------------------
# Intent Detection
# ---------------------------
def _is_column_intent(query: str) -> bool:
    text = query.lower()
    return "column" in text or (
        "table" in text and ("field" in text or "header" in text or "cart" in text)
    )


def _is_code_intent(query: str) -> bool:
    text = query.lower()
    code_markers = [
        "def ", "class ", "function", "method",
        "where is", "file", "api", "route", "update_cart"
    ]
    return any(marker in text for marker in code_markers)


# ---------------------------
# Adjusted Scoring
# ---------------------------
def _adjusted_score(query: str, doc, score: float) -> float:
    adjusted = float(score)
    metadata = doc.metadata or {}
    content = (doc.page_content or "").lower()
    path = str((metadata.get("path") or metadata.get("filename") or "")).lower()

    chunk_type = metadata.get("chunk_type")
    parse_quality = metadata.get("parse_quality")

    # Parse quality weighting
    if parse_quality == "high":
        adjusted -= 0.15
    elif parse_quality == "low":
        adjusted += 0.15

    # Penalize fallback chunks
    if chunk_type == "fallback":
        adjusted += 0.25

    # Column intent tuning
    if _is_column_intent(query):
        if chunk_type == "html_table_headers":
            adjusted -= 0.45
        if "table columns:" in content:
            adjusted -= 0.25

    # Code intent tuning
    if _is_code_intent(query):
        if chunk_type in {"ast", "tree_sitter"}:
            adjusted -= 0.2
        if "readme" in path:
            adjusted += 0.25

    return adjusted


# ---------------------------
# Confidence Calculation
# ---------------------------
def _compute_confidence(query: str, ranked_results, top_k: int):
    if not ranked_results:
        return "low", 0.0

    # Use top_k results
    top_items = ranked_results[:top_k]

    adjusted_scores = [
        _adjusted_score(query, doc, score)
        for doc, score in top_items
    ]

    best = min(adjusted_scores)
    avg = sum(adjusted_scores) / len(adjusted_scores)

    # Gap signal (difference between top 2)
    gap = 0
    if len(ranked_results) > 1:
        best_score = _adjusted_score(query, ranked_results[0][0], ranked_results[0][1])
        second_score = _adjusted_score(query, ranked_results[1][0], ranked_results[1][1])
        gap = second_score - best_score

    # Heuristic thresholds (tune later)
    if best < 0.8 and avg < 1.2:
        label = "high"
        score = 0.85
    elif best < 1.2:
        label = "medium"
        score = 0.6
    else:
        label = "low"
        score = 0.3

    # Boost if strong gap (clear winner)
    if gap > 0.3:
        score = min(score + 0.1, 1.0)

    return label, round(score, 2)


# ---------------------------
# Main Endpoint
# ---------------------------
@router.post("/")
def query_vectorstore(request: QueryRequest):
    vectorstore = get_vectorstore()

    # Retrieve more for reranking
    results = vectorstore.similarity_search_with_score(
        request.query,
        k=request.top_k * 4,
    )

    # Rerank using adjusted score
    ranked_results = sorted(
        results,
        key=lambda item: _adjusted_score(request.query, item[0], item[1])
    )

    seen = set()
    formatted_results = []

    for rank, (doc, score) in enumerate(ranked_results, start=1):
        content = (doc.page_content or "").strip()

        # Skip empty or duplicate chunks
        if not content or content in seen:
            continue

        seen.add(content)
        metadata = doc.metadata or {}

        formatted_results.append({
            "rank": rank,
            "chunk": content,
            "score": float(score),
            "metadata": {
                "path": metadata.get("path") or metadata.get("filename"),
                "chunk_type": metadata.get("chunk_type"),
                "symbol": metadata.get("symbol"),
                "symbol_kind": metadata.get("symbol_kind"),
                "language": metadata.get("language"),
                "node_type": metadata.get("node_type"),
                "start_line": metadata.get("start_line"),
                "end_line": metadata.get("end_line"),
                "fallback_reason": metadata.get("fallback_reason"),
                "parse_quality": metadata.get("parse_quality"),
                "chunk_id": metadata.get("chunk_id"),
            },
        })

        if len(formatted_results) >= request.top_k:
            break

    # Compute confidence
    confidence_label, confidence_score = _compute_confidence(
        request.query,
        ranked_results,
        request.top_k
    )

    return {
        "query": request.query,
        "confidence": confidence_label,
        "confidence_score": confidence_score,
        "results": formatted_results
    }