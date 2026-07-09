import os, re
from openai import OpenAI
from app.services.retrieval.manager import manager

print("[RAG] Using Groq (GPT-OSS 120B)")

_client = None

def get_client():
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        try:
            _client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=key,
                max_retries=2,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Groq client: {e}")
    return _client


def _is_code_query(query: str) -> bool:
    markers = ["function", "method", "parameters", "threshold", "anomaly", "def ", "class "]
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
    return code_docs + non_code


def _build_context(docs):
    chunks = []
    for d in docs:
        content = (d.page_content or "").strip()
        if not content:
            continue
        chunks.append(f"[FILE]: {d.metadata.get('path','unknown')}\n{content}")
    return "\n\n".join(chunks)


def _is_grounded(answer: str, context: str) -> bool:
    if not answer.strip() or not context.strip():
        return False
    context_lower = context.lower()
    words = [w.lower() for w in answer.split() if len(w) > 3]
    hits = sum(1 for w in words if w in context_lower)
    return hits >= 2


def rag_query(repo_id: str, query: str, top_k: int = 3):
    vs = manager.get(repo_id)

    results = vs.similarity_search_with_score(query, k=top_k * 3)

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
        return {"llm_answer": "No relevant context found in repository.", "retrieved_chunks": []}

    docs = _rerank_docs(docs, query)
    selected_docs = docs[:top_k]
    context = _build_context(selected_docs)

    if "psutil" in query.lower():
        extracted = set()
        for d in selected_docs:
            matches = re.findall(r"psutil\.\w+", d.page_content or "")
            extracted.update(matches)
        if extracted:
            return {
                "llm_answer": "psutil-related functions and attributes:\n- " + "\n- ".join(sorted(extracted)),
                "retrieved_chunks": [
                    {"chunk": d.page_content, "source": d.metadata.get("path"), "score": scores.get((d.page_content or "").strip())}
                    for d in selected_docs
                ]
            }

    prompt = f"""You are a code analysis assistant.

RULES:
- Answer using the given context only
- If code exists, explain what it does
- Mention function names clearly
- If the context has nothing related to the question, say "No relevant information found in the codebase" - do not make up answers

CONTEXT:
{context}

QUESTION:
{query}"""

    client = get_client()
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=2048,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )

    answer = response.choices[0].message.content.strip()
    answer = answer.split("CONTEXT:")[0].strip()

    if not _is_grounded(answer, context):
        answer += "\n\n(Note: partially inferred from limited context)"

    return {
        "llm_answer": answer,
        "retrieved_chunks": [
            {"chunk": d.page_content, "source": d.metadata.get("path"), "score": scores.get((d.page_content or "").strip())}
            for d in selected_docs
        ]
    }
