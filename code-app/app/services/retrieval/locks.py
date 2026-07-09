import threading


class RepoLockRegistry:
    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}
        self._global = threading.Lock()

    def get(self, repo_id: str) -> threading.Lock:
        if repo_id not in self._locks:
            with self._global:
                if repo_id not in self._locks:
                    self._locks[repo_id] = threading.Lock()
        return self._locks[repo_id]
