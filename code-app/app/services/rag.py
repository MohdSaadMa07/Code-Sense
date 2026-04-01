from llama_cpp import Llama
from app.services.storage import get_vectorstore
import traceback

# Load model ONCE (global, safe)
llm = Llama(
    model_path="app/models/Llama-3.2-1B-Instruct-F16.gguf",  # <- updated path
    n_threads=4,
    n_ctx=2048
)


def _is_code_intent(query: str) -> bool:
    text = query.lower()
    markers = ["def ", "class ", "function", "method", "route", "api", "file", "where"]
    return any(marker in text for marker in markers)


def _adjusted_score(question: str, doc, score: float) -> float:
    adjusted = float(score)
    metadata = doc.metadata or {}
    path = str((metadata.get("path") or metadata.get("filename") or "")).lower()
    chunk_type = metadata.get("chunk_type")
    parse_quality = metadata.get("parse_quality")

    if parse_quality == "high":
        adjusted -= 0.15
    elif parse_quality == "low":
        adjusted += 0.15

    if chunk_type == "fallback":
        adjusted += 0.25

    if _is_code_intent(question):
        if chunk_type in {"ast", "tree_sitter"}:
            adjusted -= 0.2
        if "readme" in path:
            adjusted += 0.3

    return adjusted


def _retrieve_ranked_docs(question: str, top_k: int):
    vectorstore = get_vectorstore()
    raw = vectorstore.similarity_search_with_score(question, k=max(3, top_k * 4))
    ranked = sorted(raw, key=lambda item: _adjusted_score(question, item[0], item[1]))

    selected = []
    seen = set()
    for doc, _score in ranked:
        content = (doc.page_content or "").strip()
        if not content or content in seen:
            continue
        seen.add(content)
        selected.append(doc)
        if len(selected) >= top_k:
            break

    return selected


def rag_query(question: str, top_k: int = 3) -> str:
    """
    Retrieve relevant chunks from FAISS and ask LLaMA.
    """
    try:
        docs = _retrieve_ranked_docs(question, top_k=top_k)

        if not docs:
            return "I don't know based on the retrieved context."

        context = "\n\n".join(doc.page_content for doc in docs)

        prompt = f"""You are a senior software engineer.
Use only the provided context to answer the question.
If the answer is not explicitly present, reply exactly: I don't know based on the retrieved context.
Keep the answer concise and avoid guessing.

### Context:
{context}

### Question:
{question}

### Answer:
"""

        try:
            output = llm(
                prompt,
                max_tokens=256,
                stop=["###"]
            )
            result = output.get("choices", [{}])[0].get("text", "").strip()
            return result if result else "I don't know based on the retrieved context."
        except Exception as e:
            error_msg = f"LLM generation failed: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            return error_msg

    except Exception as e:
        error_msg = f"RAG query failed: {str(e)}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        return error_msg
