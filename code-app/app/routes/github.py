import gc
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.github_loader import parse_github_repo, collect_repo_files
from app.services.storage import store_documents
from langchain_core.documents import Document

router = APIRouter(prefix="/github", tags=["GitHub"])

class GitHubIngestRequest(BaseModel):
    repo_url: str
    max_files: int = 500

@router.post("/ingest")
def ingest_github_repo(request: GitHubIngestRequest):
    """
    Accepts a GitHub repo URL, recursively fetches files,
    pushes them into FAISS, and returns ingestion stats.
    """
    try:
        try:
            owner, repo = parse_github_repo(request.repo_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        try:
            files = collect_repo_files(owner, repo, max_files=request.max_files)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"GitHub fetch failed: {exc}") from exc

        if not files:
            raise HTTPException(
                status_code=503,
                detail="No files fetched from GitHub. Check network access, repo URL, or API rate limits.",
            )

        documents = [
            Document(page_content=f.get("content", ""), metadata={"path": f.get("path", "")})
            for f in files
            if f.get("content", "").strip()
        ]

        if not documents:
            raise HTTPException(
                status_code=422,
                detail="No ingestible content found in fetched repository files.",
            )

        try:
            stored_count = store_documents(documents)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Ingestion failed while indexing documents: {exc}") from exc

        sample = files[0].get("path") if files else None
        file_count = len(files)
        del files, documents
        gc.collect()

        return {
            "status": "success",
            "repo": f"{owner}/{repo}",
            "files_ingested": file_count,
            "chunks_ingested": stored_count,
            "sample_file": sample,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected GitHub ingest failure: {exc}") from exc
