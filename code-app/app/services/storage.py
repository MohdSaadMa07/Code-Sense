import hashlib
import math
import os
import pickle
import uuid
from pathlib import Path

from langchain_core.documents import Document
from app.services.ast_chunker import chunk_documents_with_ast


class _BM25Index:
    def __init__(self):
        self.docstore: dict[str, Document] = {}
        self.index_to_docstore_id: dict[int, str] = {}
        self.term_doc_freq: dict[str, set[str]] = {}
        self.doc_lengths: dict[str, int] = {}
        self.avgdl = 0.0
        self.num_docs = 0
        self.k1 = 1.2
        self.b = 0.75

    @classmethod
    def load_local(cls, folder_path: str):
        with open(os.path.join(folder_path, "bm25_index.pkl"), "rb") as f:
            data = pickle.load(f)
        idx = cls()
        idx.docstore = data["docstore"]
        idx.index_to_docstore_id = {int(k): v for k, v in data["index_to_docstore_id"].items()}
        idx.term_doc_freq = {k: set(v) for k, v in data["term_doc_freq"].items()}
        idx.doc_lengths = {str(k): v for k, v in data["doc_lengths"].items()}
        idx.avgdl = data["avgdl"]
        idx.num_docs = data["num_docs"]
        return idx

    def save_local(self, folder_path: str):
        os.makedirs(folder_path, exist_ok=True)
        with open(os.path.join(folder_path, "bm25_index.pkl"), "wb") as f:
            pickle.dump({
                "docstore": self.docstore,
                "index_to_docstore_id": {str(k): v for k, v in self.index_to_docstore_id.items()},
                "term_doc_freq": {k: list(v) for k, v in self.term_doc_freq.items()},
                "doc_lengths": self.doc_lengths,
                "avgdl": self.avgdl,
                "num_docs": self.num_docs,
            }, f)

    def add_documents(self, documents: list[Document]):
        for doc in documents:
            doc_id = str(uuid.uuid4())
            idx = self.num_docs
            self.docstore[doc_id] = doc
            self.index_to_docstore_id[idx] = doc_id
            tokens = self._tokenize(doc.page_content)
            self.doc_lengths[doc_id] = len(tokens)
            for term in set(tokens):
                self.term_doc_freq.setdefault(term, set()).add(doc_id)
            self.num_docs += 1
        if self.num_docs > 0:
            self.avgdl = sum(self.doc_lengths.values()) / self.num_docs

    def similarity_search_with_score(self, query: str, k: int = 4):
        query_tokens = self._tokenize(query)
        scores: dict[str, float] = {}
        for term in set(query_tokens):
            df = len(self.term_doc_freq.get(term, set()))
            if df == 0:
                continue
            idf = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1)
            for doc_id in self.term_doc_freq.get(term, set()):
                doc_tokens = self._tokenize(self.docstore[doc_id].page_content)
                tf = doc_tokens.count(term)
                doc_len = self.doc_lengths[doc_id]
                denom = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * (tf * (self.k1 + 1)) / denom
        sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
        return [(self.docstore[did], sc) for did, sc in sorted_docs[:k]]

    def search(self, doc_id: str):
        return self.docstore.get(doc_id)

    @staticmethod
    def _tokenize(text: str):
        import re
        return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())


_embeddings = None
_vectorstore = None

VECTORSTORE_PATH = str(Path(__file__).resolve().parent.parent.parent / "vectorstore")


def clear_vectorstore():
    global _vectorstore
    _vectorstore = None
    if os.path.isdir(VECTORSTORE_PATH):
        import shutil
        shutil.rmtree(VECTORSTORE_PATH)
        print(f"[CLEAR] Removed vectorstore at {VECTORSTORE_PATH}")


def get_vectorstore():
    global _vectorstore
    if _vectorstore is None and os.path.isdir(VECTORSTORE_PATH) and os.path.isfile(os.path.join(VECTORSTORE_PATH, "bm25_index.pkl")):
        try:
            _vectorstore = _BM25Index.load_local(VECTORSTORE_PATH)
            print(f"[OK] Loaded BM25 index ({_vectorstore.num_docs} docs) from {VECTORSTORE_PATH}")
        except Exception as e:
            print(f"[WARN] Could not load existing BM25 index: {e}")
    if _vectorstore is None:
        _vectorstore = _BM25Index()
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
        print(f"[SAVE] Saved BM25 index ({vs.num_docs} docs) to {VECTORSTORE_PATH}")
    return len(ingestible_chunks)
