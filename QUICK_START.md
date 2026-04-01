# Quick Start Guide: Using Code-Sense RAG

## 1. Ingest a GitHub Repo (with better coverage)

Restart your server first:
```powershell
uvicorn app.main:app --reload
```

Then ingest with more files (now defaults to 500):
```bash
curl -X POST "http://127.0.0.1:8000/github/ingest" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d "{\"repo_url\":\"https://github.com/sumitkumar1503/ecommerce\", \"max_files\": 1000}"
```

Expected output:
```json
{
  "status": "success",
  "repo": "sumitkumar1503/ecommerce",
  "files_ingested": <number>,
  "chunks_ingested": <number>,
  "sample_file": "README.md"
}
```

## 2. Query with Source Metadata

Now when you search, results include file paths and line ranges:

```bash
curl -X POST "http://127.0.0.1:8000/query/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"cart table model\", \"top_k\":5}"
```

Response example:
```json
{
  "query": "cart table model",
  "results": [
    {
      "rank": 1,
      "chunk": "class Cart(models.Model):\n    id = models.AutoField(...)",
      "score": 0.523,
      "metadata": {
        "path": "models.py",
        "chunk_type": "ast",
        "symbol": "Cart",
        "symbol_kind": "classdef",
        "start_line": 42,
        "end_line": 58
      }
    }
  ]
}
```

Use this to verify LLM answers are grounded in actual code.

## 3. Ask LLaMA with Better Context

Now that retrieval is deeper, LLM answers should be more accurate:

```bash
curl -X POST "http://127.0.0.1:8000/llama/query?prompt=what are the exact column names in the cart table" \
  -H "accept: application/json" \
  -d ""
```

## 4. Measure Retrieval Quality

Add your own test cases to benchmark accuracy:

```bash
# Edit code-app/benchmarks/query_eval_cases.json and add cases like:
{
  "id": "cart-columns",
  "query": "cart table model columns",
  "relevant_paths": ["models.py"],
  "relevant_symbols": ["Cart"],
  "relevant_terms": ["class Cart"]
}
```

Then run:
```powershell
python code-app\scripts\benchmark_query_accuracy.py `
  --base-url http://127.0.0.1:8000 `
  --cases-file code-app\benchmarks\query_eval_cases.json `
  --top-k 5
```

Output will show `hit@5` and `mrr@5` scores to track improvements.

## Key Improvements Made

- ✅ Default `max_files` increased to 500 (was 200)
- ✅ Can now pass custom `max_files` per ingest request
- ✅ `/query/` returns source file paths and line metadata
- ✅ `/query/` returns `chunk_type` (ast/tree_sitter/fallback) for transparency
- ✅ Benchmark script to measure retrieval accuracy objectively

## Debugging Hallucinations

If LLM still hallucinates:
1. Check `/query/` results first — if they're wrong, retrieval is the issue
2. Increase `max_files` to ingest deeper into the repo
3. Use more specific query terms (e.g., `"class Cart"` vs `"cart"`)
4. Check benchmark scores to track quality over time

