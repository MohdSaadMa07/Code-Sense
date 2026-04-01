#!/usr/bin/env python
"""
Final verification that all three fixes are in place
"""
import sys
import os
sys.path.insert(0, r"C:\Users\mohds\django-projects\code-app\code-app")

print("=" * 70)
print("VERIFYING ALL FIXES ARE IN PLACE")
print("=" * 70)

# Fix 1: Model Path
print("\n[1] Checking Model Path Resolution...")
try:
    from app.services import llama_rag
    from pathlib import Path

    model_path = llama_rag.MODEL_PATH
    print(f"    ✓ MODEL_PATH: {model_path}")

    if os.path.exists(model_path):
        size_gb = os.path.getsize(model_path) / (1024**3)
        print(f"    ✓ Model exists: {size_gb:.2f} GB")
        fix1_ok = True
    else:
        print(f"    ✗ Model NOT found")
        fix1_ok = False

    if "Llama-3.2-1B-Instruct-F16.gguf" in model_path:
        print(f"    ✓ Correct model filename")
    else:
        print(f"    ✗ Wrong model filename")
        fix1_ok = False

except Exception as e:
    print(f"    ✗ Error: {e}")
    fix1_ok = False

# Fix 2: Q&A Prompt
print("\n[2] Checking Q&A Prompt...")
try:
    import inspect
    from app.services.llama_rag import rag_query

    source = inspect.getsource(rag_query)

    checks = {
        "Q&A prompt": "helpful code assistant" in source,
        "User question in prompt": "USER QUESTION:" in source,
        "Grounding check present": "len(context.strip()) < 200 and len(answer) > 400" in source,
        "Text-based answer": "answer = response" in source,
    }

    fix2_ok = all(checks.values())

    for check_name, result in checks.items():
        status = "✓" if result else "✗"
        print(f"    {status} {check_name}")

except Exception as e:
    print(f"    ✗ Error: {e}")
    fix2_ok = False

# Fix 3: Chunk Size
print("\n[3] Checking Chunk Size Parameters...")
try:
    import inspect
    from app.services.storage import store_documents

    sig = inspect.signature(store_documents)
    chunk_size = sig.parameters['chunk_size'].default
    chunk_overlap = sig.parameters['chunk_overlap'].default

    print(f"    chunk_size: {chunk_size}")
    if chunk_size == 1500:
        print(f"    ✓ Chunk size is 1500 (was 500)")
        fix3_ok_size = True
    else:
        print(f"    ✗ Chunk size is {chunk_size} (should be 1500)")
        fix3_ok_size = False

    print(f"    chunk_overlap: {chunk_overlap}")
    if chunk_overlap == 150:
        print(f"    ✓ Chunk overlap is 150 (was 50)")
        fix3_ok_overlap = True
    else:
        print(f"    ✗ Chunk overlap is {chunk_overlap} (should be 150)")
        fix3_ok_overlap = False

    fix3_ok = fix3_ok_size and fix3_ok_overlap

except Exception as e:
    print(f"    ✗ Error: {e}")
    fix3_ok = False

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

all_ok = fix1_ok and fix2_ok and fix3_ok

fixes = [
    ("Model Path Resolution", fix1_ok),
    ("Q&A Prompt Updated", fix2_ok),
    ("Chunk Size Fixed", fix3_ok),
]

for fix_name, status in fixes:
    symbol = "✅" if status else "❌"
    print(f"{symbol} {fix_name}")

print("=" * 70)

if all_ok:
    print("\n🎉 ALL FIXES VERIFIED - READY FOR PRODUCTION\n")
    sys.exit(0)
else:
    print("\n⚠️  SOME FIXES NOT DETECTED\n")
    sys.exit(1)

