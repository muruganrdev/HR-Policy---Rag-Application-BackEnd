"""Fixed-sequence HR workflow for annual leave disposition.

Runs the explicit sequence:
    Step 1: get_employee_data  (by ID or name)
    Step 2: lookup_annual_leave_policy
    Step 3: calculate_annual_leave_disposition
    Step 4: generate_final_answer

The workflow does NOT perform tool selection — it always runs all four steps.
Use the Agent (app/agent.py) for dynamic/flexible question answering.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

import ollama

from app.tools import (
    Jurisdiction,
    calculate_annual_leave_disposition,
    get_employee_data,
    lookup_annual_leave_policy,
)


OLLAMA_MODEL = "llama3"
OLLAMA_TEMPERATURE = 0.0


@dataclass
class WorkflowState:
    original_question: str
    employee_id: str | None = None
    employee_record: dict[str, Any] | None = None
    policy_result: dict[str, Any] | None = None
    calculation_result: dict[str, Any] | None = None
    final_answer: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    trace_lines: list[str] = field(default_factory=list)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Jurisdiction):
        return value.value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _emit(state: WorkflowState, line: str) -> None:
    state.trace_lines.append(line)
    print(line)


def _extract_content(response: Any) -> str:
    if isinstance(response, dict):
        message = response.get("message", {})
        if isinstance(message, dict):
            return str(message.get("content", "")).strip()
    message = getattr(response, "message", None)
    return str(getattr(message, "content", "")).strip()


def _extract_employee_id(question: str) -> str:
    """Extract a simple numeric employee ID (001-006) from the question text."""
    # Simple 3-digit ID: e.g. "005", "employee 003"
    match = re.search(r"\b(0\d{2})\b", question)
    if match:
        return match.group(1)
    raise ValueError(
        "Question must contain a numeric employee ID such as 005"
    )


def _extract_policy_limits(policy_result: dict[str, Any]) -> tuple[float, float]:
    policy_text = "\n".join(
        str(r.get("content", "")) for r in policy_result.get("results", [])
    )
    carry_match = re.search(
        r"up to\s+(\d+(?:\.\d+)?)\s+days may be carried over",
        policy_text,
        flags=re.IGNORECASE,
    )
    encash_match = re.search(
        r"maximum of\s+(\d+(?:\.\d+)?)\s+days may be encashed",
        policy_text,
        flags=re.IGNORECASE,
    )
    if carry_match is None or encash_match is None:
        raise ValueError(
            "Annual-leave policy limits were not found in policy evidence"
        )
    return float(carry_match.group(1)), float(encash_match.group(1))


def _grounded_answer_for_calculation(state: WorkflowState) -> str:
    """Build the definitive answer strictly from the observed calculation result."""
    calc = state.calculation_result or {}
    if not calc:
        raise ValueError("No calculation_result available for grounded final answer")

    def fmt(value: Any) -> str:
        if value is None:
            return "0"
        value = float(value)
        return str(int(value)) if value.is_integer() else str(value)

    parts: list[str] = []
    if "carryover_days" in calc:
        parts.append(f"{fmt(calc['carryover_days'])} days can be carried over")
    if "encashable_days" in calc:
        parts.append(f"{fmt(calc['encashable_days'])} days can be encashed")
    if "lapsed_days" in calc:
        parts.append(f"{fmt(calc['lapsed_days'])} days lapse")

    if not parts:
        raise ValueError("No annual-leave calculation values were observed")
    if len(parts) == 1:
        return f"{parts[0]}."
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}."
    return f"{parts[0]}, {parts[1]}, and {parts[2]}."


def _generate_final_answer(
    state: WorkflowState,
    chat_fn: Callable[..., Any],
) -> str:
    system_prompt = (
        "You are a deterministic HR policy assistant.\n"
        "The calculation_result is authoritative for the employee's annual leave disposition.\n"
        "Rules:\n"
        "1. Treat calculation_result as authoritative ground truth. Do not recalculate, reinterpret, or contradict it.\n"
        "2. Report the employee's exact calculated values (carryover_days, encashable_days, lapsed_days), NOT general policy maximums.\n"
        "3. Always report carryover, encashment, and lapse separately with their distinct numbers. Never merge, sum, or conflate carryover and encashment values.\n"
        "4. When reporting leave disposition, report all three outcomes: carryover days, encashable days, and lapsed days. If lapsed_days is 0, explicitly state that 0 days lapse.\n"
        "5. Do not invent tenure-based eligibility rules or claim the employee is ineligible.\n"
        "6. Do not invert logic: if balance is within the carryover limit, state that the balance can be carried over.\n"
        "7. Answer the user's question and state the exact calculated disposition numbers. Return only the concise final answer in plain text."
    )
    user_payload = {
        "question": state.original_question,
        "employee_record": _json_safe(state.employee_record),
        "policy_result": _json_safe(state.policy_result),
        "calculation_result": _json_safe(state.calculation_result),
        "instruction": (
            "The calculation_result is authoritative. Do not recalculate or reinterpret it. "
            "Answer the question and clearly distinguish the calculated disposition: "
            "state carryover, encashment, and lapse amounts separately (including 0 days lapse if lapsed_days is 0.0). "
            "Do not substitute general policy limits for the employee's calculated numbers. "
            "Return only the concise final answer in plain text."
        ),
    }
    response = chat_fn(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, indent=2)},
        ],
        options={"temperature": OLLAMA_TEMPERATURE},
    )
    answer = _extract_content(response)
    if not answer:
        raise ValueError("Model returned an empty final answer")

    if state.calculation_result is not None:
        return _grounded_answer_for_calculation(state)
    return answer


def _failure_result(state: WorkflowState, message: str) -> dict[str, Any]:
    state.final_answer = message
    state.steps.append({"phase": "final", "answer": message})
    _emit(state, f"[WORKFLOW STEP 4]\nAction: final_answer\n{message}")
    return {
        "question": state.original_question,
        "answer": message,
        "steps": _json_safe(state.steps),
        "iteration_count": 4,
        "trace": "\n".join(state.trace_lines),
    }


def run_workflow(
    question: str,
    *,
    chat_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Run the explicit fixed sequence: record → policy → calculation → answer."""
    state = WorkflowState(original_question=question)
    selected_chat = chat_fn or ollama.chat

    try:
        # Fixed Step 1: identify the employee and retrieve the record.
        state.employee_id = _extract_employee_id(question)
        _emit(state, "[WORKFLOW STEP 1]\nAction: get_employee_data")
        state.employee_record = get_employee_data(employee_id=state.employee_id)
        state.steps.append(
            {
                "phase": "tool",
                "tool": "get_employee_data",
                "arguments": {"employee_id": state.employee_id},
                "observation": {
                    "status": "success",
                    "result": _json_safe(state.employee_record),
                },
            }
        )
        _emit(
            state,
            f"Observation: {json.dumps(_json_safe(state.employee_record), sort_keys=True)}",
        )
    except Exception as error:
        state.steps.append(
            {
                "phase": "tool",
                "tool": "get_employee_data",
                "observation": {"status": "error", "error": str(error)},
            }
        )
        _emit(state, f"Observation: error: {error}")
        return _failure_result(
            state, f"Workflow stopped: employee lookup failed ({error})."
        )

    try:
        # Fixed Step 2: use jurisdiction returned by Step 1.
        jurisdiction = state.employee_record["jurisdiction"]
        _emit(state, "[WORKFLOW STEP 2]\nAction: lookup_annual_leave_policy")
        state.policy_result = lookup_annual_leave_policy(jurisdiction)
        state.steps.append(
            {
                "phase": "tool",
                "tool": "lookup_annual_leave_policy",
                "arguments": {"jurisdiction": _json_safe(jurisdiction)},
                "observation": {
                    "status": "success",
                    "result": _json_safe(state.policy_result),
                },
            }
        )
        _emit(
            state,
            f"Observation: policy results={len(state.policy_result.get('results', []))}",
        )
    except Exception as error:
        state.steps.append(
            {
                "phase": "tool",
                "tool": "lookup_annual_leave_policy",
                "observation": {"status": "error", "error": str(error)},
            }
        )
        _emit(state, f"Observation: error: {error}")
        return _failure_result(
            state, f"Workflow stopped: policy lookup failed ({error})."
        )

    try:
        # Fixed Step 3: extract limits from policy evidence, then calculate.
        carry_over_limit, encashment_limit = _extract_policy_limits(state.policy_result)
        arguments = {
            "leave_balance": state.employee_record["leave_balance"],
            "carry_over_limit": carry_over_limit,
            "encashment_limit": encashment_limit,
        }
        _emit(
            state,
            "[WORKFLOW STEP 3]\nAction: calculate_annual_leave_disposition",
        )
        state.calculation_result = calculate_annual_leave_disposition(**arguments)
        state.steps.append(
            {
                "phase": "tool",
                "tool": "calculate_annual_leave_disposition",
                "arguments": arguments,
                "observation": {
                    "status": "success",
                    "result": state.calculation_result,
                },
            }
        )
        _emit(
            state,
            f"Observation: {json.dumps(state.calculation_result, sort_keys=True)}",
        )
    except Exception as error:
        state.steps.append(
            {
                "phase": "tool",
                "tool": "calculate_annual_leave_disposition",
                "observation": {"status": "error", "error": str(error)},
            }
        )
        _emit(state, f"Observation: error: {error}")
        return _failure_result(
            state, f"Workflow stopped: calculation failed ({error})."
        )

    # Fixed Step 4: generate the answer; the model does not select tools.
    _emit(state, "[WORKFLOW STEP 4]\nAction: final_answer")
    try:
        state.final_answer = _generate_final_answer(state, selected_chat)
    except Exception as error:
        return _failure_result(
            state, f"Workflow stopped: final answer generation failed ({error})."
        )

    state.steps.append({"phase": "final", "answer": state.final_answer})
    _emit(state, state.final_answer)
    return {
        "question": state.original_question,
        "answer": state.final_answer,
        "steps": _json_safe(state.steps),
        "iteration_count": 4,
        "trace": "\n".join(state.trace_lines),
    }


if __name__ == "__main__":
    run_workflow("For employee 003, how should the current annual leave balance be handled?")
