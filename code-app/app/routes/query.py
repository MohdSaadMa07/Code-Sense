from fastapi import APIRouter
from pydantic import BaseModel
from app.services.storage import get_vectorstore

router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


def _is_column_intent(query: str) -> bool:
    text = query.lower()
    return "column" in text or ("table" in text and ("field" in text or "header" in text or "cart" in text))


def _is_code_intent(query: str) -> bool:
    text = query.lower()
    code_markers = ["def ", "class ", "function", "method", "where is", "file", "api", "route", "update_cart"]
    return any(marker in text for marker in code_markers)


def _adjusted_score(query: str, doc, score: float) -> float:
    adjusted = float(score)
    metadata = doc.metadata or {}
    content = (doc.page_content or "").lower()
    path = str((metadata.get("path") or metadata.get("filename") or "")).lower()
    chunk_type = metadata.get("chunk_type")
    parse_quality = metadata.get("parse_quality")

    if parse_quality == "high":
        adjusted -= 0.15
    elif parse_quality == "low":
        adjusted += 0.15

    if chunk_type == "fallback":
        adjusted += 0.25

    if _is_column_intent(query):
        if chunk_type == "html_table_headers":
            adjusted -= 0.45
        if "table columns:" in content:
            adjusted -= 0.25

    if _is_code_intent(query):
        if chunk_type in {"ast", "tree_sitter"}:
            adjusted -= 0.2
        if "readme" in path:
            adjusted += 0.25

    return adjusted


@router.post("/")
def query_vectorstore(request: QueryRequest):
    vectorstore = get_vectorstore()

    results = vectorstore.similarity_search_with_score(
        request.query,
        k=request.top_k * 4,
    )
    ranked_results = sorted(results, key=lambda item: _adjusted_score(request.query, item[0], item[1]))

    seen = set()
    formatted_results = []

    for rank, (doc, score) in enumerate(ranked_results, start=1):
        content = doc.page_content.strip()

        # skip empty or duplicate chunks
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

    return {
        "query": request.query,
        "results": formatted_results
    }
