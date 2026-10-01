"""Evaluate HR agent outcomes and tool-call trajectories.

Produces all required Week 8 metrics:
  - Total cases
  - Outcome pass rate
  - Trajectory pass rate
  - Outcome-vs-trajectory gap
  - Tool-choice accuracy
  - Argument validity rate
  - Step efficiency
  - Cost p50 and max
  - Average latency / P50 latency
  - Mean cost
  - Tokens
  - Termination reasons
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import statistics
import csv
from pathlib import Path
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

from app.agent import COST_PER_1K_TOKENS, _policy_numeric_limit, run_agent
from app.tools import DATABASE_PATH, Jurisdiction
from evaluation.failure_analysis import (
    PRIMARY_FAILURE_MODES,
    TERMINATION_MODES,
    build_failure_matrix,
    classify_case,
)
from evaluation.trajectory_dataset import TRAJECTORY_DATASET


# ---------------------------------------------------------------------------
# Known grounded argument values for syntactic + semantic validation
# ---------------------------------------------------------------------------

def _database_has_value(column: str, value: str) -> bool:
    allowed_columns = {"employee_id", "employee_name", "department", "manager_name"}
    if column not in allowed_columns:
        return False
    with sqlite3.connect(DATABASE_PATH) as connection:
        row = connection.execute(
            f"SELECT 1 FROM employees WHERE LOWER({column}) = LOWER(?) LIMIT 1",
            (value,),
        ).fetchone()
    return row is not None


def _grounded_calculation_arguments(
    arguments: dict[str, Any], steps: Sequence[dict[str, Any]]
) -> bool:
    employee_result = None
    policy_result = None
    for step in steps:
        observation = step.get("observation", {})
        if step.get("phase") != "tool" or not isinstance(observation, dict):
            continue
        if observation.get("status") != "success":
            continue
        if step.get("tool") == "get_employee_data":
            employee_result = observation.get("result")
        elif step.get("tool") == "lookup_annual_leave_policy":
            policy_result = observation.get("result")

    if not isinstance(employee_result, dict) or not isinstance(policy_result, dict):
        return False
    expected = {
        "leave_balance": employee_result.get("leave_balance"),
        "carry_over_limit": _policy_numeric_limit(policy_result, keyword="carry_over"),
        "encashment_limit": _policy_numeric_limit(policy_result, keyword="encashment"),
    }
    return all(
        value is not None and math.isclose(float(arguments[key]), float(value))
        for key, value in expected.items()
    )


def _validate_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
    steps: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Check argument shape separately from grounding in live data/observations."""
    def result(syntactic: bool, grounded: bool, reason: str) -> dict[str, Any]:
        return {
            "syntactic_valid": syntactic,
            "grounded_valid": grounded,
            "valid": syntactic and grounded,
            "reason": reason,
        }

    if tool_name == "get_employee_data":
        emp_id = arguments.get("employee_id")
        emp_name = arguments.get("employee_name")
        if (emp_id is None) == (emp_name is None) or set(arguments) - {"employee_id", "employee_name"}:
            return result(False, False, "supply exactly one supported employee identifier")
        if emp_id is not None:
            syntactic = isinstance(emp_id, str) and bool(re.fullmatch(r"\d{3}", emp_id))
            grounded = syntactic and _database_has_value("employee_id", emp_id)
            return result(syntactic, grounded, "ok" if grounded else "employee_id is not present in the database")
        syntactic = isinstance(emp_name, str) and bool(emp_name.strip())
        grounded = syntactic and _database_has_value("employee_name", emp_name.strip())
        return result(syntactic, grounded, "ok" if grounded else "employee_name is not present in the database")

    if tool_name == "get_department_employees":
        dept = arguments.get("department_name")
        syntactic = isinstance(dept, str) and bool(dept.strip()) and set(arguments) == {"department_name"}
        grounded = syntactic and _database_has_value("department", dept.strip())
        return result(syntactic, grounded, "ok" if grounded else "department_name is not present in the database")

    if tool_name == "get_employees_by_manager":
        mgr = arguments.get("manager_name")
        syntactic = isinstance(mgr, str) and bool(mgr.strip()) and set(arguments) == {"manager_name"}
        grounded = syntactic and _database_has_value("manager_name", mgr.strip())
        return result(syntactic, grounded, "ok" if grounded else "manager_name is not present in the database")

    if tool_name == "lookup_annual_leave_policy":
        jur = arguments.get("jurisdiction")
        jur_value = jur.value if isinstance(jur, Jurisdiction) else jur
        syntactic = isinstance(jur_value, str) and set(arguments) == {"jurisdiction"}
        grounded = syntactic and jur_value in {item.value for item in Jurisdiction}
        return result(syntactic, grounded, "ok" if grounded else "jurisdiction is unsupported")

    if tool_name == "calculate_annual_leave_disposition":
        required = {"leave_balance", "carry_over_limit", "encashment_limit"}
        syntactic = set(arguments) == required and all(
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and value >= 0
            for value in arguments.values()
        )
        grounded = syntactic and _grounded_calculation_arguments(arguments, steps)
        return result(
            syntactic,
            grounded,
            "ok" if grounded else "calculation inputs are not grounded in successful observations",
        )

    return result(False, False, "unknown tool is not validated")


def _argument_validity_for_result(result: dict[str, Any]) -> dict[str, Any]:
    """Scan all executed tool steps and validate their arguments."""
    valid_count = 0
    syntactic_count = 0
    grounded_count = 0
    total_count = 0
    details = []
    for step in _tool_attempt_events(result):
        tool = step.get("tool", "")
        args = step.get("arguments", {})
        check = _validate_tool_arguments(tool, args, result.get("steps", []))
        total_count += 1
        if check["valid"]:
            valid_count += 1
        if check["syntactic_valid"]:
            syntactic_count += 1
        if check["grounded_valid"]:
            grounded_count += 1
        details.append({"tool": tool, "arguments": args, **check})
    return {
        "valid_arguments": valid_count,
        "total_arguments": total_count,
        "syntactically_valid_arguments": syntactic_count,
        "grounded_valid_arguments": grounded_count,
        "argument_validity_rate": valid_count / total_count if total_count else 1.0,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Trajectory helpers — support alternate-path cases
# ---------------------------------------------------------------------------

def _tool_attempt_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Read executed and duplicate-blocked calls in trace order when available."""
    trace = result.get("trace", "")
    events = []
    lines = trace.splitlines()
    index = 0
    while index < len(lines):
        action_match = re.match(r"Action: ([A-Za-z0-9_]+)$", lines[index])
        duplicate_match = re.match(
            r"Duplicate tool call prevented: ([A-Za-z0-9_]+) with arguments (\{.*\})\.$",
            lines[index],
        )
        if action_match and index + 1 < len(lines):
            arguments_match = re.match(r"Arguments: (\{.*\})$", lines[index + 1])
            if arguments_match:
                try:
                    arguments = json.loads(arguments_match.group(1))
                except json.JSONDecodeError:
                    arguments = {}
                events.append({"tool": action_match.group(1), "arguments": arguments})
                index += 2
                continue
        if duplicate_match:
            try:
                arguments = json.loads(duplicate_match.group(2))
            except json.JSONDecodeError:
                arguments = {}
            events.append({"tool": duplicate_match.group(1), "arguments": arguments})
        index += 1

    if events:
        return events
    return [
        {"tool": step["tool"], "arguments": step.get("arguments", {})}
        for step in result.get("steps", [])
        if step.get("tool")
        and (
            step.get("phase") == "tool"
            or (
                step.get("phase") == "observation"
                and isinstance(step.get("observation"), dict)
                and step["observation"].get("status") == "duplicate"
            )
        )
    ]


def actual_tool_sequence(result: dict[str, Any]) -> list[str]:
    """Return executed and duplicate-blocked tool attempts in actual order."""
    return [event["tool"] for event in _tool_attempt_events(result)]


def _flatten_expected(expected_tools: Any) -> list[list[str]]:
    """Return a list of accepted sequences.

    expected_tools may be:
      ["toolA", "toolB"]              -> one accepted path
      [["toolA", "toolB"], ["toolB", "toolA"]] -> two accepted paths
    """
    if not expected_tools:
        return [[]]
    if isinstance(expected_tools[0], list):
        return [list(path) for path in expected_tools]
    return [list(expected_tools)]


def _expected_sequences(case: dict[str, Any]) -> list[list[str]]:
    return _flatten_expected(
        case.get("expected_tool_sequences", case.get("expected_tools", []))
    )


def compare_tool_sequences(
    expected_tools: Any, actual: Sequence[str]
) -> dict[str, Any]:
    """Compare ordered tool sequences; support alternate accepted paths.

    Tool-choice accuracy is positional: position-by-position match ratio
    against the best-matching accepted path.  Duplicate attempts count as
    extra actual steps, increasing the denominator.
    """
    accepted_paths = _flatten_expected(expected_tools)
    actual_list = list(actual)
    best: dict[str, Any] | None = None
    for path in accepted_paths:
        denominator = max(len(path), len(actual_list))
        matches = sum(
            path[i] == actual_list[i]
            for i in range(min(len(path), len(actual_list)))
        )
        is_exact = path == actual_list
        candidate = {
            "trajectory_correct": is_exact,
            "tool_choice_accuracy": matches / denominator if denominator else 1.0,
            "matched_tool_choices": matches,
            "tool_choice_slots": denominator,
            "matched_path": path,
        }
        if best is None or candidate["tool_choice_accuracy"] > best["tool_choice_accuracy"]:
            best = candidate
    return best or {
        "trajectory_correct": False,
        "tool_choice_accuracy": 0.0,
        "matched_tool_choices": 0,
        "tool_choice_slots": 1,
        "matched_path": [],
    }


def answer_matches(answer: str, expected_contains: Sequence[str]) -> bool:
    """Require every answer-key phrase to occur, case-insensitively."""
    normalized = answer.casefold()
    return all(phrase.casefold() in normalized for phrase in expected_contains)


def extract_latency(result: dict[str, Any]) -> float | None:
    value = result.get("elapsed_seconds")
    return float(value) if value is not None else None


def calculate_task_cost(
    result: dict[str, Any], cost_per_1k_tokens: float = COST_PER_1K_TOKENS
) -> float:
    recorded = result.get("estimated_cost")
    if recorded is not None:
        return float(recorded)
    tokens = int(result.get("tokens_used", 0))
    return (tokens / 1000) * cost_per_1k_tokens


def _step_efficiency(
    case: dict[str, Any], actual_tools: list[str], expected_path: Sequence[str] | None = None
) -> float:
    """steps_taken / steps_needed.  Ratio >= 1.0; exact = 1.0.

    For alternate-path cases uses the accepted path length that best
    matches the actual sequence.  Duplicate attempts inflate steps_taken.
    """
    accepted_paths = _expected_sequences(case)
    steps_taken = len(actual_tools)
    if expected_path is not None:
        steps_needed = len(expected_path)
    else:
        steps_needed = len(min(accepted_paths, key=lambda path: abs(len(path) - steps_taken)))
    if steps_needed == 0:
        return 1.0
    return steps_taken / steps_needed


# ---------------------------------------------------------------------------
# Per-case evaluation
# ---------------------------------------------------------------------------

def evaluate_case(
    case: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    actual_tools = actual_tool_sequence(result)
    accepted_paths = _expected_sequences(case)
    seq_cmp = compare_tool_sequences(accepted_paths, actual_tools)
    arg_validity = _argument_validity_for_result(result)
    efficiency = _step_efficiency(case, actual_tools, seq_cmp["matched_path"])
    expected_arguments = case.get("expected_arguments", {})
    tool_steps = _tool_attempt_events(result)
    expected_argument_matches = sum(
        step.get("arguments") == expected_arguments.get(step.get("tool"))
        for step in tool_steps
    )
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_tools": accepted_paths,
        "expected_arguments": expected_arguments,
        "expected_answer_contains": case.get("expected_answer_contains", []),
        "actual_tools": actual_tools,
        "expected_argument_matches": expected_argument_matches,
        "expected_argument_count": len(tool_steps),
        "expected_arguments_correct": expected_argument_matches == len(tool_steps),
        "answer": result.get("answer", ""),
        "answer_correct": answer_matches(
            result.get("answer", ""), case.get("expected_answer_contains", [])
        ),
        **seq_cmp,
        "step_efficiency": efficiency,
        "argument_validity": arg_validity,
        "iterations": result.get("iteration_count", result.get("iterations_used", 0)),
        "latency": extract_latency(result),
        "tokens": result.get("tokens_used"),
        "estimated_cost": calculate_task_cost(result),
        "termination_reason": result.get("termination_reason"),
    }


def find_outcome_trajectory_gaps(
    records: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        r for r in records
        if r["answer_correct"] and not r["trajectory_correct"]
    ]


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

def summarize_metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    count = len(records)
    if count == 0:
        return {}

    latencies = [r["latency"] for r in records if r["latency"] is not None]
    costs = [r["estimated_cost"] for r in records]
    costs_sorted = sorted(costs)

    outcome_pass = sum(r["answer_correct"] for r in records)
    traj_pass = sum(r["trajectory_correct"] for r in records)

    # Tool-choice accuracy: aggregate positional matches across all cases
    total_slots = sum(r["tool_choice_slots"] for r in records)
    total_matches = sum(r["matched_tool_choices"] for r in records)
    tool_choice_acc = total_matches / total_slots if total_slots else 1.0

    # Argument validity: aggregate across all executed steps
    total_valid_args = sum(r["argument_validity"]["valid_arguments"] for r in records)
    total_args = sum(r["argument_validity"]["total_arguments"] for r in records)
    arg_validity_rate = total_valid_args / total_args if total_args else 1.0

    # Step efficiency: mean ratio steps_taken / steps_needed
    efficiencies = [r["step_efficiency"] for r in records]
    mean_efficiency = statistics.mean(efficiencies)

    # Cost p50 and max
    p50_cost = statistics.median(costs_sorted)
    max_cost = max(costs_sorted)

    outcome_rate = outcome_pass / count
    traj_rate = traj_pass / count

    return {
        "case_count": count,
        "outcome_pass_rate": outcome_rate,
        "trajectory_pass_rate": traj_rate,
        "outcome_trajectory_gap": round(outcome_rate - traj_rate, 4),
        "tool_choice_accuracy": round(tool_choice_acc, 4),
        "argument_validity_rate": round(arg_validity_rate, 4),
        "valid_arguments": total_valid_args,
        "total_arguments": total_args,
        "syntactically_valid_arguments": sum(
            r["argument_validity"].get("syntactically_valid_arguments", 0)
            for r in records
        ),
        "grounded_valid_arguments": sum(
            r["argument_validity"].get("grounded_valid_arguments", 0)
            for r in records
        ),
        "step_efficiency_mean": round(mean_efficiency, 4),
        "step_efficiency": round(mean_efficiency, 4),
        "cost_p50": round(p50_cost, 6),
        "cost_max": round(max_cost, 6),
        "average_latency": round(statistics.mean(latencies), 3) if latencies else None,
        "p50_latency": round(statistics.median(latencies), 3) if latencies else None,
        "mean_cost_per_task": round(statistics.mean(costs), 6) if costs else None,
        "total_tokens": sum(r["tokens"] or 0 for r in records),
        "termination_reasons": dict(Counter(
            r["termination_reason"] or "none" for r in records
        )),
    }


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------

def run_evaluation(
    dataset: Sequence[dict[str, Any]] = TRAJECTORY_DATASET,
    agent_runner: Callable[[str], dict[str, Any]] = run_agent,
) -> dict[str, Any]:
    records = []
    for case in dataset:
        result = agent_runner(case["question"])
        record = evaluate_case(case, result)
        record["steps"] = result.get("steps", [])
        classification = classify_case(
            case,
            record,
            record["steps"],
            expected_arguments=case.get("expected_arguments"),
        )
        record["primary_failure_mode"] = classification["primary_failure_mode"]
        record["secondary_failure_mode"] = classification["secondary_failure_mode"]
        records.append(record)
    metrics = summarize_metrics(records)
    gaps = find_outcome_trajectory_gaps(records)
    failure_mode_counts = Counter()
    for record in records:
        primary = record["primary_failure_mode"]
        if primary != "NONE":
            failure_mode_counts[primary] += 1
        secondary = record["secondary_failure_mode"]
        if secondary:
            failure_mode_counts[secondary] += 1
    known_modes = (*PRIMARY_FAILURE_MODES, *TERMINATION_MODES.values())
    return {
        "results": records,
        "metrics": metrics,
        "outcome_trajectory_gaps": gaps,
        "failure_mode_counts": {
            mode: failure_mode_counts.get(mode, 0) for mode in known_modes
        },
    }


# ---------------------------------------------------------------------------
# Human-readable console report
# ---------------------------------------------------------------------------

def _print_report(report: dict[str, Any]) -> None:
    m = report["metrics"]
    gaps = report.get("outcome_trajectory_gaps", [])
    print("\n" + "=" * 60)
    print("HR AGENT TRAJECTORY EVALUATION REPORT")
    print("=" * 60)
    print(f"Cases:                    {m['case_count']}")
    print(f"Outcome pass rate:        {m['outcome_pass_rate']:.0%}  ({sum(r['answer_correct'] for r in report['results'])}/{m['case_count']})")
    print(f"Trajectory pass rate:     {m['trajectory_pass_rate']:.0%}  ({sum(r['trajectory_correct'] for r in report['results'])}/{m['case_count']})")
    print(f"Outcome-vs-traj gap:      {m['outcome_trajectory_gap']:+.2%}")
    print()
    print(f"Tool-choice accuracy:     {m['tool_choice_accuracy']:.0%}")
    print(f"Argument validity rate:   {m['argument_validity_rate']:.0%}  ({m['valid_arguments']}/{m['total_arguments']})")
    print(
        "  Syntactic / grounded:   "
        f"{m['syntactically_valid_arguments']}/{m['total_arguments']} / "
        f"{m['grounded_valid_arguments']}/{m['total_arguments']}"
    )
    print(f"Step efficiency (mean):   {m['step_efficiency_mean']:.3f}  (1.00 = no extra steps)")
    print()
    if m["cost_p50"] is not None:
        print(f"Cost p50:                 ${m['cost_p50']:.6f}")
        print(f"Cost max:                 ${m['cost_max']:.6f}")
        print(f"Mean cost / task:         ${m['mean_cost_per_task']:.6f}")
    if m["average_latency"] is not None:
        print(f"Average latency:          {m['average_latency']:.3f}s")
        print(f"P50 latency:              {m['p50_latency']:.3f}s")
    print(f"Total tokens:             {m['total_tokens']}")
    print(f"Termination reasons:      {m['termination_reasons']}")
    print(f"Failure mode counts:      {report['failure_mode_counts']}")
    print()

    if gaps:
        print("OUTCOME-VS-TRAJECTORY GAPS (correct answer, wrong path):")
        for g in gaps:
            print(f"  [{g['id']}] {g['question'][:60]}")
            print(f"    Expected: {g['matched_path']}")
            print(f"    Actual:   {g['actual_tools']}")
            print("    Why path failed: actual tool attempts did not exactly match an accepted sequence.")
            print(
                "    Why answer passed: all expected answer phrases occurred: "
                f"{g['expected_answer_contains']}"
            )
    else:
        print(
            "Live outcome-vs-trajectory gap: "
            f"{m['outcome_trajectory_gap'] * 100:+.2f} percentage points."
        )
        print("No live benchmark case produced a correct final answer")
        print("with an incorrect trajectory.")
    print()

    print("PER-CASE SUMMARY:")
    print(f"  {'ID':<6} {'Outcome':<8} {'Traj':<6} {'Eff':<6} {'ArgV':<6}  {'Tools (actual)'}")
    print("  " + "-" * 70)
    for r in report["results"]:
        outcome = "PASS" if r["answer_correct"] else "FAIL"
        traj = "OK" if r["trajectory_correct"] else "WRONG"
        eff = f"{r['step_efficiency']:.2f}"
        argv = f"{r['argument_validity']['valid_arguments']}/{r['argument_validity']['total_arguments']}"
        tools = " -> ".join(r["actual_tools"]) or "(none)"
        print(f"  {r['id']:<6} {outcome:<8} {traj:<6} {eff:<6} {argv:<6}  {tools}")
    print("=" * 60)


def main() -> None:
    report = run_evaluation()
    _print_report(report)
    dataset_by_id = {case["id"]: case for case in TRAJECTORY_DATASET}
    rows = build_failure_matrix(
        TRAJECTORY_DATASET,
        report["results"],
        traces={record["id"]: record["steps"] for record in report["results"]},
        expected_arguments={
            case_id: case["expected_arguments"]
            for case_id, case in dataset_by_id.items()
        },
    )
    if rows:
        output_path = Path(__file__).with_name("failure_analysis.csv")
        with open(output_path, "w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    # Also dump raw JSON for downstream analysis
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
