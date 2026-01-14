from langchain_community.vectorstores import FAISS
import os

from app.services.embeddings import create_embeddings

VECTOR_DB_PATH = "data/faiss"


def store_documents(text_chunks: list[str]):
    embeddings = create_embeddings()

    vectorstore = FAISS.from_texts(
        texts=text_chunks,
        embedding=embeddings
    )

    os.makedirs(VECTOR_DB_PATH, exist_ok=True)
    vectorstore.save_local(VECTOR_DB_PATH)
