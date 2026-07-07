import os
import numpy as np
import onnxruntime as ort
from pathlib import Path
from tokenizers import Tokenizer

CACHE_DIR = Path(__file__).resolve().parent / ".model_cache"
ONNX_PATH = CACHE_DIR / "model.onnx"
TOKENIZER_PATH = CACHE_DIR / "tokenizer.json"

_session = None
_tokenizer = None
_CLS_TOKEN_ID = 101
_SEP_TOKEN_ID = 102
_PAD_TOKEN_ID = 0


def encode(texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
    global _session, _tokenizer

    if _session is None:
        _session = ort.InferenceSession(str(ONNX_PATH))
    if _tokenizer is None:
        _tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))

    encodings = [_tokenizer.encode(t) for t in texts]
    max_len = max(len(e.ids) for e in encodings) if encodings else 0
    max_len = min(max_len, 512)
    batch_size = len(texts)

    input_ids = np.full((batch_size, max_len), _PAD_TOKEN_ID, dtype=np.int64)
    attention_mask = np.zeros((batch_size, max_len), dtype=np.int64)
    token_type_ids = np.zeros((batch_size, max_len), dtype=np.int64)

    for i, e in enumerate(encodings):
        length = min(len(e.ids), 512)
        input_ids[i, :length] = e.ids[:length]
        attention_mask[i, :length] = 1

    ort_inputs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids,
    }
    last_hidden = _session.run(None, ort_inputs)[0]

    cls_embeddings = last_hidden[:, 0, :]

    if normalize_embeddings:
        norms = np.linalg.norm(cls_embeddings, axis=1, keepdims=True)
        cls_embeddings = cls_embeddings / np.clip(norms, 1e-12, None)

    return cls_embeddings.astype(np.float32)


def export_onnx():
    """Export the model to ONNX (requires torch + transformers)."""
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from transformers import AutoTokenizer as HFTokenizer

    os.makedirs(CACHE_DIR, exist_ok=True)

    model = ORTModelForFeatureExtraction.from_pretrained("BAAI/bge-small-en-v1.5", export=True)
    tokenizer = HFTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")

    model.save_pretrained(CACHE_DIR)
    tokenizer.save_pretrained(CACHE_DIR)
    print(f"Model exported to {CACHE_DIR}")
