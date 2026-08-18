import os
import time
import numpy as np
import requests

JINA_API_KEY = os.getenv("JINA_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")

JINA_URL = "https://api.jina.ai/v1/embeddings"
_JINA_MODEL = "jina-embeddings-v3"
_VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-code-3")
EMBEDDING_DIM = 1024

if JINA_API_KEY:
    EMBEDDING_MODEL = _JINA_MODEL
elif VOYAGE_API_KEY:
    EMBEDDING_MODEL = _VOYAGE_MODEL
else:
    EMBEDDING_MODEL = None

_MAX_RETRIES = 4
_RETRY_DELAY = 2.0
_JINA_SUB_BATCH = 64
_JINA_RATE_WAIT = 20.0
_VOYAGE_SUB_BATCH = 8
_VOYAGE_RATE_WAIT = 30.0

_voyage_client = None


def _task_from_input_type(input_type: str) -> str:
    if input_type in ("query", "retrieval.query"):
        return "retrieval.query"
    return "retrieval.passage"


def _post_jina(texts: list[str], task: str) -> list[list[float]]:
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(
                JINA_URL,
                headers={
                    "Authorization": f"Bearer {JINA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _JINA_MODEL,
                    "input": texts,
                    "task": task,
                    "normalized": True,
                    "dimensions": EMBEDDING_DIM,
                },
                timeout=60,
            )
            if resp.status_code == 429:
                last_exc = RuntimeError("Jina rate limit exceeded")
                time.sleep(_JINA_RATE_WAIT)
                continue
            resp.raise_for_status()
            return [item["embedding"] for item in resp.json()["data"]]
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(min(_RETRY_DELAY * (2 ** attempt), 30))
    raise last_exc or RuntimeError("Jina embedding request failed after retries")


def _encode_jina(
    texts: list[str],
    normalize_embeddings: bool,
    input_type: str,
) -> np.ndarray:
    task = _task_from_input_type(input_type)
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _JINA_SUB_BATCH):
        part = list(texts[i:i + _JINA_SUB_BATCH])
        embeddings.extend(_post_jina(part, task))
    return _finalize(embeddings, normalize_embeddings)


def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        if not VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY environment variable is not set")
        import voyageai
        _voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    return _voyage_client


def _embed_voyage_part(client, texts: list[str], input_type: str) -> list[list[float]]:
    from voyageai.error import RateLimitError

    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = client.embed(
                texts,
                model=_VOYAGE_MODEL,
                input_type=input_type,
                output_dimension=EMBEDDING_DIM,
                truncation=True,
            )
            return resp.embeddings
        except RateLimitError as exc:
            last_exc = exc
            time.sleep(_VOYAGE_RATE_WAIT)
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(min(_RETRY_DELAY * (2 ** attempt), 30))
    raise last_exc or RuntimeError("Voyage embedding request failed after retries")


def _encode_voyage(
    texts: list[str],
    normalize_embeddings: bool,
    input_type: str,
) -> np.ndarray:
    client = _get_voyage_client()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _VOYAGE_SUB_BATCH):
        part = list(texts[i:i + _VOYAGE_SUB_BATCH])
        embeddings.extend(_embed_voyage_part(client, part, input_type))
    return _finalize(embeddings, normalize_embeddings)


def _finalize(embeddings: list[list[float]], normalize: bool) -> np.ndarray:
    arr = np.array(embeddings, dtype=np.float32)
    if normalize:
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr = arr / np.clip(norms, 1e-12, None)
    return arr


def encode(
    texts: list[str],
    normalize_embeddings: bool = True,
    input_type: str = "document",
) -> np.ndarray:
    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

    if JINA_API_KEY:
        return _encode_jina(texts, normalize_embeddings, input_type)
    if VOYAGE_API_KEY:
        return _encode_voyage(texts, normalize_embeddings, input_type)

    raise ValueError(
        "No embedding API key set (JINA_API_KEY or VOYAGE_API_KEY environment variables)"
    )