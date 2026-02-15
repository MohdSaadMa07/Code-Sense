from llama_cpp import Llama
from app.services.storage import get_vectorstore

# Load model ONCE (global, safe)
llm = Llama(
    model_path="app/models/Llama-3.2-1B-Instruct-F16.gguf",  # <- updated path
    n_threads=4,
    n_ctx=2048
)


def rag_query(question: str, top_k: int = 3) -> str:
    """
    Retrieve relevant chunks from FAISS and ask LLaMA.
    """

    vectorstore = get_vectorstore()

    docs = vectorstore.similarity_search(
        question,
        k=top_k
    )

    if not docs:
        return "No relevant context found."

    context = "\n\n".join(doc.page_content for doc in docs)

    prompt = f"""
You are a senior software engineer.

Use the following GitHub repository context to answer the question.
If the answer is not in the context, say you don't know.

### Context:
{context}

### Question:
{question}

### Answer:
"""

    output = llm(
        prompt,
        max_tokens=512,
        stop=["###"]
    )

    return output["choices"][0]["text"].strip()
