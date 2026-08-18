import os
import shutil
from pathlib import Path

from app.services.retrieval.hybrid import HybridRetriever
from app.services.retrieval.locks import RepoLockRegistry
from app.services.retrieval.cache import LRUCache

BASE_PATH = str(Path(__file__).resolve().parent.parent.parent.parent / "vectorstore")


class RetrievalManager:
    def __init__(self, base_path: str = BASE_PATH, max_cached: int = 5):
        self.base_path = base_path
        self.cache = LRUCache(maxsize=max_cached)
        self.locks = RepoLockRegistry()

    def _repo_path(self, repo_id: str) -> str:
        return os.path.join(self.base_path, repo_id)

    def get(self, repo_id: str) -> HybridRetriever:
        cached = self.cache.get(repo_id)
        if cached is not None:
            return cached

        path = self._repo_path(repo_id)
        bm25_path = os.path.join(path, "bm25_index.pkl")
        if os.path.isdir(path) and os.path.isfile(bm25_path):
            hybrid = HybridRetriever.load_local(path)
        else:
            hybrid = HybridRetriever()

        self.cache.put(repo_id, hybrid)
        return hybrid

    def ingest(self, repo_id: str, documents: list, save: bool = True) -> int:
        lock = self.locks.get(repo_id)
        with lock:
            hybrid = self.get(repo_id)
            hybrid.add_documents(documents)
            if save:
                hybrid.save_local_atomic(self._repo_path(repo_id))
            self.cache.put(repo_id, hybrid)
            return hybrid.num_docs

    def search(self, repo_id: str, query: str, k: int = 4):
        hybrid = self.get(repo_id)
        return hybrid.similarity_search_with_score(query, k=k)

    def save(self, repo_id: str):
        lock = self.locks.get(repo_id)
        with lock:
            hybrid = self.get(repo_id)
            hybrid.save_local_atomic(self._repo_path(repo_id))
            self.cache.put(repo_id, hybrid)

    def clear(self, repo_id: str):
        lock = self.locks.get(repo_id)
        with lock:
            path = self._repo_path(repo_id)
            if os.path.isdir(path):
                shutil.rmtree(path)
            self.cache.remove(repo_id)

    def has_repo(self, repo_id: str) -> bool:
        path = self._repo_path(repo_id)
        return os.path.isdir(path) and os.path.isfile(os.path.join(path, "bm25_index.pkl"))

    def num_docs(self, repo_id: str) -> int:
        hybrid = self.get(repo_id)
        return hybrid.num_docs


manager = RetrievalManager()
