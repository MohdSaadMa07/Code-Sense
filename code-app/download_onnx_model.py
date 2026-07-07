import os
import sys
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "app" / "services" / ".model_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

REPO_ID = "BAAI/bge-small-en-v1.5"

FILES = [
    ("onnx/model.onnx", "model.onnx"),
    ("tokenizer.json", "tokenizer.json"),
    ("config.json", "config.json"),
    ("special_tokens_map.json", "special_tokens_map.json"),
    ("tokenizer_config.json", "tokenizer_config.json"),
    ("vocab.txt", "vocab.txt"),
]


def _download_via_hf_hub(src: str, dst: str):
    from huggingface_hub import hf_hub_download
    import shutil
    local_path = hf_hub_download(repo_id=REPO_ID, filename=src)
    shutil.copy(local_path, dst)
    print(f"  [hf_hub] {src} -> {dst}")


def _download_via_requests(src: str, dst: str):
    import requests
    url = f"https://huggingface.co/{REPO_ID}/resolve/main/{src}"
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dst, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
    if total and downloaded != total:
        raise RuntimeError(f"Downloaded {downloaded} bytes, expected {total}")
    print(f"  [requests] {src} -> {dst} ({downloaded} bytes)")


for src, dst_name in FILES:
    dst_path = CACHE_DIR / dst_name
    if dst_path.exists():
        print(f"[SKIP] {dst_name} already exists")
        continue

    print(f"[DL] {src} ...")
    try:
        _download_via_hf_hub(src, str(dst_path))
    except Exception as e1:
        print(f"  huggingface_hub failed: {e1}")
        print(f"  falling back to direct download ...")
        try:
            _download_via_requests(src, str(dst_path))
        except Exception as e2:
            print(f"  direct download also failed: {e2}")
            sys.exit(1)

print(f"\nAll model files in {CACHE_DIR}")
