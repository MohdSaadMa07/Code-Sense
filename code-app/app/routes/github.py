import gc
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.github_loader import parse_github_repo, collect_repo_files
from app.services.storage import store_documents, store_single_batch
from langchain_core.documents import Document

router = APIRouter(prefix="/github", tags=["GitHub"])

INGEST_MICRO_BATCH = 3

class GitHubIngestRequest(BaseModel):
    repo_url: str
    max_files: int = 100

@router.post("/ingest")
def ingest_github_repo(request: GitHubIngestRequest):
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

        file_count = len(files)
        sample = files[0].get("path") if files else None
        total_chunks = 0

        for i in range(0, len(files), INGEST_MICRO_BATCH):
            batch = files[i:i + INGEST_MICRO_BATCH]
            docs = [
                Document(page_content=f.get("content", ""), metadata={"path": f.get("path", "")})
                for f in batch if f.get("content", "").strip()
            ]
            if not docs:
                continue
            try:
                stored_count = store_single_batch(docs, save=(i + INGEST_MICRO_BATCH >= len(files)))
                total_chunks += stored_count
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc
            finally:
                del docs, batch
                gc.collect()

        del files
        gc.collect()

        return {
            "status": "success",
            "repo": f"{owner}/{repo}",
            "files_ingested": file_count,
            "chunks_ingested": total_chunks,
            "sample_file": sample,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected GitHub ingest failure: {exc}") from exc
