from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

# Lazy initialization 
_vectorstore = None
_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _embeddings

def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        embeddings = get_embeddings()
        _vectorstore = FAISS.from_texts([""], embeddings)
    return _vectorstore

def store_documents(documents: list[Document]):
    if not documents:
        raise ValueError("No documents provided")
    
    vectorstore = get_vectorstore()
    vectorstore.add_documents(documents)
    return len(documents)
