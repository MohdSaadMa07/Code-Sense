import gc
import hashlib
import os
import shutil
from pathlib import Path

from langchain_core.documents import Document
from app.services.ast_chunker import chunk_documents_with_ast
from app.services.retrieval.hybrid import HybridRetriever
from app.services.retrieval.manager import manager

VECTORSTORE_PATH = str(Path(__file__).resolve().parent.parent.parent / "vectorstore")


def clear_vectorstore():
    path = VECTORSTORE_PATH
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"[CLEAR] Removed vectorstore at {path}")


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


BATCH_SIZE = 64


def _ingest_chunks(repo_id: str, chunks: list[Document]) -> int:
    if not chunks:
        return 0
    total = len(chunks)
    n = len(chunks)
    for i in range(0, n, BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        last = i + BATCH_SIZE >= n
        manager.ingest(repo_id, batch, save=last)
        gc.collect()
    return total


def store_documents(repo_id: str, documents: list[Document], chunk_size=3000, chunk_overlap=50):
    if not documents:
        raise ValueError("No documents provided")
    all_chunks = chunk_documents_with_ast(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    del documents
    ingestible_chunks = _filter_chunks(all_chunks)
    del all_chunks
    total_ingested = _ingest_chunks(repo_id, ingestible_chunks)
    del ingestible_chunks
    gc.collect()
    return total_ingested


def store_single_batch(repo_id: str, documents: list[Document], save: bool = True, chunk_size=3000, chunk_overlap=50):
    if not documents:
        return 0
    all_chunks = chunk_documents_with_ast(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    ingestible_chunks = _filter_chunks(all_chunks)
    del all_chunks, documents
    gc.collect()
    if not ingestible_chunks:
        return 0
    total = _ingest_chunks(repo_id, ingestible_chunks)
    if save:
        manager.save(repo_id)
    del ingestible_chunks
    gc.collect()
    return total
