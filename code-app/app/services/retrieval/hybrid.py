import os
from typing import List, Tuple
from langchain_core.documents import Document

from app.services.retrieval.bm25 import BM25Retriever, _Docstore
from app.services.retrieval.faiss_index import FAISSRetriever

class HybridRetriever:
    def __init__(self):
        self._shared_docstore = _Docstore()
        self.bm25 = BM25Retriever(docstore=self._shared_docstore)
        self.faiss = FAISSRetriever(docstore=self._shared_docstore)

    @property
    def num_docs(self):
        # We can rely on BM25 num_docs as the ground truth for total doc count
        return self.bm25.num_docs

    @property
    def docstore(self):
        return self.faiss.docstore

    @property
    def index_to_docstore_id(self):
        return self.faiss.faiss_id_to_doc_id

    @classmethod
    def load_local(cls, folder_path: str):
        idx = cls()
        idx.bm25 = BM25Retriever.load_local(folder_path)
        idx.faiss = FAISSRetriever.load_local(folder_path)
        idx._shared_docstore = idx.bm25.docstore
        idx.faiss.docstore = idx.bm25.docstore
        return idx

    def save_local(self, folder_path: str):
        self.bm25.save_local(folder_path)
        self.faiss.save_local(folder_path)

    def save_local_atomic(self, folder_path: str):
        import tempfile
        os.makedirs(folder_path, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(dir=folder_path)
        try:
            self.bm25.save_local(tmp_dir)
            self.faiss.save_local(tmp_dir)
            for fname in ("bm25_index.pkl", "faiss.index", "faiss_mapping.pkl"):
                src = os.path.join(tmp_dir, fname)
                dst = os.path.join(folder_path, fname)
                if os.path.exists(src):
                    os.replace(src, dst)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def add_documents(self, documents: list[Document]):
        # The document needs a stable id so both retrievers reference the same doc
        # Ensure all docs have chunk_id before passing them down
        import uuid
        for doc in documents:
            if "chunk_id" not in doc.metadata:
                doc.metadata["chunk_id"] = str(uuid.uuid4())
                
        self.bm25.add_documents(documents)
        self.faiss.add_documents(documents)

    def similarity_search_with_score(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        # Fetch more candidates from each retriever before fusion
        retrieve_k = max(k * 2, 60)
        
        bm25_results = self.bm25.search(query, k=retrieve_k)
        faiss_results = self.faiss.search(query, k=retrieve_k)
        
        return self._rrf(bm25_results, faiss_results, top_k=k)

    def _rrf(self, results1: List[Tuple[Document, float]], results2: List[Tuple[Document, float]], top_k: int = 4, k_param: int = 60) -> List[Tuple[Document, float]]:
        scores = {}
        doc_store = {}

        for rank, (doc, _) in enumerate(results1):
            doc_id = doc.metadata.get("chunk_id")
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k_param + rank + 1)
            doc_store[doc_id] = doc

        for rank, (doc, _) in enumerate(results2):
            doc_id = doc.metadata.get("chunk_id")
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k_param + rank + 1)
            doc_store[doc_id] = doc

        sorted_docs = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        
        # Return top_k combined documents with their RRF score
        return [(doc_store[doc_id], score) for doc_id, score in sorted_docs[:top_k]]
