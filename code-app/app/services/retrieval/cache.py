from collections import OrderedDict


class LRUCache:
    def __init__(self, maxsize: int = 5):
        self.maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()

    def get(self, key: str):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value):
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def remove(self, key: str):
        self._cache.pop(key, None)

    def __contains__(self, key: str) -> bool:
        return key in self._cache
