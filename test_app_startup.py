#!/usr/bin/env python
"""Quick test to verify the FastAPI app can import successfully"""
import sys
sys.path.insert(0, r"C:\Users\mohds\django-projects\code-app\code-app")

try:
    print("✓ Testing imports...")
    from app.main import app
    print("✓ App imported successfully")

    print("✓ Checking routes...")
    routes = [str(r.path) for r in app.routes]
    print(f"✓ Found {len(routes)} routes: {routes}")

    print("✓ Checking LLaMA service config...")
    from app.services import llama_rag
    print(f"✓ MODEL_PATH: {llama_rag.MODEL_PATH}")

    import os
    if os.path.exists(llama_rag.MODEL_PATH):
        print(f"✓ Model file exists: {os.path.getsize(llama_rag.MODEL_PATH)} bytes")
    else:
        print(f"✗ Model file NOT found at: {llama_rag.MODEL_PATH}")

    print("\n✅ App startup check PASSED - all imports successful!")
    sys.exit(0)

except Exception as e:
    print(f"\n❌ FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

