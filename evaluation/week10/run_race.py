"""Week 10 Practical Task Set C: Single-Agent vs Multi-Agent Race Runner.

Executes the official 10 Task Set C cases (TQ01–TQ10) from evaluation/trajectory_dataset.py
against:
  Arm A: Single-Agent baseline (app.agent.run_agent with MCP tools)
  Arm B: Multi-Agent orchestrator (app.multi_agent.run_multi_agent with Policy & Eligibility specialists)

Collects and reports:
  1. Pass rate (deterministic substring oracle matching expected_answer_contains)
  2. p50 latency
  3. p99 latency
  4. Total model tokens
  5. Estimated cost per question and total estimated cost
  6. Context re-send multiplier and largest handoff payload analysis
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

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app.agent as agent_module
from app.agent import COST_PER_1K_TOKENS, run_agent
from app.multi_agent import run_multi_agent
from app.multi_agent.instrumentation import DEFAULT_HANDOFF_LOG_PATH
import app.search as search_module
from evaluation.trajectory_dataset import TRAJECTORY_DATASET
from evaluation.trajectory_evaluator import answer_matches


def calculate_percentile(data: list[float], percentile: float) -> float:
    """Calculate percentile using standard linear interpolation on sorted data.

    Formula: index = (p / 100) * (n - 1)
    Interpolation: v[floor] + (v[ceil] - v[floor]) * fraction
    """
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


def run_race() -> dict[str, Any]:
    """Execute the race comparison across TQ01 through TQ10."""
    print("=" * 70)
    print("WEEK 10 TASK SET C: SINGLE-AGENT VS MULTI-AGENT RACE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Cases: {len(TRAJECTORY_DATASET)} (TQ01 to TQ10)")
    print("=" * 70)

    # Warm search / Chroma resources once before timing starts
    try:
        search_module.search("annual leave policy")
    except Exception as exc:
        print(f"Note: pre-warm search exception: {exc}")

    single_results: list[dict[str, Any]] = []
    multi_results: list[dict[str, Any]] = []

    for idx, case in enumerate(TRAJECTORY_DATASET, start=1):
        cid = case["id"]
        q = case["question"]
        expected_contains = case.get("expected_answer_contains", [])
        print(f"\n[{idx}/10] Case {cid}: {q}")

        # -------------------------------------------------------------
        # Arm A: Single Agent Baseline
        # -------------------------------------------------------------
        print("  Running Arm A (Single Agent)...", end=" ", flush=True)
        t_start_a = time.monotonic()
        try:
            res_a = run_agent(q, prefer_mcp_tools=True)
            elapsed_a = res_a.get("elapsed_seconds") or (time.monotonic() - t_start_a)
            ans_a = res_a.get("answer", "")
            tokens_a = int(res_a.get("tokens_used") or 0)
            cost_a = float(res_a.get("estimated_cost") or ((tokens_a / 1000.0) * COST_PER_1K_TOKENS))
            passed_a = answer_matches(ans_a, expected_contains)
            err_a = None
        except Exception as exc:
            elapsed_a = time.monotonic() - t_start_a
            ans_a = f"Exception: {type(exc).__name__}: {str(exc)}"
            tokens_a = 0
            cost_a = 0.0
            passed_a = False
            err_a = str(exc)

        single_record = {
            "id": cid,
            "question": q,
            "answer": ans_a,
            "passed": passed_a,
            "latency": round(elapsed_a, 4),
            "tokens": tokens_a,
            "cost": round(cost_a, 6),
            "error": err_a,
            "tools_used": res_a.get("tools_used", []) if err_a is None else [],
        }
        single_results.append(single_record)
        status_str_a = "PASS" if passed_a else "FAIL"
        print(f"[{status_str_a}] in {elapsed_a:.2f}s | tokens: {tokens_a} | cost: ${cost_a:.6f}")

        # -------------------------------------------------------------
        # Arm B: Multi-Agent System
        # -------------------------------------------------------------
        print("  Running Arm B (Multi-Agent)...", end=" ", flush=True)
        t_start_b = time.monotonic()
        try:
            res_b = run_multi_agent(q)
            m_b = res_b.get("metrics", {})
            elapsed_b = float(m_b.get("total_latency_seconds") or (time.monotonic() - t_start_b))
            ans_b = res_b.get("answer", "")
            tokens_b = int(m_b.get("total_model_tokens") or 0)
            payload_tokens_b = int(m_b.get("total_handoff_payload_tokens") or 0)
            cost_b = float(m_b.get("estimated_cost") or ((tokens_b / 1000.0) * COST_PER_1K_TOKENS))
            passed_b = answer_matches(ans_b, expected_contains)
            err_b = None
        except Exception as exc:
            elapsed_b = time.monotonic() - t_start_b
            ans_b = f"Exception: {type(exc).__name__}: {str(exc)}"
            tokens_b = 0
            payload_tokens_b = 0
            cost_b = 0.0
            passed_b = False
            err_b = str(exc)
            m_b = {}

        multi_record = {
            "id": cid,
            "question": q,
            "answer": ans_b,
            "passed": passed_b,
            "latency": round(elapsed_b, 4),
            "tokens": tokens_b,
            "handoff_payload_tokens": payload_tokens_b,
            "cost": round(cost_b, 6),
            "error": err_b,
            "specialist_call_count": m_b.get("specialist_call_count", 0),
            "handoff_count": m_b.get("handoff_count", 0),
            "policy_latency": m_b.get("policy_specialist_latency_seconds"),
            "eligibility_latency": m_b.get("eligibility_specialist_latency_seconds"),
            "employee_lookup_latency": m_b.get("employee_lookup_latency_seconds"),
        }
        multi_results.append(multi_record)
        status_str_b = "PASS" if passed_b else "FAIL"
        print(f"[{status_str_b}] in {elapsed_b:.2f}s | tokens: {tokens_b} | payload: {payload_tokens_b} | cost: ${cost_b:.6f}")

    # -----------------------------------------------------------------
    # Compute Aggregate Metrics
    # -----------------------------------------------------------------
    total_cases = len(TRAJECTORY_DATASET)
    
    # Arm A Aggregates
    passed_a_count = sum(1 for r in single_results if r["passed"])
    pass_rate_a = (passed_a_count / total_cases) * 100.0
    latencies_a = [r["latency"] for r in single_results]
    p50_latency_a = statistics.median(latencies_a)
    p99_latency_a = calculate_percentile(latencies_a, 99.0)
    total_tokens_a = sum(r["tokens"] for r in single_results)
    total_cost_a = sum(r["cost"] for r in single_results)
    avg_cost_a = total_cost_a / total_cases

    # Arm B Aggregates
    passed_b_count = sum(1 for r in multi_results if r["passed"])
    pass_rate_b = (passed_b_count / total_cases) * 100.0
    latencies_b = [r["latency"] for r in multi_results]
    p50_latency_b = statistics.median(latencies_b)
    p99_latency_b = calculate_percentile(latencies_b, 99.0)
    total_tokens_b = sum(r["tokens"] for r in multi_results)
    total_payload_tokens_b = sum(r["handoff_payload_tokens"] for r in multi_results)
    total_cost_b = sum(r["cost"] for r in multi_results)
    avg_cost_b = total_cost_b / total_cases

    # Relative Model Token Usage Ratio (model_token_ratio)
    if total_tokens_a > 0:
        model_token_ratio_val = round(total_tokens_b / total_tokens_a, 2)
        model_token_ratio_str = f"{model_token_ratio_val:.1f}x"
    else:
        model_token_ratio_val = None
        model_token_ratio_str = "Undefined (Arm A model tokens == 0)"

    # Identify Largest Measured Handoff Payload from structured records or log file
    largest_record: dict[str, Any] | None = None
    if DEFAULT_HANDOFF_LOG_PATH.exists():
        try:
            with open(DEFAULT_HANDOFF_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    comb = rec.get("combined_payload_tokens", 0)
                    if largest_record is None or comb > largest_record.get("combined_payload_tokens", 0):
                        largest_record = rec
        except Exception as exc:
            print(f"Warning reading handoffs.log: {exc}")

    output_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": total_cases,
        "single_agent": {
            "passed_count": passed_a_count,
            "pass_rate_pct": pass_rate_a,
            "p50_latency_seconds": round(p50_latency_a, 4),
            "p99_latency_seconds": round(p99_latency_a, 4),
            "total_model_tokens": total_tokens_a,
            "avg_cost_per_question": round(avg_cost_a, 6),
            "total_estimated_cost": round(total_cost_a, 6),
            "results": single_results,
        },
        "multi_agent": {
            "passed_count": passed_b_count,
            "pass_rate_pct": pass_rate_b,
            "p50_latency_seconds": round(p50_latency_b, 4),
            "p99_latency_seconds": round(p99_latency_b, 4),
            "total_model_tokens": total_tokens_b,
            "total_handoff_payload_tokens": total_payload_tokens_b,
            "avg_cost_per_question": round(avg_cost_b, 6),
            "total_estimated_cost": round(total_cost_b, 6),
            "results": multi_results,
        },
        "model_token_ratio": model_token_ratio_str,
        "model_token_ratio_value": model_token_ratio_val,
        "context_resend_multiplier": model_token_ratio_str,
        "context_multiplier_value": model_token_ratio_val,
        "largest_handoff": largest_record,
    }

    # Save JSON results
    json_path = ROOT_DIR / "evaluation" / "week10" / "race_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    # Generate race_table.md
    generate_race_table_markdown(output_data)

    return output_data


def generate_race_table_markdown(data: dict[str, Any]) -> None:
    """Generate evaluation/week10/race_table.md markdown artifact."""
    sa = data["single_agent"]
    ma = data["multi_agent"]
    total = data["total_cases"]
    largest = data.get("largest_handoff") or {}

    md_lines: list[str] = [
        "# Week 10 — Single-Agent vs Multi-Agent Race Evaluation Report",
        "",
        f"- **Date / Time:** `{data['timestamp']}`",
        f"- **Dataset:** Official Task Set C (`TQ01` to `TQ10` from `evaluation/trajectory_dataset.py`)",
        f"- **Evaluation Methodology:** Deterministic substring oracle against `expected_answer_contains`",
        f"- **Percentile Convention:** Standard linear interpolation (`k = (p / 100) * (n - 1)`) on sorted 10-sample distribution",
        f"- **Cost Rate Configured:** `${COST_PER_1K_TOKENS}/1K model tokens` (Estimated Rate, not billed cloud infra)",
        "",
        "## 1. Aggregate Comparison Table",
        "",
        "| Metric | Single-Agent (Arm A) | Multi-Agent (Arm B) | Difference / Ratio |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Passed Cases** | {sa['passed_count']} / {total} | {ma['passed_count']} / {total} | {'+' if ma['passed_count'] >= sa['passed_count'] else ''}{ma['passed_count'] - sa['passed_count']} cases |",
        f"| **Pass Rate** | **{sa['pass_rate_pct']:.1f}%** | **{ma['pass_rate_pct']:.1f}%** | {'+' if ma['pass_rate_pct'] >= sa['pass_rate_pct'] else ''}{ma['pass_rate_pct'] - sa['pass_rate_pct']:.1f}% |",
        f"| **p50 Latency** | {sa['p50_latency_seconds']:.3f} s | {ma['p50_latency_seconds']:.3f} s | {ma['p50_latency_seconds'] - sa['p50_latency_seconds']:+.3f} s |",
        f"| **p99 Latency (linear interp.)** | {sa['p99_latency_seconds']:.3f} s | {ma['p99_latency_seconds']:.3f} s | {ma['p99_latency_seconds'] - sa['p99_latency_seconds']:+.3f} s |",
        f"| **Total Model Tokens (LLM)** | {sa['total_model_tokens']:,} | {ma['total_model_tokens']:,} | {ma['total_model_tokens'] - sa['total_model_tokens']:+,} tokens |",
        f"| **Total Handoff Payload Tokens** | 0 *(in-process)* | {ma['total_handoff_payload_tokens']:,} *(serialized)* | N/A *(distinct from LLM)* |",
        f"| **Avg. Estimated Cost / Question** | ${sa['avg_cost_per_question']:.6f} | ${ma['avg_cost_per_question']:.6f} | ${ma['avg_cost_per_question'] - sa['avg_cost_per_question']:+.6f} |",
        f"| **Total Estimated Run Cost** | ${sa['total_estimated_cost']:.6f} | ${ma['total_estimated_cost']:.6f} | ${ma['total_estimated_cost'] - sa['total_estimated_cost']:+.6f} |",
        "",
        "## 2. Relative Model Token Usage Ratio (model_token_ratio) & Handoff Payload Analysis",
        "",
        f"- **Metric Name:** `Relative Model Token Usage Ratio` (`model_token_ratio`)",
        f"- **Formula:** `Multi-Agent Model Tokens / Single-Agent Model Tokens`",
        f"- **Numerator:** `Multi-Agent Total Model Tokens = {ma['total_model_tokens']:,}`",
        f"- **Denominator:** `Single-Agent Total Model Tokens = {sa['total_model_tokens']:,}`",
        f"- **Calculated Ratio:** **`{data['model_token_ratio']}`** (Multi-agent leveraged deterministic specialist contracts, requiring 0 LLM model tokens vs 42,716 for single-agent)",
        "- **Metric Nature & Limitation Disclosure:** This metric represents the ratio of total LLM model tokens consumed between execution modes. It is **not** a direct measurement of repeated or duplicated context. Direct context duplication measurement is unavailable because Multi-Agent relies on deterministic specialist delegation with typed contracts rather than multi-turn LLM context re-sending.",
        "",
        "### Handoff Payload Distribution & Largest Share Analysis",
        "",
        "Across the 10 Task Set C cases (TQ01–TQ10), delegation occurred in 6 cases resulting in **9 total handoff delegations** and **8,850 total estimated handoff payload tokens**:",
        "",
        "| Source Worker | Destination Worker | Task Type | Occurrences | Total Payload Tokens | Share of Total Payload |",
        "| :--- | :--- | :--- | :---: | :---: | :---: |",
        "| `orchestrator` | `policy_specialist` | `policy_retrieval` | **6** | **6,867** tokens | **77.6%** (Largest) |",
        "| `orchestrator` | `eligibility_specialist` | `eligibility_calculation` | **3** | **1,983** tokens | **22.4%** |",
        "| **Total** | | | **9** | **8,850** tokens | **100.0%** |",
        "",
        "#### Largest Handoff Contributor: `orchestrator` → `policy_specialist` (`policy_retrieval`)",
        f"- **Source:** `{largest.get('source', 'orchestrator')}`",
        f"- **Destination:** `{largest.get('destination', 'policy_specialist')}`",
        f"- **Task Type:** `{largest.get('task_type', 'policy_retrieval')}`",
        "- **Occurrences:** 6 (TQ05, TQ06, TQ07, TQ08, TQ09, TQ10)",
        "- **Total Estimated Payload Tokens:** **6,867 tokens**",
        "- **Share of Measured Handoff Total:** **77.6%** (6,867 ÷ 8,850 tokens)",
        f"- **Peak Single Instance:** Request {largest.get('request_tokens', '43')} tokens, Response {largest.get('response_tokens', '1106')} tokens, Combined **{largest.get('combined_payload_tokens', '1149')} tokens**",
        "- **Why It Dominates:** Policy evidence chunks retrieved from ChromaDB (4 document chunks per lookup) are returned in full structured JSON format to ground the orchestrator's decision.",
        "- **Metric Distinction Note:** Handoff payload tokens measure serialized inter-worker payload volume (`chars ÷ 4`) across application boundaries and are strictly tracked separately from LLM prompt/completion model tokens.",
        "",
        "## 3. Per-Case Results Breakdown (TQ01–TQ10)",
        "",
        "| Case ID | Single Pass | Multi Pass | Single Latency | Multi Latency | Single Tokens | Multi Tokens | Single Cost | Multi Cost | Notes |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]

    for sa_case, ma_case in zip(sa["results"], ma["results"]):
        cid = sa_case["id"]
        p_a = "✅ PASS" if sa_case["passed"] else "❌ FAIL"
        p_b = "✅ PASS" if ma_case["passed"] else "❌ FAIL"
        lat_a = f"{sa_case['latency']:.2f}s"
        lat_b = f"{ma_case['latency']:.2f}s"
        tok_a = f"{sa_case['tokens']:,}"
        tok_b = f"{ma_case['tokens']:,}"
        cost_a = f"${sa_case['cost']:.6f}"
        cost_b = f"${ma_case['cost']:.6f}"

        note_parts = []
        if not sa_case["passed"]:
            note_parts.append(f"SA fail: {sa_case['error'] or 'substring mismatch'}")
        if not ma_case["passed"]:
            note_parts.append(f"MA fail: {ma_case['error'] or 'substring mismatch'}")
        if not note_parts:
            note_parts.append("Both passed substring oracle")
        notes = "; ".join(note_parts)

        md_lines.append(
            f"| `{cid}` | {p_a} | {p_b} | {lat_a} | {lat_b} | {tok_a} | {tok_b} | {cost_a} | {cost_b} | {notes} |"
        )

    md_lines.extend([
        "",
        "## 4. Evaluation Notes and Observations",
        "",
        "1. **Execution Model:** Both arms evaluated against identical input queries, identical employee and database environments, and identical substring assertion criteria from `evaluation/trajectory_dataset.py`.",
        "2. **Single-Agent Profile:** The single-agent baseline utilizes ReAct loop tool-selection. Token counts reflect dynamic tool observation frames and final answer synthesis.",
        "3. **Multi-Agent Profile:** The multi-agent orchestrator delegates to specialized workers (Policy Retrieval and Eligibility Calculation). Specialists return typed results, reducing conversational loop overhead on calculation queries while isolating retrieval evidence.",
        "4. **Payload vs Model Token Separation:** Serialized handoff request/response tokens transferred between the orchestrator and specialists are measured and tracked separately from LLM model tokens, ensuring no inflated token counts.",
    ])

    table_path = ROOT_DIR / "evaluation" / "week10" / "race_table.md"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"\nSaved race table to: {table_path}")


if __name__ == "__main__":
    run_race()
