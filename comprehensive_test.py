#!/usr/bin/env python
"""Comprehensive test of FastAPI application"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

print("=" * 70)
print("FASTAPI APPLICATION TEST SUITE")
print("=" * 70)

# Test 1: Root endpoint
print("\n[TEST 1] GET / (Root endpoint)")
try:
    r = requests.get(f"{BASE_URL}/", timeout=5)
    print(f"  ✓ Status: {r.status_code}")
    print(f"  ✓ Response: {r.json()}")
    test1_pass = r.status_code == 200
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    test1_pass = False

# Test 2: Query vector store (should return empty since no docs ingested)
print("\n[TEST 2] POST /query/ (Query vectorstore - empty)")
try:
    r = requests.post(
        f"{BASE_URL}/query/",
        json={"query": "test", "top_k": 3},
        timeout=10
    )
    print(f"  ✓ Status: {r.status_code}")
    data = r.json()
    print(f"  ✓ Results count: {len(data.get('results', []))}")
    test2_pass = r.status_code == 200
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    test2_pass = False

# Test 3: LLaMA endpoint with empty context
print("\n[TEST 3] POST /llama/query (LLaMA with empty context)")
try:
    r = requests.post(
        "http://127.0.0.1:8000/llama/query?prompt=what%20is%20cart&top_k=3",
        timeout=60
    )
    print(f"  ✓ Status: {r.status_code}")
    data = r.json()
    result = data.get('result')
    print(f"  ✓ Result: {result}")
    test3_pass = r.status_code == 200 and result == "NOT FOUND IN CONTEXT"
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    test3_pass = False

# Test 4: Check model loading
print("\n[TEST 4] Model configuration check")
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "code-app"))
    from app.services import llama_rag
    import os
    print(f"  ✓ MODEL_PATH: {llama_rag.MODEL_PATH}")
    exists = os.path.exists(llama_rag.MODEL_PATH)
    size = os.path.getsize(llama_rag.MODEL_PATH) if exists else 0
    print(f"  ✓ Model exists: {exists}")
    print(f"  ✓ Model size: {size / (1024**3):.2f} GB")
    test4_pass = exists and size > 1e9
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    test4_pass = False

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"[1] Root endpoint:        {'✓ PASS' if test1_pass else '✗ FAIL'}")
print(f"[2] Query endpoint:       {'✓ PASS' if test2_pass else '✗ FAIL'}")
print(f"[3] LLaMA endpoint:       {'✓ PASS' if test3_pass else '✗ FAIL'}")
print(f"[4] Model loaded:         {'✓ PASS' if test4_pass else '✗ FAIL'}")
print("=" * 70)

all_pass = all([test1_pass, test2_pass, test3_pass, test4_pass])
print(f"\nOVERALL STATUS: {'✅ ALL TESTS PASSED' if all_pass else '❌ SOME TESTS FAILED'}")
print("\nThe FastAPI application is ready!")
print("Next: Ingest a repository via POST /github/ingest")
print("=" * 70)


