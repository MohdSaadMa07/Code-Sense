import io, sys
if isinstance(sys.stdout, io.TextIOWrapper) and sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if isinstance(sys.stderr, io.TextIOWrapper) and sys.stderr.encoding and "utf" not in sys.stderr.encoding.lower():
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import os
from app.services.storage import store_documents
from langchain_core.documents import Document

GITHUB_API_BASE = "https://api.github.com"

ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".md", ".txt", ".json", ".yml", ".yaml", ".html", ".java", ".go", ".rb", ".php", ".sql", ".sh", ".env"}
IGNORED_FOLDERS = {".github", "tests", "__tests__", "static/vendors", "static/vendor"}


def get_headers():
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fastapi-rag-app"
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def parse_github_repo(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    return parts[0], parts[1]


def is_allowed_file(path: str) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    for folder in IGNORED_FOLDERS:
        if normalized_path.startswith(folder + "/"):
            return False
    parts = normalized_path.split("/")
    if any(part.startswith(".") for part in parts[:-1]):
        return False
    _, ext = os.path.splitext(normalized_path)
    return ext in ALLOWED_EXTENSIONS


def fetch_repo_contents(owner, repo, path=""):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        if response.status_code == 403:
            return []
        if response.status_code == 404:
            return []
        if response.status_code != 200:
            return []
        return response.json()
    except requests.exceptions.RequestException:
        return []


def _download_file(item: dict) -> dict | None:
    try:
        resp = requests.get(item["download_url"], headers=get_headers(), timeout=15)
        if resp.status_code != 200:
            return None
        raw = resp.content
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        return {"path": item["path"], "content": text}
    except requests.exceptions.RequestException:
        return None


def collect_repo_files(owner: str, repo: str, path: str = "", max_files: int = 500) -> list[dict]:
    file_items = []
    _gather_file_items(owner, repo, path, max_files, file_items)

    collected = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(_download_file, item): item for item in file_items}
        for fut in as_completed(futs):
            result = fut.result()
            if result:
                collected.append(result)
    return collected


def _gather_file_items(owner: str, repo: str, path: str, max_files: int, out: list):
    items = fetch_repo_contents(owner, repo, path)
    for item in items:
        if len(out) >= max_files:
            return
        if item["type"] == "dir":
            _gather_file_items(owner, repo, item["path"], max_files, out)
        elif item["type"] == "file" and is_allowed_file(item["path"]):
            out.append(item)


def deduplicate_documents(documents: list[Document]) -> list[Document]:
    seen = set()
    unique = []
    for doc in documents:
        key = (doc.metadata.get("path", ""), doc.page_content)
        if key not in seen:
            seen.add(key)
            unique.append(doc)
    return unique


def ingest_github_repo(repo_url: str) -> dict:
    try:
        owner, repo = parse_github_repo(repo_url)

        files = collect_repo_files(owner, repo)

        if not files:
            return {
                "status": "error",
                "message": "No files fetched (rate limit / invalid repo / auth issue)"
            }

        documents = [
            Document(page_content=f["content"], metadata={"path": f["path"]})
            for f in files
        ]

        documents = deduplicate_documents(documents)

        chunks_ingested = store_documents(documents)

        return {
            "status": "success",
            "repo": f"{owner}/{repo}",
            "files_ingested": len(files),
            "chunks_ingested": chunks_ingested,
            "sample_file": files[0]["path"] if files else None,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
