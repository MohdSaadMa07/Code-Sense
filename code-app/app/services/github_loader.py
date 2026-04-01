from urllib.parse import urlparse
import requests
import os
from app.services.storage import store_documents
from langchain_core.documents import Document

GITHUB_API_BASE = "https://api.github.com"

ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".md", ".txt", ".json", ".yml", ".yaml", ".html", ".java", ".go", ".rb", ".php", ".sql", ".sh", ".env"}
IGNORED_FOLDERS = {".github", "tests", "__tests__", "static/vendors", "static/vendor"}


def get_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fastapi-rag-app"
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


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
        print(f"STATUS: {response.status_code} | PATH: {path}")
        if response.status_code == 403:
            raise Exception("GitHub API rate limit hit or unauthorized (check token)")
        if response.status_code != 200:
            print(f"⚠️ Skipping path: {path} | Status: {response.status_code}")
            return []
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return []


def collect_repo_files(owner: str, repo: str, path: str = "", max_files: int = 500) -> list[dict]:
    collected_files = []
    items = fetch_repo_contents(owner, repo, path)

    for item in items:
        if len(collected_files) >= max_files:
            print("⚠️ Max file limit reached")
            break
        if item["type"] == "dir":
            collected_files.extend(
                collect_repo_files(owner, repo, item["path"], max_files)
            )
        elif item["type"] == "file" and is_allowed_file(item["path"]):
            try:
                file_response = requests.get(
                    item["download_url"],
                    headers=get_headers(),
                    timeout=10
                )
                if file_response.status_code == 200:
                    collected_files.append({
                        "path": item["path"],
                        "content": file_response.text
                    })
                else:
                    print(f"⚠️ Failed file: {item['path']}")
            except requests.exceptions.RequestException as e:
                print(f"❌ File fetch error: {e}")

    return collected_files


# ✅ FIX: Deduplicate by (path, content) before storing.
#         Without this, every re-ingest multiplies chunks in FAISS —
#         causing all top_k slots to return identical results.
def deduplicate_documents(documents: list[Document]) -> list[Document]:
    seen = set()
    unique = []
    for doc in documents:
        key = (doc.metadata.get("path", ""), doc.page_content)
        if key not in seen:
            seen.add(key)
            unique.append(doc)
    removed = len(documents) - len(unique)
    if removed:
        print(f"🧹 Removed {removed} duplicate document(s) before ingestion")
    return unique


def ingest_github_repo(repo_url: str) -> dict:
    try:
        owner, repo = parse_github_repo(repo_url)
        print(f"🚀 Ingesting repo: {owner}/{repo}")

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

        # ✅ FIX: Deduplicate before chunking + storing
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