import hashlib
import os
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from app.services.ast_chunker import chunk_documents_with_ast

_embeddings = None
_vectorstore = None

VECTORSTORE_PATH = str(Path(__file__).resolve().parent.parent.parent / "vectorstore")

class _JinaEmbeddings(Embeddings):
    def __init__(self):
        import requests as _req
        self._api_key = os.getenv("JINA_API_KEY", "")
        self._api_url = "https://api.jina.ai/v1/embeddings"
        self._session = _req.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        })
        self._last_call = 0.0

    def _call(self, texts, retries=3):
        import time
        single = isinstance(texts, str)
        texts_list = [texts] if single else texts
        for attempt in range(retries):
            now = time.time()
            since_last = now - self._last_call
            if since_last < 0.6:
                time.sleep(0.6 - since_last)
            self._last_call = time.time()
            try:
                resp = self._session.post(self._api_url, json={
                    "model": "jina-embeddings-v3",
                    "input": texts_list,
                    "normalized": True
                }, timeout=60)
                if resp.status_code == 429:
                    if attempt < retries - 1:
                        time.sleep(2 * (attempt + 1))
                        continue
                resp.raise_for_status()
                data = resp.json()
                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings[0] if single else embeddings
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    raise RuntimeError(f"Embedding call failed after {retries} retries: {e}")

    def embed_query(self, text: str):
        return self._call(text)

    def embed_documents(self, texts: list[str]):
        return self._call(texts)


class _LocalEmbeddings(Embeddings):
    def __init__(self):
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

    def embed_query(self, text: str):
        return list(self._model.embed(text))[0].tolist()

    def embed_documents(self, texts: list[str]):
        return [e.tolist() for e in self._model.embed(texts)]


def _has_real_jina_key():
    key = os.getenv("JINA_API_KEY", "")
    return bool(key) and "your_free_key" not in key


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        if _has_real_jina_key():
            _embeddings = _JinaEmbeddings()
        else:
            try:
                _embeddings = _LocalEmbeddings()
            except Exception as e:
                raise RuntimeError(
                    "No valid JINA_API_KEY found and local embeddings failed to load.\n"
                    "Option A: pip install fastembed (for local embeddings, ~150MB RAM)\n"
                    "Option B: set JINA_API_KEY (free at https://jina.ai/embeddings/)"
                ) from e
    return _embeddings

def clear_vectorstore():
    global _vectorstore
    _vectorstore = None
    if os.path.isdir(VECTORSTORE_PATH):
        import shutil
        shutil.rmtree(VECTORSTORE_PATH)
        print(f"[CLEAR] Removed vectorstore at {VECTORSTORE_PATH}")


def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        embeddings = get_embeddings()
        # Try loading existing index from disk first
        if os.path.isdir(VECTORSTORE_PATH) and os.path.isfile(os.path.join(VECTORSTORE_PATH, "index.faiss")):
            try:
                _vectorstore = FAISS.load_local(
                    VECTORSTORE_PATH,
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
                print(f"[OK] Loaded existing FAISS index ({_vectorstore.index.ntotal} vectors) from {VECTORSTORE_PATH}")
                return _vectorstore
            except Exception as e:
                print(f"[WARN] Could not load existing FAISS index, creating new empty one: {e}")
        # Fall back to fresh empty FAISS init
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


def store_documents(documents: list[Document], chunk_size=2000, chunk_overlap=50):
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
        vs.save_local(VECTORSTORE_PATH)
        print(f"[SAVE] Saved FAISS index ({vs.index.ntotal} vectors) to {VECTORSTORE_PATH}")
    return len(ingestible_chunks)
