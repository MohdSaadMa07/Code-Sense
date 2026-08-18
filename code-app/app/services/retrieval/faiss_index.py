import os
import pickle
import faiss
import numpy as np

from langchain_core.documents import Document

if os.getenv("JINA_API_KEY") or os.getenv("VOYAGE_API_KEY"):
    from app.services.remote_embeddings import (
        encode as get_embeddings,
        EMBEDDING_DIM,
        EMBEDDING_MODEL,
    )
else:
    from app.services.onnx_embeddings import encode as get_embeddings
    EMBEDDING_DIM = 384
    EMBEDDING_MODEL = "bge-small-en-v1.5"

class FAISSRetriever:
    def __init__(self, dimension=EMBEDDING_DIM, docstore: dict | None = None):
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(self.dimension)
        self.faiss_id_to_doc_id: dict[int, str] = {}
        self.docstore = docstore if docstore is not None else {}

    @classmethod
    def load_local(cls, folder_path: str):
        idx = cls()
        index_path = os.path.join(folder_path, "faiss.index")
        mapping_path = os.path.join(folder_path, "faiss_mapping.pkl")

        if os.path.exists(index_path) and os.path.exists(mapping_path):
            idx.index = faiss.read_index(index_path)
            if idx.index.d != EMBEDDING_DIM:
                print(f"[FAISS] index dimension {idx.index.d} != {EMBEDDING_DIM}; rebuilding index")
                return cls()
            with open(mapping_path, "rb") as f:
                data = pickle.load(f)
                if data.get("embedding_model") != EMBEDDING_MODEL:
                    print(f"[FAISS] index embedding model {data.get('embedding_model')} != {EMBEDDING_MODEL}; rebuilding index")
                    return cls()
                idx.faiss_id_to_doc_id = data.get("faiss_id_to_doc_id", {})
                idx.docstore = data.get("docstore", {})
        return idx

    def save_local(self, folder_path: str):
        os.makedirs(folder_path, exist_ok=True)
        faiss.write_index(self.index, os.path.join(folder_path, "faiss.index"))
        with open(os.path.join(folder_path, "faiss_mapping.pkl"), "wb") as f:
            pickle.dump({
                "faiss_id_to_doc_id": self.faiss_id_to_doc_id,
                "docstore": self.docstore,
                "embedding_model": EMBEDDING_MODEL
            }, f)

    def add_documents(self, documents: list[Document]):
        if not documents:
            return 0

        texts = [doc.page_content for doc in documents]

        try:
            embeddings = get_embeddings(texts, normalize_embeddings=True, input_type="document")
        except Exception as e:
            print(f"[FAISS] embedding failed, skipping semantic add ({len(documents)} chunks): {e}")
            return 0

        start_id = self.index.ntotal
        for i, doc in enumerate(documents):
            doc_id = doc.metadata.get("chunk_id")
            self.faiss_id_to_doc_id[start_id + i] = doc_id
            self.docstore[doc_id] = doc

        self.index.add(np.array(embeddings, dtype=np.float32))
        return len(documents)

    def search(self, query: str, k: int = 4):
        if self.index.ntotal == 0:
            return []

        try:
            query_vector = get_embeddings([query], normalize_embeddings=True, input_type="query").astype(np.float32)
        except Exception as e:
            print(f"[FAISS] embedding failed, skipping semantic search: {e}")
            return []

        distances, indices = self.index.search(query_vector, k)

        results = []
        for j, idx in enumerate(indices[0]):
            if idx != -1 and idx in self.faiss_id_to_doc_id:
                doc_id = self.faiss_id_to_doc_id[idx]
                score = distances[0][j]
                doc = self.docstore.get(doc_id)
                if doc:
                    results.append((doc, score))

        return results