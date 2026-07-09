from fastapi import APIRouter, Query
from app.services.retrieval.manager import manager

router = APIRouter(prefix="/symbols", tags=["Symbols"])


@router.get("/")
def get_symbols(repository_id: str = Query(...)):
    if not manager.has_repo(repository_id):
        return {"files": []}

    hybrid = manager.get(repository_id)

    if not hasattr(hybrid, "docstore"):
        return {"files": []}

    files: dict[str, list[dict]] = {}

    for doc_id in hybrid.index_to_docstore_id.values():
        doc = hybrid.docstore.get(doc_id)
        if not doc or not hasattr(doc, "metadata"):
            continue

        meta = doc.metadata
        path = meta.get("path") or meta.get("filename")
        symbol = meta.get("symbol")
        kind = meta.get("symbol_kind")
        start = meta.get("start_line")
        end = meta.get("end_line")

        if not path or not symbol:
            continue

        if path not in files:
            files[path] = []

        existing = next((s for s in files[path] if s["name"] == symbol), None)
        if not existing:
            files[path].append({
                "name": symbol,
                "kind": kind or "symbol",
                "start_line": start,
                "end_line": end,
            })

    result = []
    for path in sorted(files):
        result.append({
            "path": path,
            "symbols": files[path],
        })

    return {"files": result}
