import hashlib
import os
import shutil
from pathlib import Path

from langchain_core.documents import Document
from app.services.ast_chunker import chunk_documents_with_ast
from app.services.retrieval.hybrid import HybridRetriever

_vectorstore = None

VECTORSTORE_PATH = str(Path(__file__).resolve().parent.parent.parent / "vectorstore")


def clear_vectorstore():
    global _vectorstore
    _vectorstore = None
    if os.path.isdir(VECTORSTORE_PATH):
        shutil.rmtree(VECTORSTORE_PATH)
        print(f"[CLEAR] Removed vectorstore at {VECTORSTORE_PATH}")


def get_vectorstore():
    global _vectorstore
    if _vectorstore is None and os.path.isdir(VECTORSTORE_PATH) and os.path.isfile(os.path.join(VECTORSTORE_PATH, "bm25_index.pkl")):
        try:
            _vectorstore = HybridRetriever.load_local(VECTORSTORE_PATH)
            print(f"[OK] Loaded Hybrid index ({_vectorstore.num_docs} docs) from {VECTORSTORE_PATH}")
        except Exception as e:
            print(f"[WARN] Could not load existing Hybrid index: {e}")
    if _vectorstore is None:
        _vectorstore = HybridRetriever()
    return _vectorstore


def _default_parse_quality(chunk_type: str) -> str:
    if chunk_type in {"ast", "tree_sitter", "html_table_headers"}:
        return "high"
    if chunk_type == "module":
        return "medium"
    return "low"


def _looks_like_noise(content: str) -> bool:
    stripped = (content or "").strip()
    if not stripped or len(stripped) < 25:
        return True
    alnum = sum(ch.isalnum() for ch in stripped)
    return alnum < 8


def _is_markdown_image_or_badge(content: str) -> bool:
    text = " ".join((content or "").lower().split())
    return text.startswith("![") or ("img.shields.io" in text)


def _with_ingestion_metadata(doc: Document) -> Document:
    metadata = dict(doc.metadata or {})
    content = (doc.page_content or "").strip()
    path = metadata.get("path") or metadata.get("filename") or ""
    ext = os.path.splitext(str(path))[1].lower() if path else None
    chunk_type = metadata.get("chunk_type") or "fallback"
    metadata["path"] = path
    metadata["source_ext"] = ext
    metadata["content_length"] = len(content)
    metadata["parse_quality"] = metadata.get("parse_quality") or _default_parse_quality(chunk_type)
    stable_key = "|".join([str(path), str(metadata.get("symbol") or ""), str(metadata.get("start_line") or ""), str(metadata.get("end_line") or ""), content[:120]])
    metadata["chunk_id"] = hashlib.sha1(stable_key.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return Document(page_content=content, metadata=metadata)


def _filter_chunks(chunks: list[Document]) -> list[Document]:
    filtered: list[Document] = []
    seen_ids: set[str] = set()
    for chunk in chunks:
        content = (chunk.page_content or "").strip()
        metadata = chunk.metadata or {}
        chunk_type = metadata.get("chunk_type") or "fallback"
        if _is_markdown_image_or_badge(content):
            continue
        if chunk_type == "fallback" and _looks_like_noise(content):
            continue
        enriched = _with_ingestion_metadata(chunk)
        chunk_id = enriched.metadata.get("chunk_id")
        if chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            filtered.append(enriched)
    return filtered


def store_documents(documents: list[Document], chunk_size=2000, chunk_overlap=50):
    if not documents:
        raise ValueError("No documents provided")
    vs = get_vectorstore()
    all_chunks = chunk_documents_with_ast(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    ingestible_chunks = _filter_chunks(all_chunks)
    if ingestible_chunks:
        vs.add_documents(ingestible_chunks)
        vs.save_local(VECTORSTORE_PATH)
        print(f"[SAVE] Saved Hybrid index ({vs.num_docs} docs) to {VECTORSTORE_PATH}")
    return len(ingestible_chunks)
