import argparse
import os
import sys

# Ensure the parent directory is in the path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.documents import Document
from app.services.storage import store_documents, clear_vectorstore

def ingest_directory(directory_path: str):
    """
    Reads all text-based files in the given directory recursively and stores them in the hybrid vectorstore.
    Run this script LOCALLY to generate embeddings without hitting Render memory limits.
    """
    if not os.path.exists(directory_path):
        print(f"Error: Directory {directory_path} not found.")
        sys.exit(1)

    print(f"Starting local ingestion for directory: {directory_path}")
    
    # List of common text/code extensions
    valid_extensions = {
        ".py", ".js", ".ts", ".html", ".css", ".md", ".txt", ".json", 
        ".yaml", ".yml", ".sh", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h"
    }

    documents = []
    
    for root, _, files in os.walk(directory_path):
        # Skip common ignored directories
        if any(ignored in root for ignored in [".git", "node_modules", ".venv", "__pycache__", "venv"]):
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                        if text.strip():
                            # Path relative to the target directory for cleaner metadata
                            rel_path = os.path.relpath(file_path, directory_path)
                            documents.append(
                                Document(
                                    page_content=text,
                                    metadata={"filename": file, "path": rel_path}
                                )
                            )
                except Exception as e:
                    print(f"Skipping {file_path}: {e}")

    if not documents:
        print("No valid text documents found to ingest.")
        sys.exit(1)

    print(f"Found {len(documents)} documents. Starting chunking and embedding generation...")
    print("WARNING: This may take a few minutes if the repository is large.")
    
    # Clear old vectorstore
    clear_vectorstore()
    
    # Store documents
    try:
        chunks_ingested = store_documents(documents)
        print(f"Success! {chunks_ingested} chunks embedded and saved to the vectorstore.")
        print("You can now safely deploy the generated 'vectorstore' directory to Render.")
    except Exception as e:
        print(f"Ingestion failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Locally ingest a codebase into the hybrid vectorstore.")
    parser.add_argument("directory", nargs="?", default=".", help="The root directory of the codebase to ingest (defaults to current directory).")
    args = parser.parse_args()
    
    ingest_directory(args.directory)
