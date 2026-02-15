from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document  # Corrected import
from langchain_text_splitters import RecursiveCharacterTextSplitter  # Corrected import

_embeddings = None
_vectorstore = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"  # Downloads if not local
        )
    return _embeddings

def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        embeddings = get_embeddings()
        # Proper empty FAISS init (from_texts([], ...) deprecated/buggy)
        dummy_embedding = embeddings.embed_query(" ")
        dimension = len(dummy_embedding)
        import faiss
        from langchain_community.docstore.in_memory import InMemoryDocstore
        index = faiss.IndexFlatL2(dimension)
        _vectorstore = FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=InMemoryDocstore({}),
            index_to_docstore_id={}
        )
    return _vectorstore

def store_documents(documents: list[Document], chunk_size=500, chunk_overlap=50):
    if not documents:
        raise ValueError("No documents provided")

    vs = get_vectorstore()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    all_chunks = []
    for doc in documents:
        if doc.page_content.strip():  # Skip empty docs
            chunks = splitter.split_text(doc.page_content)
            all_chunks.extend([Document(page_content=c, metadata=doc.metadata) for c in chunks])

    if all_chunks:
        vs.add_documents(all_chunks)
    return len(all_chunks)
