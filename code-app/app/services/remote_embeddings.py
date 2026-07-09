import os
import time
import numpy as np
import requests

JINA_API_KEY = os.getenv("JINA_API_KEY")
JINA_URL = "https://api.jina.ai/v1/embeddings"
_MODEL = "jina-embeddings-v3"
EMBEDDING_DIM = 1024

_MAX_RETRIES = 5
_RETRY_DELAY = 2.0


def encode(texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
    if not JINA_API_KEY:
        raise ValueError("JINA_API_KEY environment variable is not set")

    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(
                JINA_URL,
                headers={
                    "Authorization": f"Bearer {JINA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"input": texts, "model": _MODEL},
                timeout=120,
            )

            if resp.status_code == 429:
                wait = _RETRY_DELAY * (2 ** attempt)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            embeddings = np.array([d["embedding"] for d in data["data"]], dtype=np.float32)

            if normalize_embeddings:
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = embeddings / np.clip(norms, 1e-12, None)

            return embeddings

        except requests.RequestException as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (2 ** attempt))

    raise last_exc or RuntimeError("Embedding request failed after retries")
