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


# ── Detect field extraction queries ──────────────────────────────────────────
def is_field_extraction_query(query: str) -> bool:
    """
    Detect if query is asking for database/table structure.
    If query contains: fields/columns/table/headers/shown/displayed/visible
    → use JSON extraction prompt
    Otherwise → use plain Q&A prompt
    """
    field_keywords = {
        "fields", "columns", "table", "headers",
        "shown", "displayed", "visible", "keys", "properties", "attributes", "schema", "structure"
    }
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in field_keywords)


# ── Grounding check (length-aware) ────────────────────────────────────────────
def is_grounded(answer: str, context: str) -> bool:
    context_stripped = context.strip()
    answer_stripped = answer.strip()

    # A short context cannot ground a long answer
    if len(context_stripped) < 100 and len(answer_stripped) > 150:
        return False

    answer_words = set(answer_stripped.lower().split())
    context_words = set(context_stripped.lower().split())

    if not answer_words:
        return False

    overlap = answer_words.intersection(context_words)
    ratio = len(overlap) / len(answer_words)

    # Require both high word overlap AND context has enough substance (> 50 words)
    return ratio > 0.6 and len(context_words) > 50


# ── Deduplication ─────────────────────────────────────────────────────────────
def deduplicate_docs(docs: list[Document]) -> list[Document]:
    """Remove duplicate documents by page_content"""
    seen = set()
    unique = []
    for doc in docs:
        if doc.page_content not in seen:
            seen.add(doc.page_content)
            unique.append(doc)
    return unique


# ── Drop junk chunks too short to ground any answer ──────────────────────────
def filter_short_chunks(docs: list[Document]) -> list[Document]:
    """Filter out chunks shorter than MIN_CHUNK_LENGTH"""
    return [doc for doc in docs if len(doc.page_content.strip()) >= MIN_CHUNK_LENGTH]


# ── Format chunks for API response ───────────────────────────────────────────
def _format_chunks(docs: list[Document]) -> list[dict]:
    return [
        {
            "chunk": doc.page_content,
            "score": getattr(doc, "score", None),
            "source": doc.metadata.get("path", "unknown"),
            "metadata": doc.metadata,
        }
        for doc in docs
    ]


# ── Main RAG pipeline ─────────────────────────────────────────────────────────
def rag_query(query: str, top_k: int = 3) -> dict:
    """
    Hybrid RAG pipeline:
      1. Retrieve 3× candidates to survive dedup/filter losses
      2. Deduplicate by page_content
      3. Extract table headers from ALL deduped docs (deterministic)
      4. Filter out short chunks (< 80 chars)
      5. Call LLM only if quality context remains
    """
    vs = get_vectorstore()
    if vs is None:
        raise ValueError("Vectorstore not initialised. Ingest documents first.")

    # Step 1: Retrieve extra candidates (3×) to compensate for dedup/filter losses
    raw_docs: list[Document] = vs.similarity_search(query, k=top_k * 3)

    # Step 2: Deduplicate by page_content
    docs = deduplicate_docs(raw_docs)

    # Step 3: Deterministic table extraction on ALL deduped docs
    all_content = "\n\n".join(doc.page_content for doc in docs)
    table_headers = extract_table_headers(all_content)
    if table_headers:
        return {
            "llm_answer": f"Table columns found: {', '.join(table_headers)}",
            "retrieved_chunks": _format_chunks(docs[:top_k]),
        }

    # Step 4: Filter out short chunks before LLM
    quality_docs = filter_short_chunks(docs)

    # Step 5: Bail if no quality context survived
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

    # ── Choose prompt based on query type ──────────────────────────────────────
    if is_field_extraction_query(query):
        # Schema extraction prompt (JSON format for field names)
        prompt = f"""You are a database schema analyzer. Extract field/column names from the provided code context.

RULES:
1. Look for class definitions, database models, or data structures
2. List all field/column names found
3. If no schema found, respond with: NOT FOUND IN CONTEXT
4. Do not make up fields

PROVIDED CODE CONTEXT:
{context}

QUERY:
{query}

FIELDS/COLUMNS:"""
    else:
        # Fix 30: Simplified Q&A prompt template
        prompt = f"""Answer ONLY using the context. If not found say NOT FOUND IN CONTEXT. Do not repeat the context.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

    llm = get_llm()
    # Fix 27: Add stop sequences including "PLEASE" to prevent overflow
    response = llm(
        prompt,
        max_tokens=512,
        stop=["[FILE]:", "CONTEXT:", "QUERY:", "PLEASE"]
    )
    raw_output = response["choices"][0]["text"].strip()

    # Strip everything after any stop sequence marker
    for stop_marker in ["[FILE]:", "CONTEXT:", "QUERY:", "PLEASE"]:
        if stop_marker in raw_output:
            raw_output = raw_output[:raw_output.index(stop_marker)].strip()
            break

    answer = raw_output

    # Fix 29: For Q&A (non-field) queries, skip is_grounded() check
    # Just return the stripped answer
    if not is_field_extraction_query(query):
        return {
            "llm_answer": answer,
            "retrieved_chunks": _format_chunks(llm_docs),
        }

    # For field extraction queries, apply grounding check
    if len(context.strip()) < 200 and len(answer) > 400 and answer != "NOT FOUND IN CONTEXT":
        if not is_grounded(answer, context):
            return {
                "llm_answer": "NOT FOUND IN CONTEXT",
                "retrieved_chunks": _format_chunks(llm_docs),
            }

    return {
        "llm_answer": answer,
        "retrieved_chunks": _format_chunks(llm_docs),
    }