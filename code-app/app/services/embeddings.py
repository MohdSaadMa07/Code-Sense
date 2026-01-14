from langchain_openai import OpenAIEmbeddings


def create_embeddings():
    """
    Creates and returns embedding model
    """
    return OpenAIEmbeddings()
