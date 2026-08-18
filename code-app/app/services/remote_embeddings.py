import os
import time
import numpy as np

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
_MODEL = os.getenv("VOYAGE_MODEL", "voyage-code-3")
EMBEDDING_DIM = 1024

_MAX_RETRIES = 6
_RETRY_DELAY = 2.0
_RATE_LIMIT_WAIT = 30.0
_SUB_BATCH = 8

_client = None


def _get_client():
    global _client
    if _client is None:
        if not VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY environment variable is not set")
        import voyageai
        _client = voyageai.Client(api_key=VOYAGE_API_KEY)
    return _client


def _embed_part(client, texts: list[str], input_type: str) -> list[list[float]]:
    from voyageai.error import RateLimitError

    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = client.embed(
                texts,
                model=_MODEL,
                input_type=input_type,
                output_dimension=EMBEDDING_DIM,
                truncation=True,
            )
            return resp.embeddings
        except RateLimitError as exc:
            last_exc = exc
            time.sleep(_RATE_LIMIT_WAIT)
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(min(_RETRY_DELAY * (2 ** attempt), 30))

    raise last_exc or RuntimeError("Voyage embedding request failed after retries")


def encode(
    texts: list[str],
    normalize_embeddings: bool = True,
    input_type: str = "document",
) -> np.ndarray:
    if not VOYAGE_API_KEY:
        raise ValueError("VOYAGE_API_KEY environment variable is not set")

    client = _get_client()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _SUB_BATCH):
        part = list(texts[i:i + _SUB_BATCH])
        embeddings.extend(_embed_part(client, part, input_type))

    arr = np.array(embeddings, dtype=np.float32)

    if normalize_embeddings:
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr = arr / np.clip(norms, 1e-12, None)

    return arr