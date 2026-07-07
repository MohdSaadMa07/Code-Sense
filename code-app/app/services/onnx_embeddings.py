import numpy as np
from sentence_transformers import SentenceTransformer

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-small-en-v1.5", backend="onnx")
    return _model


def encode(texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
    model = get_model()
    return model.encode(texts, normalize_embeddings=normalize_embeddings)
