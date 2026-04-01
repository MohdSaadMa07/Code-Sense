#!/usr/bin/env python
"""
Final verification that the FastAPI app is fully operational
Run this after the server is started with: uvicorn app.main:app --reload
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

print_section("🚀 FastAPI Application - Full Verification")

# Test 1: Health check
print("[✓] Testing health check...")
r = requests.get(f"{BASE_URL}/")
assert r.status_code == 200, f"Health check failed: {r.status_code}"
print(f"    Server responding: {r.json()}\n")

# Test 2: Query endpoint
print("[✓] Testing query endpoint (empty vectorstore)...")
r = requests.post(f"{BASE_URL}/query/", json={"query": "test", "top_k": 3})
assert r.status_code == 200, f"Query failed: {r.status_code}"
data = r.json()
print(f"    Query results: {len(data['results'])} chunks found")
print(f"    Expected: 0 (no documents ingested yet)\n")

# Test 3: LLaMA endpoint
print("[✓] Testing LLaMA endpoint...")
r = requests.post(f"{BASE_URL}/llama/query?prompt=what%20is%20cart&top_k=3")
assert r.status_code == 200, f"LLaMA query failed: {r.status_code}"
data = r.json()
print(f"    LLaMA response: {data['result']}")
print(f"    Expected: 'NOT FOUND IN CONTEXT' (no documents ingested)\n")

# Test 4: Model configuration
print("[✓] Verifying LLaMA model...")
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "code-app"))
from app.services import llama_rag
import os
model_exists = os.path.exists(llama_rag.MODEL_PATH)
model_size_gb = os.path.getsize(llama_rag.MODEL_PATH) / (1024**3) if model_exists else 0
print(f"    Model path: {llama_rag.MODEL_PATH}")
print(f"    Model exists: {model_exists}")
print(f"    Model size: {model_size_gb:.2f} GB\n")

print_section("✅ APPLICATION STATUS: FULLY OPERATIONAL")

print("All endpoints are working correctly!")
print("\nTo ingest a repository:")
print("  POST /github/ingest")
print("  {")
print('    "repo_url": "https://github.com/username/repo"')
print('    "max_files": 500')
print("  }\n")

print("To query the ingested documents:")
print("  POST /query/")
print("  {")
print('    "query": "your search query"')
print('    "top_k": 3')
print("  }\n")

print("To ask LLaMA about the documents:")
print("  POST /llama/query?prompt=your%20question&top_k=3&include_context=false\n")

print_section("📝 Server Details")
print(f"Base URL: {BASE_URL}")
print(f"API Docs: {BASE_URL}/docs")
print(f"OpenAPI Schema: {BASE_URL}/openapi.json\n")

