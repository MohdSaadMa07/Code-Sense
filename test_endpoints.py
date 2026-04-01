#!/usr/bin/env python
"""Test FastAPI endpoints"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_root():
    """Test the root endpoint"""
    try:
        print("Testing GET /...")
        r = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"  Status: {r.status_code}")
        print(f"  Response: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_llama_endpoint():
    """Test the llama query endpoint"""
    try:
        print("\nTesting POST /llama/query...")
        params = {
            "prompt": "what are columns in cart",
            "top_k": 3,
            "include_context": False
        }
        r = requests.post(
            f"{BASE_URL}/llama/query",
            params=params,
            timeout=30
        )
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"  Result: {json.dumps(result, indent=2)[:200]}...")
            return True
        else:
            print(f"  Error: {r.text}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("FastAPI Server Test Suite")
    print("=" * 50)

    # Test root
    root_ok = test_root()

    # Test llama (only if root works)
    llama_ok = test_llama_endpoint() if root_ok else False

    print("\n" + "=" * 50)
    print(f"Root endpoint: {'✓ PASS' if root_ok else '✗ FAIL'}")
    print(f"LLaMA endpoint: {'✓ PASS' if llama_ok else '✗ FAIL'}")
    print("=" * 50)


