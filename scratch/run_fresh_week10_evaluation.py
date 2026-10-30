"""Fresh Single-Agent and Multi-Agent Evaluation Runner for Week 10 Final Submission.

Executes Task Set C (TQ01-TQ10) against unchanged trajectory dataset.
Outputs to scratch/fresh_evaluation_results.json.
Preserves all historical benchmark artifacts untouched.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app.agent as agent_module
from app.agent import COST_PER_1K_TOKENS, run_agent
from app.multi_agent import run_multi_agent
import app.search as search_module
from evaluation.trajectory_dataset import TRAJECTORY_DATASET
from evaluation.trajectory_evaluator import answer_matches


def calculate_percentile(data: list[float], percentile: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    k = (percentile / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    fraction = k - f
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * fraction


def run_fresh_eval():
    output_path = ROOT_DIR / "scratch" / "fresh_evaluation_results.json"
    print("=" * 70, flush=True)
    print("WEEK 10 FRESH EVALUATION: SINGLE-AGENT VS MULTI-AGENT", flush=True)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"Cases: {len(TRAJECTORY_DATASET)} (TQ01 to TQ10)", flush=True)
    print("=" * 70, flush=True)

    # 1. First run Arm B (Multi-Agent) across all 10 cases
    print("\n--- RUNNING ARM B: MULTI-AGENT (10 cases) ---", flush=True)
    multi_results = []
    for idx, case in enumerate(TRAJECTORY_DATASET, start=1):
        cid = case["id"]
        q = case["question"]
        expected_contains = case.get("expected_answer_contains", [])
        print(f"[{idx}/10] {cid}: {q}", flush=True)
        t_start = time.monotonic()
        try:
            res_b = run_multi_agent(q)
            m_b = res_b.get("metrics", {})
            elapsed_b = float(m_b.get("total_latency_seconds") or (time.monotonic() - t_start))
            ans_b = res_b.get("answer", "")
            tokens_b = int(m_b.get("total_model_tokens") or 0)
            payload_tokens_b = int(m_b.get("total_handoff_payload_tokens") or 0)
            cost_b = float(m_b.get("estimated_cost") or ((tokens_b / 1000.0) * COST_PER_1K_TOKENS))
            passed_b = answer_matches(ans_b, expected_contains)
            err_b = None
        except Exception as exc:
            elapsed_b = time.monotonic() - t_start
            ans_b = f"Exception: {type(exc).__name__}: {str(exc)}"
            tokens_b = 0
            payload_tokens_b = 0
            cost_b = 0.0
            passed_b = False
            err_b = str(exc)
            m_b = {}

        status_str = "PASS" if passed_b else "FAIL"
        print(f"  -> [{status_str}] in {elapsed_b:.4f}s | tokens: {tokens_b} | payload: {payload_tokens_b}", flush=True)

        rec = {
            "id": cid,
            "question": q,
            "answer": ans_b,
            "expected_contains": expected_contains,
            "passed": passed_b,
            "latency": round(elapsed_b, 4),
            "tokens": tokens_b,
            "handoff_payload_tokens": payload_tokens_b,
            "cost": round(cost_b, 6),
            "error": err_b,
            "specialist_call_count": m_b.get("specialist_call_count", 0),
            "handoff_count": m_b.get("handoff_count", 0),
        }
        multi_results.append(rec)

    # 2. Next run Arm A (Single-Agent) across all 10 cases
    print("\n--- RUNNING ARM A: SINGLE-AGENT (10 cases) ---", flush=True)
    single_results = []
    for idx, case in enumerate(TRAJECTORY_DATASET, start=1):
        cid = case["id"]
        q = case["question"]
        expected_contains = case.get("expected_answer_contains", [])
        print(f"[{idx}/10] {cid}: {q}", flush=True)
        t_start = time.monotonic()
        try:
            res_a = run_agent(q, prefer_mcp_tools=True)
            elapsed_a = res_a.get("elapsed_seconds") or (time.monotonic() - t_start)
            ans_a = res_a.get("answer", "")
            tokens_a = int(res_a.get("tokens_used") or 0)
            cost_a = float(res_a.get("estimated_cost") or ((tokens_a / 1000.0) * COST_PER_1K_TOKENS))
            passed_a = answer_matches(ans_a, expected_contains)
            err_a = None
            tools_used = res_a.get("tools_used", [])
        except Exception as exc:
            elapsed_a = time.monotonic() - t_start
            ans_a = f"Exception: {type(exc).__name__}: {str(exc)}"
            tokens_a = 0
            cost_a = 0.0
            passed_a = False
            err_a = str(exc)
            tools_used = []

        status_str = "PASS" if passed_a else "FAIL"
        print(f"  -> [{status_str}] in {elapsed_a:.2f}s | tokens: {tokens_a} | cost: ${cost_a:.6f}", flush=True)

        rec = {
            "id": cid,
            "question": q,
            "answer": ans_a,
            "expected_contains": expected_contains,
            "passed": passed_a,
            "latency": round(elapsed_a, 4),
            "tokens": tokens_a,
            "cost": round(cost_a, 6),
            "error": err_a,
            "tools_used": tools_used,
        }
        single_results.append(rec)

        # Save checkpoint after each single-agent case
        checkpoint = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "multi_agent": multi_results,
            "single_agent": single_results,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)

    # Aggregates
    n = len(TRAJECTORY_DATASET)
    sa_lat = [r["latency"] for r in single_results]
    ma_lat = [r["latency"] for r in multi_results]

    sa_summary = {
        "passed_count": sum(1 for r in single_results if r["passed"]),
        "failed_count": sum(1 for r in single_results if not r["passed"]),
        "pass_rate_pct": round(sum(1 for r in single_results if r["passed"]) / n * 100.0, 1),
        "p50_latency_seconds": round(statistics.median(sa_lat), 4),
        "p99_latency_seconds": round(calculate_percentile(sa_lat, 99.0), 4),
        "total_model_tokens": sum(r["tokens"] for r in single_results),
        "total_estimated_cost": round(sum(r["cost"] for r in single_results), 6),
        "avg_cost_per_question": round(sum(r["cost"] for r in single_results) / n, 6),
        "results": single_results,
    }

    ma_summary = {
        "passed_count": sum(1 for r in multi_results if r["passed"]),
        "failed_count": sum(1 for r in multi_results if not r["passed"]),
        "pass_rate_pct": round(sum(1 for r in multi_results if r["passed"]) / n * 100.0, 1),
        "p50_latency_seconds": round(statistics.median(ma_lat), 4),
        "p99_latency_seconds": round(calculate_percentile(ma_lat, 99.0), 4),
        "total_model_tokens": sum(r["tokens"] for r in multi_results),
        "total_handoff_payload_tokens": sum(r["handoff_payload_tokens"] for r in multi_results),
        "total_estimated_cost": round(sum(r["cost"] for r in multi_results), 6),
        "total_handoffs": sum(r["handoff_count"] for r in multi_results),
        "results": multi_results,
    }

    final_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": n,
        "single_agent": sa_summary,
        "multi_agent": ma_summary,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=2)

    print("\n" + "=" * 70, flush=True)
    print("FRESH EVALUATION COMPLETE", flush=True)
    print(f"Single-Agent Pass Rate: {sa_summary['pass_rate_pct']}% | p50: {sa_summary['p50_latency_seconds']}s | p99: {sa_summary['p99_latency_seconds']}s | Tokens: {sa_summary['total_model_tokens']}", flush=True)
    print(f"Multi-Agent Pass Rate:  {ma_summary['pass_rate_pct']}% | p50: {ma_summary['p50_latency_seconds']}s | p99: {ma_summary['p99_latency_seconds']}s | Tokens: {ma_summary['total_model_tokens']}", flush=True)
    print(f"Results saved to: {output_path}", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_fresh_eval()
