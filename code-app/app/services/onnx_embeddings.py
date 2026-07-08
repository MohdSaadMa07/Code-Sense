import os
import threading
import requests
import numpy as np
import onnxruntime as ort
from pathlib import Path
from tokenizers import Tokenizer

CACHE_DIR = Path(__file__).resolve().parent / "model_cache"
ONNX_PATH = CACHE_DIR / "model.onnx"
TOKENIZER_PATH = CACHE_DIR / "tokenizer.json"

_session = None
_tokenizer = None
_download_lock = threading.Lock()
_download_done = threading.Event()
_PAD_TOKEN_ID = 0

def _make_session_opts():
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    opts.enable_cpu_mem_arena = False
    opts.enable_mem_pattern = False
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opts.enable_profiling = False
    return opts


_FILES = [
    ("onnx/model.onnx", "model.onnx"),
    ("tokenizer.json", "tokenizer.json"),
    ("config.json", "config.json"),
    ("special_tokens_map.json", "special_tokens_map.json"),
    ("tokenizer_config.json", "tokenizer_config.json"),
    ("vocab.txt", "vocab.txt"),
]


def _ensure_model():
    if _download_done.is_set():
        return
    if ONNX_PATH.exists():
        _download_done.set()
        return
    with _download_lock:
        if _download_done.is_set():
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for src, dst_name in _FILES:
            dst = CACHE_DIR / dst_name
            if dst.exists():
                continue
            url = f"https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/{src}"
            print(f"[ONNX] Downloading {src} ...")
            resp = requests.get(url, stream=True, timeout=300)
            resp.raise_for_status()
            with open(dst, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"[ONNX] Saved {dst_name}")
            del resp
        _download_done.set()
        import gc; gc.collect()


def encode(texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
    global _session, _tokenizer

    _ensure_model()

    if _session is None:
        _session = ort.InferenceSession(
            str(ONNX_PATH),
            providers=["CPUExecutionProvider"],
            sess_options=_make_session_opts(),
        )
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
