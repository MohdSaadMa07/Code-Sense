from fastapi import APIRouter
from pydantic import BaseModel
from app.services.github_loader import parse_github_repo, collect_repo_files
from app.services.storage import store_documents
from langchain_core.documents import Document

router = APIRouter(prefix="/github", tags=["GitHub"])

class GitHubIngestRequest(BaseModel):
    repo_url: str

@router.post("/ingest")
def ingest_github_repo(request: GitHubIngestRequest):
    """
    Accepts a GitHub repo URL, recursively fetches files,
    pushes them into FAISS, and returns ingestion stats.
    """
    # 1️⃣ Parse owner/repo from URL
    owner, repo = parse_github_repo(request.repo_url)

    # 2️⃣ Recursively collect files
    files = collect_repo_files(owner, repo)

    # 3️⃣ Convert to Documents for FAISS
    documents = [
        Document(page_content=f["content"], metadata={"path": f["path"]})
        for f in files
        if f["content"].strip()
    ]

    # 4️⃣ Store in FAISS
    stored_count = store_documents(documents)

    # 5️⃣ Return summary
    return {
        "status": "success",
        "repo": f"{owner}/{repo}",
        "files_ingested": len(files),
        "chunks_ingested": stored_count,
        "sample_file": files[0]["path"] if files else None
    }
