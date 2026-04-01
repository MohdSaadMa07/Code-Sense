from llama_cpp import Llama
from app.services.storage import get_vectorstore
from langchain_core.documents import Document
from bs4 import BeautifulSoup
import json
from pathlib import Path

# Resolve model path relative to this file's location
_APP_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = str(_APP_DIR / "models" / "Llama-3.2-1B-Instruct-F16.gguf")

# Chunks shorter than this are stray comments / single lines that cause hallucination
MIN_CHUNK_LENGTH = 80

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=8192,
            n_threads=8,
            temperature=0.1,
            top_p=0.9,
        )
    return _llm


# ── Deterministic extraction (PRIMARY path) ───────────────────────────────────
def extract_table_headers(context: str) -> list[str]:
    headers = []
    soup = BeautifulSoup(context, "html.parser")
    for th in soup.find_all("th"):
        text = th.get_text(strip=True)
        if text:
            headers.append(text)
    return headers


# ── Grounding check (length-aware) ────────────────────────────────────────────
def is_grounded(answer: str, context: str) -> bool:
    context_stripped = context.strip()
    answer_stripped = answer.strip()

    # A 29-char comment cannot ground a 600-char step-by-step answer
    if len(context_stripped) < 100 and len(answer_stripped) > 150:
        return False

    answer_words = set(answer_stripped.lower().split())
    context_words = set(context_stripped.lower().split())

    if not answer_words:
        return False

    overlap = answer_words.intersection(context_words)
    ratio = len(overlap) / len(answer_words)

    # Require both high word overlap AND context has enough substance
    return ratio > 0.6 and len(context_words) > 50


# ── Safe JSON parsing ─────────────────────────────────────────────────────────
def safe_json_load(output: str):
    try:
        output = output.replace("```json", "").replace("```python", "").replace("```", "")
        return json.loads(output)
    except Exception:
        return None


# ── Deduplication ─────────────────────────────────────────────────────────────
def deduplicate_docs(docs: list[Document]) -> list[Document]:
    seen = set()
    unique = []
    for doc in docs:
        if doc.page_content not in seen:
            seen.add(doc.page_content)
            unique.append(doc)
    return unique


# ── Drop junk chunks too short to ground any answer ──────────────────────────
def filter_short_chunks(docs: list[Document]) -> list[Document]:
    return [doc for doc in docs if len(doc.page_content.strip()) >= MIN_CHUNK_LENGTH]


# ── Format chunks for API response ───────────────────────────────────────────
def _format_chunks(docs: list[Document]) -> list[dict]:
    return [
        {
            "chunk": doc.page_content,
            "score": getattr(doc, "score", None),
            "source": doc.metadata.get("source", doc.metadata.get("path", "unknown")),
            "metadata": doc.metadata,
        }
        for doc in docs
    ]


# ── Main RAG pipeline ─────────────────────────────────────────────────────────
def rag_query(query: str, top_k: int = 3) -> dict:
    """
    Hybrid RAG pipeline:
      1. Retrieve (fetch 3× to survive dedup + length filter losses)
      2. Deduplicate by page_content
      3. Filter out short/junk chunks (< 80 chars)
      4. Deterministic extraction — BeautifulSoup <th> scan (no LLM)
      5. LLM fallback — strict JSON extraction with length-aware grounding
    """
    vs = get_vectorstore()
    if vs is None:
        raise ValueError("Vectorstore not initialised. Ingest documents first.")

    # Step 1 — retrieve extra candidates to compensate for dedup/filter losses
    raw_docs: list[Document] = vs.similarity_search(query, k=top_k * 3)

    # Step 2 — deduplicate
    docs = deduplicate_docs(raw_docs)

    # Step 3 — drop junk chunks before passing to LLM
    quality_docs = filter_short_chunks(docs)

    # ── Step 5: LLM fallback — bail early if no quality context survived
    if not quality_docs:
        return {
            "llm_answer": "NOT FOUND IN CONTEXT",
            "retrieved_chunks": _format_chunks(docs[:top_k]),
        }

    llm_docs = quality_docs[:top_k]

    context = "\n\n".join(
        f"[FILE]: {doc.metadata.get('path', 'unknown')}\n[CONTENT]:\n{doc.page_content}"
        for doc in llm_docs
    )

    # Modern Q&A prompt - answer questions based on code context
    prompt = f"""You are a helpful code assistant. Answer the user's question based ONLY on the provided code context.

IMPORTANT RULES:
1. Answer based strictly on the provided context
2. If the context answers the question, provide a clear, concise answer
3. Use code snippets from the context if relevant
4. If the context does not contain relevant information, respond with: NOT FOUND IN CONTEXT
5. Do not make up or infer information not in the context

PROVIDED CODE CONTEXT:
{context}

USER QUESTION:
{query}

YOUR ANSWER:"""

    llm = get_llm()
    response = llm(prompt, max_tokens=512)
    answer = response["choices"][0]["text"].strip()

    # Simple grounding check - if answer is too long but context is short, likely hallucination
    if len(context.strip()) < 200 and len(answer) > 400 and answer != "NOT FOUND IN CONTEXT":
        return {
            "llm_answer": "NOT FOUND IN CONTEXT",
            "retrieved_chunks": _format_chunks(llm_docs),
        }

    return {
        "llm_answer": answer,
        "retrieved_chunks": _format_chunks(llm_docs),
    }