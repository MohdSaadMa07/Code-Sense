from fastapi import APIRouter
from app.services.storage import get_vectorstore

router = APIRouter(prefix="/symbols", tags=["Symbols"])


@router.get("/")
def get_symbols():
    vs = get_vectorstore()

    if not vs or not hasattr(vs, "docstore"):
        return {"files": []}

    files: dict[str, list[dict]] = {}

    for doc_id in vs.index_to_docstore_id.values():
        doc = vs.docstore.get(doc_id)
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
