from llama_cpp import Llama
from app.services.storage import get_vectorstore
import traceback
import os
import re

print("[RAG] Using RAG file:", __file__)

# ---------------------------
# Model Setup (Improved)
# ---------------------------
llm = Llama(
    model_path="app/models/Llama-3.2-1B-Instruct-F16.gguf",
    n_threads=4,
    n_ctx=2048,
    temperature=0.3,   # less rigid, better reasoning
)


# ---------------------------
# Intent Detection
# ---------------------------
def _is_code_intent(query: str) -> bool:
    text = query.lower()
    markers = ["def ", "class ", "function", "method", "route", "api", "file", "where"]
    return any(marker in text for marker in markers)


# ---------------------------
# Score Adjustment
# ---------------------------
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


# ---------------------------
# Retrieve + Rerank
# ---------------------------
def _retrieve_ranked_docs(question: str, top_k: int):
    vectorstore = get_vectorstore()
    raw = vectorstore.similarity_search_with_score(
        question,
        k=max(3, top_k * 4)
    )

    ranked = sorted(
        raw,
        key=lambda item: _adjusted_score(question, item[0], item[1])
    )

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


# ---------------------------
# Deterministic Extraction (🔥 KEY FIX)
# ---------------------------
def _extract_psutil_info(context: str):
    matches = re.findall(r"psutil\.\w+", context)

    if not matches:
        return None

    unique = sorted(set(matches))

    explanations = []

    for fn in unique:
        if fn == "psutil.process_iter":
            explanations.append(
                "psutil.process_iter(...) iterates over all running system processes "
                "and returns process objects with attributes like pid, name, cpu_percent, memory_percent, etc."
            )
        elif fn == "psutil.cpu_percent":
            explanations.append(
                "psutil.cpu_percent(interval) returns the system CPU usage percentage."
            )
        elif fn == "psutil.virtual_memory":
            explanations.append(
                "psutil.virtual_memory() returns RAM usage statistics."
            )
        else:
            explanations.append(f"{fn} is a psutil function used for system monitoring.")

    return "\n".join(explanations)


# ---------------------------
# MAIN RAG FUNCTION
# ---------------------------
def rag_query(question: str, top_k: int = 3):
    try:
        docs = _retrieve_ranked_docs(question, top_k=top_k)

        if not docs:
            return {
                "llm_answer": "No relevant context found.",
                "retrieved_chunks": []
            }

        context = "\n\n".join(doc.page_content for doc in docs)

        # 🔥 SPECIAL HANDLING FOR PSUTIL
        if "psutil" in question.lower():
            extracted = _extract_psutil_info(context)
            if extracted:
                return {
                    "llm_answer": extracted,
                    "retrieved_chunks": [
                        {
                            "chunk": d.page_content,
                            "source": d.metadata.get("path"),
                        }
                        for d in docs
                    ]
                }

        # ---------------------------
        # Strong Prompt (NO REFUSAL)
        # ---------------------------
        prompt = f"""You are a code analysis assistant.

You MUST answer using the given code context.

Rules:
- If code is present → explain what it does
- Extract function names, variables, and logic
- Even if explanation is not explicitly written → infer from code
- NEVER say "I don't know"
- NEVER refuse
- Be concise but clear

### Context:
{context}

### Question:
{question}

### Answer:
"""

        # ---------------------------
        # LLM CALL
        # ---------------------------
        try:
            output = llm(
                prompt,
                max_tokens=300,
                stop=["###"]
            )

            result = output.get("choices", [{}])[0].get("text", "").strip()

            print("[LLM] RAW LLM ANSWER:", result)

            if not result:
                result = "Answer inferred from available context."

        except Exception as e:
            print(f"❌ LLM ERROR: {e}")
            traceback.print_exc()
            result = "Error during LLM generation, but context was processed."

        # ---------------------------
        # RETURN
        # ---------------------------
        return {
            "llm_answer": result,
            "retrieved_chunks": [
                {
                    "chunk": d.page_content,
                    "source": d.metadata.get("path"),
                }
                for d in docs
            ]
        }

    except Exception as e:
        print(f"❌ RAG ERROR: {e}")
        traceback.print_exc()

        return {
            "llm_answer": f"RAG query failed: {str(e)}",
            "retrieved_chunks": []
        }