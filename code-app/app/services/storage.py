import hashlib
import os

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from app.services.ast_chunker import chunk_documents_with_ast

_embeddings = None
_vectorstore = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"  # Downloads if not local
        )
    return _embeddings

def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        embeddings = get_embeddings()
        # Proper empty FAISS init (from_texts([], ...) deprecated/buggy)
        dummy_embedding = embeddings.embed_query(" ")
        dimension = len(dummy_embedding)
        import faiss
        from langchain_community.docstore.in_memory import InMemoryDocstore
        index = faiss.IndexFlatL2(dimension)
        _vectorstore = FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=InMemoryDocstore({}),
            index_to_docstore_id={}
        )
    return _vectorstore


def _default_parse_quality(chunk_type: str) -> str:
    if chunk_type in {"ast", "tree_sitter", "html_table_headers"}:
        return "high"
    if chunk_type == "module":
        return "medium"
    return "low"


def _looks_like_noise(content: str) -> bool:
    stripped = (content or "").strip()
    if not stripped:
        return True

    if len(stripped) < 25:
        return True

    alnum = sum(ch.isalnum() for ch in stripped)
    if alnum < 8:
        return True

    return False


def _is_markdown_image_or_badge(content: str) -> bool:
    text = " ".join((content or "").lower().split())
    return text.startswith("![") or ("img.shields.io" in text)


def _with_ingestion_metadata(doc: Document) -> Document:
    metadata = dict(doc.metadata or {})
    content = (doc.page_content or "").strip()

    path = metadata.get("path") or metadata.get("filename") or ""
    ext = os.path.splitext(str(path))[1].lower() if path else None
    chunk_type = metadata.get("chunk_type") or "fallback"

    metadata["path"] = path or metadata.get("path")
    metadata["source_ext"] = ext
    metadata["content_length"] = len(content)
    metadata["parse_quality"] = metadata.get("parse_quality") or _default_parse_quality(chunk_type)

    stable_key = "|".join(
        [
            str(path),
            str(metadata.get("symbol") or ""),
            str(metadata.get("start_line") or ""),
            str(metadata.get("end_line") or ""),
            content[:120],
        ]
    )
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
        if chunk_id in seen_ids:
            continue

        seen_ids.add(chunk_id)
        filtered.append(enriched)

    return filtered


def store_documents(documents: list[Document], chunk_size=500, chunk_overlap=50):
    if not documents:
        raise ValueError("No documents provided")

    vs = get_vectorstore()
    all_chunks = chunk_documents_with_ast(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    ingestible_chunks = _filter_chunks(all_chunks)

    if ingestible_chunks:
        vs.add_documents(ingestible_chunks)
    return len(ingestible_chunks)
