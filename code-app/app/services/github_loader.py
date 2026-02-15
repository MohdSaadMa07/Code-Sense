from urllib.parse import urlparse
import requests
import os
from app.services.storage import store_documents, Document

GITHUB_API_BASE = "https://api.github.com"

# Allowed extensions for ingestion
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".md", ".txt", ".json", ".yml", ".yaml"}
IGNORED_FOLDERS = {".github", "tests", "__tests__"}


def parse_github_repo(url: str) -> tuple[str, str]:
    """
    Extract owner and repo name from GitHub URL
    """
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    return parts[0], parts[1]


def is_allowed_file(path: str) -> bool:
    """
    Decide if a file should be ingested:
    - Skip ignored folders
    - Only allow files with ALLOWED_EXTENSIONS
    - Skip hidden files/folders
    """
    normalized_path = path.replace("\\", "/").lower()

    # Skip ignored folders
    for folder in IGNORED_FOLDERS:
        if normalized_path.startswith(folder + "/"):
            return False

    # Skip hidden folders/files
    parts = normalized_path.split("/")
    if any(part.startswith(".") for part in parts[:-1]):
        return False

    # Check extension
    _, ext = os.path.splitext(normalized_path)
    return ext in ALLOWED_EXTENSIONS


def fetch_repo_contents(owner: str, repo: str, path: str = ""):
    """
    Fetch files/folders from a GitHub repo path
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch repository contents: {url}")
    return response.json()


def collect_repo_files(owner: str, repo: str, path: str = "") -> list[dict]:
    """
    Recursively collect file contents from a GitHub repo
    """
    collected_files = []
    items = fetch_repo_contents(owner, repo, path)

    for item in items:
        if item["type"] == "dir":
            collected_files.extend(collect_repo_files(owner, repo, item["path"]))
        elif item["type"] == "file" and is_allowed_file(item["path"]):
            file_response = requests.get(item["download_url"])
            if file_response.status_code == 200:
                collected_files.append({
                    "path": item["path"],
                    "content": file_response.text
                })

    return collected_files


def ingest_github_repo(repo_url: str) -> dict:
    """
    Fetch files from GitHub repo, convert to Documents, and store in FAISS
    """
    owner, repo = parse_github_repo(repo_url)
    files = collect_repo_files(owner, repo)

    documents = [Document(page_content=f["content"]) for f in files]
    chunks_ingested = store_documents(documents)

    return {
        "status": "success",
        "repo": f"{owner}/{repo}",
        "files_ingested": len(files),
        "chunks_ingested": chunks_ingested
    }
