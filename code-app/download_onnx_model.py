import os
import shutil
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "app" / "services" / ".model_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

REPO_ID = "BAAI/bge-small-en-v1.5"

FILES = [
    "onnx/model.onnx",
    "tokenizer.json",
    "config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "vocab.txt",
]

for src in FILES:
    try:
        from huggingface_hub import hf_hub_download
        local_path = hf_hub_download(repo_id=REPO_ID, filename=src)
        dst_name = os.path.basename(src)
        dst_path = CACHE_DIR / dst_name
        shutil.copy(local_path, dst_path)
        print(f"[OK] {src} -> {dst_path}")
    except Exception as e:
        print(f"[WARN] Could not download {src}: {e}")

print(f"Model files downloaded to {CACHE_DIR}")
