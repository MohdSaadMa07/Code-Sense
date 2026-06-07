from llama_cpp import Llama
from app.services.storage import get_vectorstore
from pathlib import Path
import re

print("[LLAMA-RAG] Using new RAG file")

# ---------------------------
# Model Setup
# ---------------------------
_APP_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = str(_APP_DIR / "models" / "Llama-3.2-1B-Instruct-F16.gguf")

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,
            n_threads=8,
            temperature=0.2,
        )
    return _llm


# ---------------------------
# Helpers
# ---------------------------
def _is_code_query(query: str) -> bool:
    markers = [
        "function", "method", "parameters", "threshold",
        "anomaly", "cpu", "ram", "z-score"
    ]
    return any(m in query.lower() for m in markers)


def _is_code_doc(doc) -> bool:
    content = (doc.page_content or "").lower()
    path = str(doc.metadata.get("path", "")).lower()
    return path.endswith(".py") or "def " in content or "class " in content


def _rerank_docs(docs, query):
    if not _is_code_query(query):
        return docs

    code_docs = [d for d in docs if _is_code_doc(d)]
    non_code = [d for d in docs if d not in code_docs]

    # prioritize real code heavily
    return code_docs + non_code


def _build_context(docs):
    chunks = []
    for d in docs:
        content = (d.page_content or "").strip()
        if not content:
            continue

        chunks.append(
            f"[FILE]: {d.metadata.get('path','unknown')}\n{content}"
        )

    return "\n\n".join(chunks)


def _is_grounded(answer: str, context: str) -> bool:
    if not answer.strip() or not context.strip():
        return False

    context_lower = context.lower()
    words = [w.lower() for w in answer.split() if len(w) > 3]

    hits = sum(1 for w in words if w in context_lower)

    return hits >= 2  # still permissive


# ---------------------------
# Main RAG Function
# ---------------------------
def rag_query(query: str, top_k: int = 3):
    vs = get_vectorstore()
    if not vs:
        raise ValueError("Vectorstore not initialized")

    # 1. Retrieve more docs
    results = vs.similarity_search_with_score(query, k=top_k * 3)

    # 2. Deduplicate (strip-based)
    seen = set()
    docs = []
    scores = {}

    for doc, score in results:
        key = (doc.page_content or "").strip()
        if not key or key in seen:
            continue

        seen.add(key)
        docs.append(doc)
        scores[key] = float(score)

    if not docs:
        return {
            "llm_answer": "No relevant context found in repository.",
            "retrieved_chunks": []
        }

    # 3. Rerank
    docs = _rerank_docs(docs, query)

    # 4. Select
    selected_docs = docs[:top_k]

    context = _build_context(selected_docs)

    # ---------------------------
    # 🔥 Deterministic psutil extraction (improved)
    # ---------------------------
    if "psutil" in query.lower():
        extracted = set()

        for d in selected_docs:
            matches = re.findall(r"psutil\.\w+", d.page_content or "")
            extracted.update(matches)

        if extracted:
            return {
                "llm_answer": "psutil-related functions and attributes:\n- " + "\n- ".join(sorted(extracted)),
                "retrieved_chunks": [
                    {
                        "chunk": d.page_content,
                        "source": d.metadata.get("path"),
                        "score": scores.get((d.page_content or "").strip())
                    }
                    for d in selected_docs
                ]
            }

    # ---------------------------
    # 🧠 Strong Prompt
    # ---------------------------
    prompt = f"""
You are a code analysis assistant.

RULES:
- Answer using the given context only
- If code exists → explain what it does
- Mention function names clearly
- Extract whatever relevant info you can from the context
- If the context has nothing related to the question, say "No relevant information found in the codebase" — do not make up answers

CONTEXT:
{context}

QUESTION:
{query}

ANSWER:
"""

    llm = get_llm()
    response = llm(prompt, max_tokens=400)

    answer = response["choices"][0]["text"].strip()

    # cleanup weird model outputs
    answer = answer.split("CONTEXT:")[0].strip()

    # ---------------------------
    # Soft grounding (never block)
    # ---------------------------
    if not _is_grounded(answer, context):
        answer += "\n\n(Note: partially inferred from limited context)"

    # ---------------------------
    # Return
    # ---------------------------
    return {
        "llm_answer": answer,
        "retrieved_chunks": [
            {
                "chunk": d.page_content,
                "source": d.metadata.get("path"),
                "score": scores.get((d.page_content or "").strip())
            }
            for d in selected_docs
        ]
    }