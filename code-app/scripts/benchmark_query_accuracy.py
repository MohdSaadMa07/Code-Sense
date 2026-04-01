import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class CaseResult:
    case_id: str
    query: str
    hit: bool
    reciprocal_rank: float
    first_match_rank: int | None


def load_cases(cases_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("cases file must contain a JSON array")
    return payload


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def result_matches_case(result: dict[str, Any], case: dict[str, Any]) -> bool:
    chunk = _normalize(result.get("chunk"))
    metadata = result.get("metadata") or {}
    path = _normalize(metadata.get("path"))
    symbol = _normalize(metadata.get("symbol"))

    expected_paths = [_normalize(p) for p in case.get("relevant_paths", [])]
    expected_symbols = [_normalize(s) for s in case.get("relevant_symbols", [])]
    expected_terms = [_normalize(t) for t in case.get("relevant_terms", [])]

    if expected_paths and path in expected_paths:
        return True
    if expected_symbols and symbol in expected_symbols:
        return True
    if expected_terms and any(term and term in chunk for term in expected_terms):
        return True
    return False


def evaluate_case(base_url: str, case: dict[str, Any], top_k: int, timeout: int) -> CaseResult:
    query = case["query"]
    response = requests.post(
        f"{base_url.rstrip('/')}/query/",
        json={"query": query, "top_k": top_k},
        timeout=timeout,
    )
    response.raise_for_status()
    results = (response.json() or {}).get("results", [])

    first_match_rank = None
    for idx, result in enumerate(results, start=1):
        if result_matches_case(result, case):
            first_match_rank = idx
            break

    hit = first_match_rank is not None
    reciprocal_rank = 1.0 / first_match_rank if first_match_rank else 0.0

    return CaseResult(
        case_id=str(case.get("id") or query),
        query=query,
        hit=hit,
        reciprocal_rank=reciprocal_rank,
        first_match_rank=first_match_rank,
    )


def print_report(case_results: list[CaseResult], top_k: int) -> None:
    total = len(case_results)
    hit_count = sum(1 for r in case_results if r.hit)
    hit_at_k = hit_count / total if total else 0.0
    mrr = statistics.fmean([r.reciprocal_rank for r in case_results]) if total else 0.0

    print(f"cases={total} top_k={top_k}")
    print(f"hit@{top_k}={hit_at_k:.3f}")
    print(f"mrr@{top_k}={mrr:.3f}")
    print("\nPer-case:")
    for r in case_results:
        print(
            f"- id={r.case_id} hit={r.hit} first_match_rank={r.first_match_rank} "
            f"rr={r.reciprocal_rank:.3f} query={r.query}"
        )


def run_self_test() -> None:
    sample_case = {
        "id": "demo",
        "query": "where is cart updated",
        "relevant_paths": ["cart/views.py"],
        "relevant_symbols": ["update_cart"],
        "relevant_terms": ["def update_cart"],
    }
    sample_result_hit = {
        "chunk": "def update_cart(request):\n    pass",
        "metadata": {"path": "cart/views.py", "symbol": "update_cart"},
    }
    sample_result_miss = {
        "chunk": "def cart_view(request):\n    pass",
        "metadata": {"path": "orders/views.py", "symbol": "cart_view"},
    }

    assert result_matches_case(sample_result_hit, sample_case)
    assert not result_matches_case(sample_result_miss, sample_case)
    print("SELF_TEST_OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark retrieval quality of /query endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI base URL")
    parser.add_argument(
        "--cases-file",
        default="benchmarks/query_eval_cases.json",
        help="JSON file containing benchmark cases",
    )
    parser.add_argument("--top-k", type=int, default=5, help="top_k value sent to /query")
    parser.add_argument("--timeout", type=int, default=30, help="request timeout in seconds")
    parser.add_argument("--self-test", action="store_true", help="run script self-test and exit")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    cases = load_cases(Path(args.cases_file))
    results = [evaluate_case(args.base_url, case, args.top_k, args.timeout) for case in cases]
    print_report(results, args.top_k)


if __name__ == "__main__":
    main()

