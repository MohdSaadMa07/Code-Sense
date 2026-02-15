from llama_cpp import Llama
from app.services.storage import get_vectorstore
from langchain_core.documents import Document

# Path to your downloaded GGUF model
MODEL_PATH = "models/Llama-3.2-1B-Instruct-F16.gguf"

# Lazy initialization
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_threads=4
        )
    return _llm

def rag_query(query: str, top_k: int = 3) -> list[dict]:
    """
    Retrieve top-k relevant chunks from FAISS vectorstore
    and pass as context to Llama for answering.
    Returns a list of {chunk, score}.
    """
    vs = get_vectorstore()
    if vs is None:
        raise ValueError("Vectorstore is not initialized. Ingest documents first.")

    # Retrieve top-k similar chunks
    docs: list[Document] = vs.similarity_search(query, k=top_k)

    if not docs:
        return []

    # Concatenate chunks as context for Llama
    context = "\n\n".join([doc.page_content for doc in docs])

    llm = get_llm()
    prompt = f"Answer the question based on the following context:\n\n{context}\n\nQuestion: {query}\nAnswer:"

    response = llm(prompt, max_tokens=250)
    answer = response['choices'][0]['text'].strip()

    # Return top-k chunks with their text
    return [{"chunk": doc.page_content, "score": getattr(doc, 'score', None)} for doc in docs] + [{"llm_answer": answer}]
