from llama_cpp import Llama
from app.services.storage import get_vectorstore
from langchain_core.documents import Document

# Path to your downloaded Code LLaMA 7B-instruct model
MODEL_PATH = "models/codellama-7b-instruct.gguf"  # <- update with your actual GGUF path

# Lazy initialization
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=8192,       # Larger context for code-heavy repos
            n_threads=8,      # Increase if you have more CPU cores / GPU threads
            temperature=0.2,  # Lower temp reduces hallucination
            top_p=0.95,       # Optional: better sampling
        )
    return _llm

def rag_query(query: str, top_k: int = 3) -> dict:
    """
    Retrieve top-k relevant chunks from vectorstore and generate an answer using Code LLaMA 7B-instruct.
    Returns a structured dict with:
      - 'llm_answer': str
      - 'retrieved_chunks': list of {chunk, score, source}
    """
    # Load vectorstore
    vs = get_vectorstore()
    if vs is None:
        raise ValueError("Vectorstore is not initialized. Ingest documents first.")

    # Retrieve top-k similar chunks
    docs: list[Document] = vs.similarity_search(query, k=top_k)
    if not docs:
        return {"llm_answer": "No relevant chunks found.", "retrieved_chunks": []}

    # Concatenate chunks with metadata for better context
    context = "\n\n".join([
        f"File: {doc.metadata.get('source', 'unknown')}\n{doc.page_content}"
        for doc in docs
    ])

    # Strong prompt tailored for code reasoning
    prompt = f"""
You are an expert programmer. Answer the question using ONLY the following retrieved chunks.
Do not invent information. If the answer is not in the chunks, say 'I don't know'.

Context:
{context}

Question: {query}
Answer:
"""

    # Generate response
    llm = get_llm()
    response = llm(prompt, max_tokens=1024)  # Increase max_tokens for longer code answers
    answer = response['choices'][0]['text'].strip()

    # Return structured result
    return {
        "llm_answer": answer,
        "retrieved_chunks": [
            {
                "chunk": doc.page_content,
                "score": getattr(doc, "score", None),
                "source": doc.metadata.get("source", "unknown")
            }
            for doc in docs
        ]
    }