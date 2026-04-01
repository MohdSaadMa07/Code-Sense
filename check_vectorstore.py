#!/usr/bin/env python
"""Test vector store status"""
import sys
sys.path.insert(0, r"C:\Users\mohds\django-projects\code-app\code-app")

try:
    from app.services.storage import get_vectorstore

    print("Checking vector store...")
    vs = get_vectorstore()

    if vs is None:
        print("❌ Vector store is None")
    else:
        print("✓ Vector store initialized")

        # Try a test query
        results = vs.similarity_search("update order status", k=3)
        print(f"✓ Test query returned {len(results)} results")

        for i, doc in enumerate(results, 1):
            print(f"\n  [{i}] Path: {doc.metadata.get('path')}")
            print(f"      Content: {doc.page_content[:100]}...")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

