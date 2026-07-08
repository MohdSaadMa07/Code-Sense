import os
import numpy as np
import requests

JINA_API_KEY = os.getenv("JINA_API_KEY")
JINA_URL = "https://api.jina.ai/v1/embeddings"
_MODEL = "jina-embeddings-v3"


def encode(texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
    if not JINA_API_KEY:
        raise ValueError("JINA_API_KEY environment variable is not set")

    resp = requests.post(
        JINA_URL,
        headers={
            "Authorization": f"Bearer {JINA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"input": texts, "model": _MODEL},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    embeddings = np.array([d["embedding"] for d in data["data"]], dtype=np.float32)

    if normalize_embeddings:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.clip(norms, 1e-12, None)

    return embeddings
