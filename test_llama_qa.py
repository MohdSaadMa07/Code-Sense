#!/usr/bin/env python
"""Test the improved LLaMA Q&A endpoint"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

print("="*70)
print("Testing Improved LLaMA Q&A Pipeline")
print("="*70)

# Test query from the user's request
query = "How does the admin update the status of a booking?"
print(f"\nQuery: {query}\n")

try:
    # Test with include_context=true to see both answer and retrieved chunks
    url = f"{BASE_URL}/llama/query?prompt={query.replace(' ', '%20').replace('?', '%3F')}&top_k=3&include_context=true"

    print(f"URL: {url}\n")
    r = requests.post(url, timeout=60)

    print(f"Status: {r.status_code}\n")

    data = r.json()

    print("="*70)
    print("LLAMA ANSWER:")
    print("="*70)
    print(data['result'])
    print()

    if 'context' in data:
        print("="*70)
        print("RETRIEVED CONTEXT CHUNKS:")
        print("="*70)
        for i, chunk in enumerate(data['context'], 1):
            print(f"\n[Chunk {i}] Source: {chunk['source']}")
            print(f"Content:\n{chunk['chunk'][:200]}...")
            print(f"Metadata: {json.dumps(chunk['metadata'], indent=2)}")

    print("\n" + "="*70)
    if "NOT FOUND IN CONTEXT" not in data['result']:
        print("✅ SUCCESS: LLaMA provided an answer!")
    else:
        print("⚠️  WARNING: LLaMA could not find answer in context")
    print("="*70)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

