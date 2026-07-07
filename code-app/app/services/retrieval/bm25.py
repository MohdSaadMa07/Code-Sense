import math
import os
import pickle
import uuid

from langchain_core.documents import Document

class _Docstore(dict):
    def search(self, doc_id: str):
        return self.get(doc_id)

class BM25Retriever:
    def __init__(self):
        self.docstore: _Docstore = _Docstore()
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
            # We assume metadata["chunk_id"] or uuid
            doc_id = doc.metadata.get("chunk_id", str(uuid.uuid4()))
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

    def search(self, query: str, k: int = 4):
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
        # Return docs and scores, limited to k
        return [(self.docstore[did], sc) for did, sc in sorted_docs[:k]]

    @staticmethod
    def _tokenize(text: str):
        import re
        return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
