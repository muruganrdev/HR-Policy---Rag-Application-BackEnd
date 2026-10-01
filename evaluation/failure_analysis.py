"""Pure analysis helpers for Week 8 Agent failure traces."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any


TERMINATION_MODES = {
    "wall_clock": "WALL_CLOCK",
    "max_iterations": "MAX_ITERATIONS",
    "max_tokens": "MAX_TOKENS",
    "max_cost": "MAX_COST",
}

PRIMARY_FAILURE_MODES = (
    "TOOL_LOOP",
    "WRONG_TOOL",
    "WRONG_ARGUMENT",
    "WRONG_ORDER",
    "MISSING_TOOL",
    "PREMATURE_FINAL",
    "FINAL_ANSWER_ERROR",
    "TOOL_ERROR",
)


def classify_termination(reason: str | None) -> str | None:
    if reason is None:
        return None
    return TERMINATION_MODES.get(reason, "UNKNOWN_TERMINATION")


def _trace_tool_events(trace_steps: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for step in trace_steps:
        observation = step.get("observation", {})
        is_duplicate_attempt = (
            step.get("phase") == "observation"
            and isinstance(observation, dict)
            and observation.get("status") == "duplicate"
        )
        if step.get("tool") and (step.get("phase") == "tool" or is_duplicate_attempt):
            events.append(step)
    return events


def detect_repeated_tools(
    trace_steps: Sequence[dict[str, Any]] = (),
    actual_tools: Sequence[str] = (),
) -> dict[str, Any]:
    """Count extra calls/attempts and repeated arguments from ordered trace events."""
    events = _trace_tool_events(trace_steps)
    traced_tools = [event["tool"] for event in events]
    if not events or (actual_tools and traced_tools != list(actual_tools)):
        events = [{"tool": name} for name in actual_tools]

    counts = Counter(event["tool"] for event in events)
    repeated_counts = {name: count - 1 for name, count in counts.items() if count > 1}
    first_arguments: dict[str, Any] = {}
    identical_argument_repetitions = 0
    for event in events:
        tool = event["tool"]
        if "arguments" not in event:
            continue
        if tool not in first_arguments:
            first_arguments[tool] = event["arguments"]
        elif event["arguments"] == first_arguments[tool]:
            identical_argument_repetitions += 1

    return {
        "has_repeats": bool(repeated_counts),
        "repeated_tool_counts": repeated_counts,
        "repeat_attempts": sum(repeated_counts.values()),
        "identical_argument_repetitions": identical_argument_repetitions,
        "tool_event_count": len(events),
    }


def _has_tool_error(trace_steps: Sequence[dict[str, Any]]) -> bool:
    return any(
        step.get("phase") == "tool"
        and isinstance(step.get("observation"), dict)
        and step["observation"].get("status") == "error"
        for step in trace_steps
    )


def _arguments_mismatch(
    trace_steps: Sequence[dict[str, Any]],
    expected_arguments: Sequence[dict[str, Any]] | dict[str, dict[str, Any]] | None,
) -> bool:
    if expected_arguments is None:
        return False
    executed = [step for step in trace_steps if step.get("phase") == "tool"]
    if isinstance(expected_arguments, dict):
        return any(
            step.get("arguments") != expected_arguments.get(step.get("tool"))
            for step in executed
        )
    return any(
        index >= len(executed)
        or executed[index].get("arguments") != expected
        for index, expected in enumerate(expected_arguments)
    )


def classify_case(
    case: dict[str, Any],
    result: dict[str, Any],
    trace_steps: Sequence[dict[str, Any]] | None = None,
    expected_arguments: Sequence[dict[str, Any]] | dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assign one primary mode and, when relevant, a secondary termination mode."""
    steps = list(trace_steps if trace_steps is not None else result.get("steps", []))
    actual = list(result.get("actual_tools", []))
    expected_paths = case.get("expected_tool_sequences")
    if expected_paths is None:
        expected = case.get("expected_tools", [])
        expected_paths = expected if expected and isinstance(expected[0], list) else [expected]
    expected_paths = [list(path) for path in expected_paths]
    repeated = detect_repeated_tools(steps, actual)
    termination = classify_termination(result.get("termination_reason"))

    if _has_tool_error(steps):
        primary = "TOOL_ERROR"
    elif repeated["has_repeats"]:
        primary = "TOOL_LOOP"
    elif actual not in expected_paths:
        if any(Counter(actual) == Counter(path) for path in expected_paths):
            primary = "WRONG_ORDER"
        elif any(tool not in {name for path in expected_paths for name in path} for tool in actual):
            primary = "WRONG_TOOL"
        elif any(step.get("phase") == "final" for step in steps):
            primary = "PREMATURE_FINAL"
        else:
            primary = "MISSING_TOOL"
    elif _arguments_mismatch(steps, expected_arguments):
        primary = "WRONG_ARGUMENT"
    elif not result.get("answer_correct", False):
        primary = "FINAL_ANSWER_ERROR"
    elif termination is not None:
        primary = termination
    else:
        primary = "NONE"

    secondary = termination if termination is not None and termination != primary else None
    return {
        "primary_failure_mode": primary,
        "secondary_failure_mode": secondary,
        "termination_mode": termination,
        "repeated_tool_analysis": repeated,
    }


def find_outcome_trajectory_gaps(
    records: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("answer_correct") and not record.get("trajectory_correct")
    ]


def build_failure_matrix(
    dataset: Sequence[dict[str, Any]],
    records: Sequence[dict[str, Any]],
    *,
    traces: dict[str, Sequence[dict[str, Any]]] | None = None,
    notes: dict[str, str] | None = None,
    expected_arguments: dict[str, Sequence[dict[str, Any]] | dict[str, dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Join benchmark rows with trace classifications for CSV serialization."""
    records_by_id = {record["id"]: record for record in records}
    traces = traces or {}
    notes = notes or {}
    expected_arguments = expected_arguments or {}
    matrix = []
    for case in dataset:
        record = records_by_id[case["id"]]
        trace = traces.get(case["id"], ())
        classification = classify_case(
            case, record, trace, expected_arguments.get(case["id"])
        )
        matrix.append(
            {
                "case_id": case["id"],
                "question": case["question"],
                "answer_correct": record["answer_correct"],
                "trajectory_correct": record["trajectory_correct"],
                "expected_tools": " | ".join(
                    " -> ".join(path)
                    for path in (
                        case.get("expected_tool_sequences")
                        or ([case["expected_tools"]] if case.get("expected_tools") and isinstance(case["expected_tools"][0], str) else case.get("expected_tools", []))
                    )
                ),
                "actual_tools": " -> ".join(record.get("actual_tools", [])),
                "tool_choice_accuracy": record.get("tool_choice_accuracy"),
                "primary_failure_mode": classification["primary_failure_mode"],
                "secondary_failure_mode": classification["secondary_failure_mode"] or "",
                "termination_reason": record.get("termination_reason") or "none",
                "iterations": record.get("iterations"),
                "latency_seconds": record.get("latency"),
                "tokens": record.get("tokens"),
                "estimated_cost": record.get("estimated_cost"),
                "notes": notes.get(case["id"], ""),
            }
        )
    return matrix