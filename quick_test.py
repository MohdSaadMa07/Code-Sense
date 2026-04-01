#!/usr/bin/env python
"""Simple test for llama endpoint"""
import sys
print("Python version:", sys.version, file=sys.stderr)

try:
    import requests
    print("Requests imported OK", file=sys.stderr)
except Exception as e:
    print(f"Failed to import requests: {e}", file=sys.stderr)
    sys.exit(1)

url = "http://127.0.0.1:8000/llama/query?prompt=what%20is%20cart&top_k=3"
print(f"Testing: {url}", file=sys.stderr)
sys.stderr.flush()

try:
    print("Making request...", file=sys.stderr)
    r = requests.post(url, timeout=60)
    print(f"Status: {r.status_code}", file=sys.stderr)
    print(f"Response: {r.text[:500]}", file=sys.stderr)
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

print("Done", file=sys.stderr)


