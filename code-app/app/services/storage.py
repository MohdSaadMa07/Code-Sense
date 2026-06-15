import hashlib
import os
import pickle
import uuid
from pathlib import Path

import faiss
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from app.services.ast_chunker import chunk_documents_with_ast


class _FAISS:
    def __init__(self, embedding_function, index, docstore, index_to_docstore_id):
        self.embedding_function = embedding_function
        self.index = index
        self.docstore = docstore
        self.index_to_docstore_id = index_to_docstore_id

    @classmethod
    def load_local(cls, folder_path, embeddings, allow_dangerous_deserialization=True):
        index = faiss.read_index(os.path.join(folder_path, "index.faiss"))
        with open(os.path.join(folder_path, "docstore.pkl"), "rb") as f:
            docstore = pickle.load(f)
        with open(os.path.join(folder_path, "id_map.pkl"), "rb") as f:
            index_to_docstore_id = pickle.load(f)
        return cls(embeddings, index, docstore, index_to_docstore_id)

    @classmethod
    def from_empty(cls, embeddings, dimension):
        index = faiss.IndexFlatL2(dimension)
        return cls(embeddings, index, {}, {})

    def save_local(self, folder_path):
        os.makedirs(folder_path, exist_ok=True)
        faiss.write_index(self.index, os.path.join(folder_path, "index.faiss"))
        with open(os.path.join(folder_path, "docstore.pkl"), "wb") as f:
            pickle.dump(self.docstore, f)
        with open(os.path.join(folder_path, "id_map.pkl"), "wb") as f:
            pickle.dump(self.index_to_docstore_id, f)

    def add_documents(self, documents):
        texts = [d.page_content for d in documents]
        vectors = self.embedding_function.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in documents]
        start = self.index.ntotal
        self.index.add(np.array(vectors, dtype=np.float32))
        for i, doc in enumerate(documents):
            self.docstore[ids[i]] = doc
            self.index_to_docstore_id[start + i] = ids[i]

    def similarity_search_with_score(self, query, k=4):
        vec = self.embedding_function.embed_query(query)
        scores, indices = self.index.search(np.array([vec], dtype=np.float32), k)
        docs = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            doc_id = self.index_to_docstore_id.get(int(idx))
            if doc_id and doc_id in self.docstore:
                docs.append((self.docstore[doc_id], float(score)))
        return docs

_embeddings = None
_vectorstore = None

VECTORSTORE_PATH = str(Path(__file__).resolve().parent.parent.parent / "vectorstore")

class _GeminiEmbeddings(Embeddings):
    def __init__(self):
        self._api_key = os.getenv("GEMINI_API_KEY", "")

    def _embed(self, text):
        import requests
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/text-embedding-004:embedContent?key={self._api_key}",
            json={"model": "models/text-embedding-004", "content": {"parts": [{"text": text}]}},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]

    def _batch_embed(self, texts):
        import requests
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/text-embedding-004:batchEmbedContents?key={self._api_key}",
            json={"requests": [
                {"model": "models/text-embedding-004", "content": {"parts": [{"text": t}]}}
                for t in texts
            ]},
            timeout=60
        )
        resp.raise_for_status()
        return [e["values"] for e in resp.json()["embeddings"]]

    def embed_query(self, text: str):
        return self._embed(text)

    def embed_documents(self, texts: list[str]):
        return self._batch_embed(texts)


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key or "your_key" in key:
            try:
                from fastembed import TextEmbedding
                class _Local(Embeddings):
                    def __init__(self):
                        self._model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
                    def embed_query(self, text):
                        return list(self._model.embed(text))[0].tolist()
                    def embed_documents(self, texts):
                        return [e.tolist() for e in self._model.embed(texts)]
                _embeddings = _Local()
            except Exception:
                raise RuntimeError("Set GEMINI_API_KEY (free at https://aistudio.google.com/) or install fastembed")
        else:
            _embeddings = _GeminiEmbeddings()
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
                _vectorstore = _FAISS.load_local(
                    VECTORSTORE_PATH,
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
                print(f"[OK] Loaded existing FAISS index ({_vectorstore.index.ntotal} vectors) from {VECTORSTORE_PATH}")
                return _vectorstore
            except Exception as e:
                print(f"[WARN] Could not load existing FAISS index, creating new empty one: {e}")
        dummy_embedding = embeddings.embed_query(" ")
        _vectorstore = _FAISS.from_empty(embeddings, len(dummy_embedding))
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
