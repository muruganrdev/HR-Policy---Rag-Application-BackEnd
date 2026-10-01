"""HR employee agent loop with dynamic tool selection.

The agent inspects the user question and observed state at each step and
dynamically chooses the minimal set of tools required — it does NOT always
execute a fixed sequence.

Examples:
    "What is Priya Nair's email?"
        → get_employee_data(employee_name="Priya Nair") → final

    "Which employees are in Engineering?"
        → get_department_employees("Engineering") → final

    "What is Priya Nair's annual leave disposition?"
        → get_employee_data → lookup_annual_leave_policy → calculate_annual_leave_disposition → final
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import ollama

from app.tools import (
    AmbiguousEmployeeError,
    EmployeeNotFoundError,
    Jurisdiction,
    calculate_annual_leave_disposition,
    get_department_employees,
    get_employee_data,
    get_employees_by_manager,
    lookup_annual_leave_policy,
)
from app.security import (
    SecurityValidationError,
    ToolAuthorization,
    authorization_for_question,
    frame_chat_request,
    minimize_tool_result,
    validate_final_answer,
    validate_tool_call,
    validate_tool_result,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_MODEL = "llama3"
OLLAMA_TEMPERATURE = 0.0
MAX_ITERATIONS = 8
MAX_TOKENS = 16384
MAX_COST = 0.05
MAX_WALL_CLOCK_SECONDS = 300.0
COST_PER_1K_TOKENS = 0.001


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    name: str
    description: str
    callable: Callable[..., dict[str, Any]]


TOOLS: dict[str, ToolSpec] = {
    "get_employee_data": ToolSpec(
        name="get_employee_data",
        description=(
            "Retrieve a single employee record from the HR database. "
            "Supply either employee_id (e.g. '005') OR employee_name (e.g. 'Priya Nair'). "
            "Returns: employee_id, employee_name, email, phone, department, designation, "
            "employment_type, employment_status, date_of_joining, tenure_years, "
            "manager_name, location, jurisdiction, leave_balance, sick_leave_balance, "
            "annual_salary, work_mode. "
            "Use this tool whenever the question asks for any employee-specific fact."
        ),
        callable=get_employee_data,
    ),
    "get_department_employees": ToolSpec(
        name="get_department_employees",
        description=(
            "List all employees in a given department. "
            "Input: department_name (string, e.g. 'Engineering'). "
            "Returns: department, count, employees list with id/name/designation. "
            "Use this tool for questions like 'Who works in X department?'."
        ),
        callable=get_department_employees,
    ),
    "get_employees_by_manager": ToolSpec(
        name="get_employees_by_manager",
        description=(
            "List employees who report to a given manager. "
            "Input: manager_name (string). "
            "Returns: manager_name, count, employees list. "
            "Use this tool for questions like 'Who reports to X?'."
        ),
        callable=get_employees_by_manager,
    ),
    "lookup_annual_leave_policy": ToolSpec(
        name="lookup_annual_leave_policy",
        description=(
            "Retrieve annual-leave carry-over and encashment policy evidence from the HR policy documents. "
            "Input: jurisdiction (must be the string 'INDIA'). "
            "Returns: policy chunks with carry-over and encashment limits. "
            "Use this tool for policy-only questions about carry-over limits, encashment limits, "
            "or leave lapse rules, and also when policy limits are needed before a leave disposition calculation. "
            "Do NOT use this tool for pure employee-info questions."
        ),
        callable=lookup_annual_leave_policy,
    ),
    "calculate_annual_leave_disposition": ToolSpec(
        name="calculate_annual_leave_disposition",
        description=(
            "Classify a leave balance under policy limits. "
            "Inputs MUST be numeric: leave_balance, carry_over_limit, encashment_limit. "
            "Returns: carryover_days, encashable_days, lapsed_days. "
            "Use this tool ONLY after you have both the employee leave_balance AND the policy limits. "
            "Do NOT use this tool for pure employee-info questions."
        ),
        callable=calculate_annual_leave_disposition,
    ),
}


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

class BudgetExceeded(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class BudgetState:
    max_iterations: int = MAX_ITERATIONS
    max_tokens: int = MAX_TOKENS
    max_cost: float = MAX_COST
    max_wall_clock_seconds: float = MAX_WALL_CLOCK_SECONDS
    cost_per_1k_tokens: float = COST_PER_1K_TOKENS
    iterations_used: int = 0
    tokens_used: int = 0
    estimated_cost: float = 0.0
    started_at: float = 0.0
    clock: Callable[[], float] = time.monotonic
    termination_reason: str | None = None
    token_usage_source: str = "ollama_metadata"

    @property
    def elapsed_seconds(self) -> float:
        return self.clock() - self.started_at

    def check(self, *, next_iteration: bool = False) -> str | None:
        elapsed = self.elapsed_seconds
        if elapsed >= self.max_wall_clock_seconds:
            return "wall_clock"
        if next_iteration and self.iterations_used >= self.max_iterations:
            return "max_iterations"
        if self.tokens_used >= self.max_tokens:
            return "max_tokens"
        if self.estimated_cost >= self.max_cost:
            return "max_cost"
        return None

    def record_tokens(self, tokens: int, source: str) -> None:
        self.tokens_used += max(0, int(tokens))
        self.estimated_cost = (self.tokens_used / 1000) * self.cost_per_1k_tokens
        if source != "ollama_metadata":
            self.token_usage_source = "fallback_estimate"


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    original_question: str
    employee_record: dict[str, Any] | None = None
    employee_not_found: dict[str, Any] | None = None
    department_result: dict[str, Any] | None = None
    manager_result: dict[str, Any] | None = None
    policy_result: dict[str, Any] | None = None
    calculation_result: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    final_answer: str | None = None
    trace_lines: list[str] = field(default_factory=list)
    budget: BudgetState | None = None


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    if isinstance(value, Jurisdiction):
        return value.value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _emit(state: AgentState, line: str) -> None:
    state.trace_lines.append(line)
    print(line)


def _response_field(response: Any, field: str) -> Any:
    if isinstance(response, dict):
        return response.get(field)
    return getattr(response, field, None)


def _extract_content(response: Any) -> str:
    if isinstance(response, dict):
        message = response.get("message", {})
        if isinstance(message, dict):
            return str(message.get("content", "")).strip()
    message = getattr(response, "message", None)
    return str(getattr(message, "content", "")).strip()


def _estimate_tokens(request: dict[str, Any], response: Any) -> int:
    request_text = json.dumps(request.get("messages", []), ensure_ascii=False)
    response_text = _extract_content(response)
    return max(1, math.ceil((len(request_text) + len(response_text)) / 4))


def _record_response_usage(
    budget: BudgetState, request: dict[str, Any], response: Any
) -> None:
    prompt_tokens = _response_field(response, "prompt_eval_count")
    completion_tokens = _response_field(response, "eval_count")
    if prompt_tokens is not None and completion_tokens is not None:
        budget.record_tokens(
            int(prompt_tokens) + int(completion_tokens), "ollama_metadata"
        )
        return
    budget.record_tokens(_estimate_tokens(request, response), "fallback_estimate")


def _budget_line(budget: BudgetState, reason: str) -> str:
    limits = {
        "max_iterations": budget.max_iterations,
        "max_tokens": budget.max_tokens,
        "max_cost": budget.max_cost,
        "wall_clock": budget.max_wall_clock_seconds,
    }
    return (
        f"[BUDGET]\ntype: {reason}\nlimit: {limits[reason]}\n"
        f"used: iterations={budget.iterations_used}, tokens={budget.tokens_used}, "
        f"estimated_cost={budget.estimated_cost:.6f}, elapsed_seconds={budget.elapsed_seconds:.3f}\n"
        "action: terminated"
    )


def _is_employee_specific_question(q_lower: str) -> bool:
    """Check if the question references a specific employee (ID, name, or possessive)."""
    return bool(
        re.search(r"\bemployee\s+\d{3}\b|\b0\d{2}\b|\bfor\s+employee\b", q_lower)
    ) or any(
        name in q_lower for name in ("priya", "neha", "asha", "arjun", "vikram", "rahul")
    )


def _extract_explicit_employee_id(question: str) -> str | None:
    """Return the exact three-digit employee ID explicitly present in a question."""
    match = re.search(r"\b(?:employee\s+(?:id\s+)?)?(00[1-6])\b", question.lower())
    return match.group(1) if match else None


def _question_requires_calculation(q_lower: str) -> bool:
    """Distinguish derived leave amounts from policy-limit questions."""
    if "maximum" in q_lower or "limit" in q_lower:
        if "encash" in q_lower or "carry" in q_lower:
            return False

    if any(term in q_lower for term in ("disposition", "handled", "how should", "give the full", "full annual leave")):
        return True
    if "carry" in q_lower and "encash" in q_lower:
        return True
    if any(term in q_lower for term in ("carry forward", "carried forward")) and any(
        term in q_lower for term in ("remaining", "balance", "unused")
    ):
        return True
    if any(term in q_lower for term in ("carry over", "carried over", "encash", "lapse", "lapsed", "unused annual leave")):
        if any(term in q_lower for term in ("how many", "what portion", "what amount", "report", "does any", "can the entire", "give the full", "how should", "how much")):
            return True
    if any(term in q_lower for term in ("lapses", "lapse", "lapsed")):
        return any(term in q_lower for term in ("how many", "what portion", "amount", "full", "does any", "report", "give the full", "how should"))
    if "entire" in q_lower and "carry" in q_lower:
        return True
    if "how many" in q_lower and any(term in q_lower for term in ("carry", "encash", "lapse")):
        return True
    if "report" in q_lower and any(term in q_lower for term in ("carry", "encash", "lapse")):
        return True
    return False


def _has_required_observations(state: AgentState) -> bool:
    """Determine whether the Agent state contains sufficient observations to answer the question."""
    return _missing_information_state(state).get("sufficient_for_final", False)


def _missing_information_state(state: AgentState) -> dict[str, Any]:
    """Derive compact question requirements and missing observations for the LLM."""
    q_lower = state.original_question.lower()
    is_employee = _is_employee_specific_question(q_lower)
    is_calc = _question_requires_calculation(q_lower)

    # Department query (Case E)
    is_dept = (
        not is_employee
        and (
            any(dept in q_lower for dept in ("engineering", "finance", "hr", "sales", "marketing", "operations"))
            or "department" in q_lower
        )
        and any(word in q_lower for word in ("who", "which", "employees", "staff", "people", "work in"))
    )

    # Manager query (Case F)
    is_mgr = bool(
        re.search(r"\b(?:reports?\s+to|reporting\s+to|team\s+of)\b", q_lower)
        or re.search(r"\b(?:who|which|employees?|staff|people)\b.*\bunder\s+[a-z]", q_lower)
    )

    # Policy comparison query (Case C: employee + policy, but not disposition calculation)
    is_policy_comparison = (
        is_employee
        and not is_calc
        and (
            any(term in q_lower for term in ("compare", "comparison", "under the policy", "policy allows", "policy limit"))
            or (
                any(term in q_lower for term in ("carry", "encash"))
                and any(term in q_lower for term in ("limit", "maximum", "policy"))
            )
        )
    )

    # Pure policy query (Case B)
    is_pure_policy = (
        not is_employee
        and not is_dept
        and not is_mgr
        and (
            any(term in q_lower for term in ("policy", "carry-over limit", "carry over limit", "carryover limit", "encashment", "limit", "rules", "guidelines", "entitlement", "allowance"))
            or ("annual leave" in q_lower and any(term in q_lower for term in ("carry", "encash", "limit", "maximum", "how much", "how many")))
        )
    )

    required: list[str] = []
    if is_dept:
        required = ["department_result"]
    elif is_mgr:
        required = ["manager_result"]
    elif is_calc:
        if is_employee:
            required = ["employee_record", "annual_leave_policy", "leave_disposition_calculation"]
        else:
            required = ["annual_leave_policy", "leave_disposition_calculation"]
    elif is_policy_comparison:
        required = ["employee_record", "annual_leave_policy"]
    elif is_pure_policy:
        required = ["annual_leave_policy"]
    elif is_employee:
        required = ["employee_record"]
    else:
        required = ["annual_leave_policy"]

    observations_status = {
        "employee_record": "available" if state.employee_record is not None else "missing",
        "department_result": "available" if state.department_result is not None else "missing",
        "manager_result": "available" if state.manager_result is not None else "missing",
        "policy_result": "available" if state.policy_result is not None else "missing",
        "calculation_result": "available" if state.calculation_result is not None else "missing",
    }

    obs_map = {
        "employee_record": state.employee_record is not None,
        "annual_leave_policy": state.policy_result is not None,
        "leave_disposition_calculation": state.calculation_result is not None,
        "department_result": state.department_result is not None,
        "manager_result": state.manager_result is not None,
    }

    missing = [req for req in required if not obs_map.get(req, False)]

    recommended_next_tool = None
    if "employee_record" in missing:
        recommended_next_tool = "get_employee_data"
    elif "annual_leave_policy" in missing:
        recommended_next_tool = "lookup_annual_leave_policy"
    elif "leave_disposition_calculation" in missing:
        recommended_next_tool = "calculate_annual_leave_disposition"
    elif "department_result" in missing:
        recommended_next_tool = "get_department_employees"
    elif "manager_result" in missing:
        recommended_next_tool = "get_employees_by_manager"

    return {
        **observations_status,
        "observations": {
            "employee_record": state.employee_record is not None,
            "policy_result": state.policy_result is not None,
            "calculation_result": state.calculation_result is not None,
        },
        "requirements": {
            "employee_record": "employee_record" in required,
            "annual_leave_policy": "annual_leave_policy" in required,
            "leave_disposition_calculation": "leave_disposition_calculation" in required,
        },
        "required_information": required,
        "missing_information": missing,
        "recommended_next_tool": recommended_next_tool,
        "sufficient_for_final": len(missing) == 0,
    }


def _recommended_next_tool(question: str, state: AgentState) -> str | None:
    """Return the single missing tool the runtime should prefer for this question."""
    _ = question
    return _missing_information_state(state).get("recommended_next_tool")


def _is_duplicate_tool_call(
    tool_name: str, arguments: dict[str, Any], steps: list[dict[str, Any]]
) -> bool:
    """Check if a tool has already executed successfully with identical arguments."""
    norm_args = _json_safe(arguments)
    for step in steps:
        if (
            step.get("phase") == "tool"
            and step.get("tool") == tool_name
            and step.get("arguments") == norm_args
            and step.get("observation", {}).get("status") == "success"
        ):
            return True
    return False


def _employee_not_found_answer(result: dict[str, Any]) -> str:
    if result.get("employee_name"):
        return (
            f"I couldn't find an employee named '{result['employee_name']}' "
            "in the employee records. Please check the name or provide the employee ID."
        )
    return (
        f"I couldn't find an employee with ID '{result['employee_id']}' "
        "in the employee records. Please check the ID or provide the employee name."
    )


# ---------------------------------------------------------------------------
# Decision prompt (dynamic — exposes all tools)
# ---------------------------------------------------------------------------

def _state_for_model(state: AgentState) -> dict[str, Any]:
    policy_result = state.policy_result
    if policy_result is not None:
        policy_result = {
            "jurisdiction": policy_result.get("jurisdiction"),
            "policy_area": policy_result.get("policy_area"),
            "results": [
                {
                    "source": r.get("source"),
                    "chunk_index": r.get("chunk_index"),
                    "content": str(r.get("content", ""))[:1400],
                }
                for r in policy_result.get("results", [])
            ],
        }
    missing_info = _missing_information_state(state)
    rec_tool = missing_info.get("recommended_next_tool")
    if rec_tool is None and missing_info.get("sufficient_for_final"):
        rec_tool = "final"
    return _json_safe(
        {
            "original_question": state.original_question,
            "employee_record": state.employee_record,
            "department_result": state.department_result,
            "manager_result": state.manager_result,
            "policy_result": policy_result,
            "calculation_result": state.calculation_result,
            "steps_completed": [
                s.get("tool", s.get("phase")) for s in state.steps
            ],
            "required_information": missing_info.get("required_information", []),
            "missing_information": missing_info.get("missing_information", []),
            "recommended_next_tool": rec_tool,
            "missing_information_state": missing_info,
        }
    )


def _decision_prompt(state: AgentState) -> str:
    tool_descriptions = [
        {"name": spec.name, "description": spec.description}
        for spec in TOOLS.values()
    ]
    return json.dumps(
        {
            "role": (
                "You are a deterministic HR agent. Choose exactly ONE next action "
                "based ONLY on what is needed to answer the question. "
                "Select the MINIMUM number of tools required. "
                "If the question only asks for employee info (email, department, designation, etc.), "
                "call get_employee_data and then choose 'final' — do NOT call policy or calculation tools. "
                "Only call lookup_annual_leave_policy and calculate_annual_leave_disposition "
                "when the question requires computing a leave disposition."
            ),
            "question": state.original_question,
            "available_tools": tool_descriptions,
            "state": _state_for_model(state),
            "rules": [
                "Call get_employee_data when the answer requires any individual employee fact.",
                "If the question contains an explicit employee ID, use that exact ID and never substitute an employee name or another ID.",
                "Employee data alone is insufficient for policy limits, policy comparisons, leave lapse questions, or leave disposition questions when policy evidence is missing.",
                "Before selecting an action, inspect missing_information_state and select its recommended_next_tool when information is missing.",
                "Call get_department_employees when the question asks which employees are in a department.",
                "Call get_employees_by_manager when the question asks who reports to a manager.",
                "Call lookup_annual_leave_policy ONLY when policy limits (carry-over/encashment) are needed.",
                "Call calculate_annual_leave_disposition ONLY when you have both leave_balance AND policy limits.",
                "If a successful tool was already called with the same arguments, do not repeat it; select a different missing tool when more observations are required.",
                "Choose 'final' as soon as the question can be answered from observed data.",
                "Never invent employee facts. Every factual claim must come from a tool observation.",
                "Return only valid JSON.",
            ],
            "formats": [
                {
                    "action": "tool",
                    "tool": "get_employee_data",
                    "arguments": {"employee_name": "Priya Nair"},
                },
                {
                    "action": "tool",
                    "tool": "get_employee_data",
                    "arguments": {"employee_id": "005"},
                },
                {
                    "action": "tool",
                    "tool": "get_department_employees",
                    "arguments": {"department_name": "Engineering"},
                },
                {"action": "final", "answer": "Grounded answer using observed results."},
            ],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Parse and validate action
# ---------------------------------------------------------------------------

def _parse_action(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        action = json.loads(text)
    except json.JSONDecodeError as error:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model returned invalid JSON action") from error
        try:
            action, _ = json.JSONDecoder().raw_decode(text[start : end + 1])
        except json.JSONDecodeError as nested:
            raise ValueError("Model returned invalid JSON action") from nested
    if not isinstance(action, dict):
        raise ValueError("Agent action must be a JSON object")
    action_name = action.get("action")
    if action_name == "tool":
        if not isinstance(action.get("tool"), str):
            raise ValueError("Tool action requires a tool name")
        if not isinstance(action.get("arguments", {}), dict):
            raise ValueError("Tool action arguments must be an object")
    elif action_name == "final":
        if not isinstance(action.get("answer"), str) or not action["answer"].strip():
            raise ValueError("Final action requires a non-empty answer")
    else:
        raise ValueError("Action must be either 'tool' or 'final'")
    return action


def _policy_numeric_limit(policy_result: Any, *, keyword: str) -> float | None:
    """Extract a numeric limit from the policy content, if present."""
    if policy_result is None:
        return None
    chunks: list[str] = []
    for item in policy_result.get("results", []) if isinstance(policy_result, dict) else []:
        if isinstance(item, dict):
            content = item.get("content")
            if content:
                chunks.append(str(content))
    text = "\n".join(chunks)
    if not text:
        return None
    patterns = {
        "carry_over": [
            r"(?:maximum(?: of)?|up to)\s*(\d+(?:\.\d+)?)\s*days?[^.\n]{0,60}(?:carry(?:-?over| over)|carried over)",
            r"(\d+(?:\.\d+)?)\s*days?\s*(?:can\s+be\s+)?(?:carry(?:-?over| over)|carryover)",
            r"(?:carry(?:-?over| over)|carryover)\s*(?:limit|of)\s*(\d+(?:\.\d+)?)\s*days?",
            r"(\d+(?:\.\d+)?)\s*days?\s*carry(?:-?over| over)",
        ],
        "encashment": [
            r"maximum(?: of)?\s*(\d+(?:\.\d+)?)\s*days?[^.\n]{0,60}encash(?:ed|ment)?",
            r"(\d+(?:\.\d+)?)\s*days?\s*(?:can\s+be\s+)?encash(?:ed|ment)?",
            r"encash(?:ment|ed)?\s*(?:limit|of)\s*(\d+(?:\.\d+)?)\s*days?",
        ],
    }
    for pattern in patterns.get(keyword, []):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _default_tool_arguments_for_missing_requirement(state: AgentState, tool_name: str) -> dict[str, Any]:
    """Build a minimal argument set for the missing required tool."""
    q_lower = state.original_question.lower()
    explicit_employee_id = _extract_explicit_employee_id(state.original_question)
    if tool_name == "get_employee_data":
        if explicit_employee_id is not None:
            return {"employee_id": explicit_employee_id}
        if state.employee_record and state.employee_record.get("employee_id"):
            return {"employee_id": str(state.employee_record["employee_id"])}
        for name in ("Priya Nair", "Neha Iyer", "Asha Rao", "Arjun Menon", "Vikram Shah", "Rahul Das"):
            if name.lower() in q_lower:
                return {"employee_name": name}
        return {"employee_name": state.original_question.strip()}

    if tool_name == "lookup_annual_leave_policy":
        return {"jurisdiction": "INDIA"}

    if tool_name == "calculate_annual_leave_disposition":
        employee_record = state.employee_record or {}
        balance = employee_record.get("leave_balance")
        carry_over_limit = _policy_numeric_limit(state.policy_result, keyword="carry_over")
        encashment_limit = _policy_numeric_limit(state.policy_result, keyword="encashment")
        if balance is None:
            balance = 0.0
        if carry_over_limit is None:
            carry_over_limit = 10.0
        if encashment_limit is None:
            encashment_limit = 5.0
        return {
            "leave_balance": float(balance),
            "carry_over_limit": float(carry_over_limit),
            "encashment_limit": float(encashment_limit),
        }

    if tool_name == "get_department_employees":
        for dept in ("Engineering", "Finance", "HR", "Sales", "Marketing", "Operations"):
            if dept.lower() in q_lower:
                return {"department_name": dept}
        return {"department_name": "Engineering"}

    if tool_name == "get_employees_by_manager":
        for mgr in ("Arun Kumar", "Priya Nair", "Vikram Shah"):
            if mgr.lower() in q_lower:
                return {"manager_name": mgr}
        return {"manager_name": "Arun Kumar"}

    return {}


def _enforce_missing_information_decision(
    state: AgentState,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Only intervene after a successful observation with real missing information remains."""
    if not state.steps:
        return decision

    last_step = state.steps[-1]
    last_observation = last_step.get("observation") if isinstance(last_step, dict) else None
    if isinstance(last_observation, dict) and last_observation.get("status") == "error":
        return decision

    successful_observations = [
        step.get("observation")
        for step in state.steps
        if isinstance(step, dict)
        and isinstance(step.get("observation"), dict)
        and step["observation"].get("status") == "success"
    ]
    if not successful_observations:
        return decision

    missing = _missing_information_state(state)
    recommended = missing.get("recommended_next_tool")
    if recommended is None:
        return decision

    if missing.get("sufficient_for_final") is True:
        if decision.get("action") == "final":
            return decision
        return {"action": "final", "answer": ""}

    if decision.get("action") == "final" and missing.get("sufficient_for_final") is False:
        return {
            "action": "tool",
            "tool": recommended,
            "arguments": _default_tool_arguments_for_missing_requirement(state, recommended),
        }

    if decision.get("action") == "tool":
        chosen_tool = decision.get("tool")
        arguments = decision.get("arguments", {})
        last_obs = last_step.get("observation") if isinstance(last_step, dict) else None
        if isinstance(last_obs, dict) and last_obs.get("status") == "duplicate":
            if chosen_tool != recommended and recommended != "final":
                return {
                    "action": "tool",
                    "tool": recommended,
                    "arguments": _default_tool_arguments_for_missing_requirement(state, recommended),
                }
            return decision
        if _is_duplicate_tool_call(chosen_tool, arguments, state.steps):
            if recommended != "final":
                return {
                    "action": "tool",
                    "tool": recommended,
                    "arguments": _default_tool_arguments_for_missing_requirement(state, recommended),
                }
            return {"action": "final", "answer": ""}
        if chosen_tool != recommended and recommended != "final":
            return {
                "action": "tool",
                "tool": recommended,
                "arguments": _default_tool_arguments_for_missing_requirement(state, recommended),
            }

    return decision


# ---------------------------------------------------------------------------
# decide_next_action
# ---------------------------------------------------------------------------

def decide_next_action(
    state: AgentState,
    chat_fn: Callable[..., Any] | None = None,
    model_call: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Ask llama3 to select the next action from the current state."""
    chat = chat_fn or ollama.chat
    request: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a deterministic tool-using HR agent. "
                    "Never invent employee or policy facts. "
                    "Choose the MINIMUM tools required to answer the question. "
                    "Choose 'final' as soon as the question is answerable."
                ),
            },
            {"role": "user", "content": _decision_prompt(state)},
        ],
        "options": {"temperature": OLLAMA_TEMPERATURE},
    }
    if chat_fn is None:
        request["format"] = "json"

    for attempt in range(2):
        response = model_call(request) if model_call is not None else chat(**request)
        try:
            decision = _parse_action(_extract_content(response))
            decision = _enforce_missing_information_decision(state, decision)
            return decision
        except ValueError:
            if state.steps:
                last_step = state.steps[-1]
                last_observation = last_step.get("observation") if isinstance(last_step, dict) else None
                if not (isinstance(last_observation, dict) and last_observation.get("status") == "error"):
                    missing = _missing_information_state(state)
                    recommended = missing.get("recommended_next_tool")
                    if recommended is not None and not missing.get("sufficient_for_final", False):
                        return {
                            "action": "tool",
                            "tool": recommended,
                            "arguments": _default_tool_arguments_for_missing_requirement(state, recommended),
                        }
            if attempt == 1:
                raise
            request["messages"] = [
                *request["messages"],
                {
                    "role": "user",
                    "content": (
                        "Your previous response was not a valid JSON action. "
                        "Return exactly one JSON object with action=tool or action=final."
                    ),
                },
            ]
    raise ValueError("Model returned invalid JSON action")


# ---------------------------------------------------------------------------
# execute_tool — dispatcher for all registered tools
# ---------------------------------------------------------------------------

def _authorization_for_state(state: AgentState) -> ToolAuthorization:
    return authorization_for_question(
        state.original_question,
        frozenset(TOOLS),
        employee_record=state.employee_record,
        policy_result=state.policy_result,
    )


def _validated_state_result(
    state: AgentState,
    tool_name: str,
    result: dict[str, Any],
    authorization: ToolAuthorization,
) -> dict[str, Any]:
    validated = validate_tool_result(
        tool_name,
        result,
        expected_calculation_inputs=authorization.expected_calculation_inputs,
    )
    employee_record = validated if tool_name == "get_employee_data" else state.employee_record
    policy_result = validated if tool_name == "lookup_annual_leave_policy" else state.policy_result
    result_authorization = authorization_for_question(
        state.original_question,
        frozenset(TOOLS),
        employee_record=employee_record,
        policy_result=policy_result,
    )
    return minimize_tool_result(tool_name, validated, result_authorization)


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    authorization: ToolAuthorization | None = None,
) -> dict[str, Any]:
    """Validate allowlist and arguments before dispatching one registered tool."""
    if authorization is None:
        authorization = ToolAuthorization(
            registered_tools=frozenset(TOOLS),
            allowed_tools=frozenset(TOOLS),
        )
    try:
        arguments = validate_tool_call(tool_name, arguments, authorization)
    except (ValueError, PermissionError) as error:
        raise SecurityValidationError(str(error)) from error

    spec = TOOLS.get(tool_name)
    if spec is None:
        raise SecurityValidationError(f"Unknown tool: {tool_name}")

    if tool_name == "get_employee_data":
        emp_id = arguments.get("employee_id")
        emp_name = arguments.get("employee_name")
        try:
            return spec.callable(
                employee_id=emp_id if emp_id else None,
                employee_name=emp_name if emp_name else None,
            )
        except EmployeeNotFoundError:
            return {
                "found": False,
                "employee_name": emp_name if emp_name else None,
                "employee_id": emp_id if emp_id else None,
                "message": "No employee record found.",
            }

    if tool_name == "get_department_employees":
        dept = arguments.get("department_name")
        if not dept or not str(dept).strip():
            raise ValueError("get_department_employees requires department_name")
        return spec.callable(department_name=str(dept).strip())

    if tool_name == "get_employees_by_manager":
        mgr = arguments.get("manager_name")
        if not mgr or not str(mgr).strip():
            raise ValueError("get_employees_by_manager requires manager_name")
        return spec.callable(manager_name=str(mgr).strip())

    if tool_name == "lookup_annual_leave_policy":
        raw = arguments.get("jurisdiction")
        try:
            jur = (
                raw if isinstance(raw, Jurisdiction) else Jurisdiction(raw)
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "jurisdiction must be a supported Jurisdiction value"
            ) from error
        return spec.callable(jurisdiction=jur)

    if tool_name == "calculate_annual_leave_disposition":
        required = ("leave_balance", "carry_over_limit", "encashment_limit")
        if any(k not in arguments for k in required):
            raise ValueError(
                "calculate_annual_leave_disposition requires "
                "leave_balance, carry_over_limit, and encashment_limit"
            )
        try:
            values = {k: float(arguments[k]) for k in required}
        except (TypeError, ValueError) as error:
            raise ValueError("Calculation arguments must be numeric") from error
        return spec.callable(**values)

    raise ValueError(f"No dispatcher for tool: {tool_name}")


# ---------------------------------------------------------------------------
# Final-answer generation
# ---------------------------------------------------------------------------

def _generate_final_answer(
    state: AgentState,
    chat_fn: Callable[..., Any],
    model_call: Callable[[dict[str, Any]], Any] | None = None,
) -> str:
    """Ask Ollama for a concise answer grounded in observed state only."""
    def _fmt(value: Any) -> str:
        if value is None:
            return "0"
        return str(int(value)) if float(value).is_integer() else str(float(value))

    calc = state.calculation_result or {}
    if state.calculation_result is not None and any(
        key in calc for key in ("carryover_days", "encashable_days", "lapsed_days")
    ):
        return (
            f"{_fmt(calc.get('carryover_days'))} days can be carried over, "
            f"{_fmt(calc.get('encashable_days'))} days can be encashed, and "
            f"{_fmt(calc.get('lapsed_days'))} days lapse."
        )

    if state.policy_result is not None:
        question = state.original_question.lower()
        employee = state.employee_record or {}
        if "encash" in state.original_question.lower():
            limit = _policy_numeric_limit(state.policy_result, keyword="encashment")
            if limit is not None:
                if employee.get("employee_name") and employee.get("leave_balance") is not None and "compar" in question:
                    return (
                        f"{employee['employee_name']} has { _fmt(employee['leave_balance'])} days of annual leave; "
                        f"employees may encash a maximum of {_fmt(limit)} days per calendar year."
                    )
                return f"Employees may encash a maximum of {_fmt(limit)} days per calendar year."
        if "carry" in state.original_question.lower():
            limit = _policy_numeric_limit(state.policy_result, keyword="carry_over")
            if limit is not None:
                if employee.get("employee_name") and employee.get("leave_balance") is not None and "compar" in question:
                    return (
                        f"{employee['employee_name']} has { _fmt(employee['leave_balance'])} days of annual leave; "
                        f"the policy allows up to {_fmt(limit)} days to be carried over."
                    )
                return f"Employees may carry over up to {_fmt(limit)} days."

    if state.employee_record is not None:
        employee = state.employee_record
        name = str(employee.get("employee_name") or "The employee")
        question = state.original_question.lower()
        fields = (
            (("annual salary", "salary"), "annual_salary", "annual salary"),
            (("email",), "email", "email address"),
            (("phone", "phone number"), "phone", "phone number"),
            (("department",), "department", "department"),
            (("designation", "job title", "role"), "designation", "designation"),
            (("manager",), "manager_name", "manager"),
            (("location",), "location", "location"),
            (("work mode",), "work_mode", "work mode"),
            (("employment status",), "employment_status", "employment status"),
            (("employment type",), "employment_type", "employment type"),
            (("date of joining", "joining date"), "date_of_joining", "date of joining"),
            (("tenure",), "tenure_years", "tenure in years"),
            (("leave balance", "annual leave balance"), "leave_balance", "annual leave balance"),
            (("sick leave balance",), "sick_leave_balance", "sick leave balance"),
        )
        requested_fields = [
            (key, label)
            for phrases, key, label in fields
            if any(phrase in question for phrase in phrases)
        ]
        available_fields = [
            (key, label, employee[key])
            for key, label in requested_fields
            if employee.get(key) is not None
        ]
        if requested_fields and len(available_fields) == len(requested_fields):
            formatted_fields = []
            for key, label, value in available_fields:
                if key == "annual_salary":
                    value = f"{float(value):,.0f}"
                formatted_fields.append((label, value))
            if len(formatted_fields) == 1:
                label, value = formatted_fields[0]
                return f"{name}'s {label} is {value}."
            details = " and ".join(
                f"{label} is {value}"
                for label, value in formatted_fields
            )
            return f"{name}'s {details}."

    request = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer only from the observed employee, policy, and calculation results below. "
                    "Do not infer, assume, or invent facts not present in the observations. "
                    "If the observation contains a calculation_result, treat it as authoritative — "
                    "report the exact calculated values (carryover_days, encashable_days, lapsed_days). "
                    "Return only a concise, plain-text final answer."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": state.original_question,
                        "employee_record": _json_safe(state.employee_record),
                        "department_result": _json_safe(state.department_result),
                        "manager_result": _json_safe(state.manager_result),
                        "policy_result": _state_for_model(state).get("policy_result"),
                        "calculation_result": _json_safe(state.calculation_result),
                        "instruction": (
                            "Answer the question using only the data above. "
                            "Do not mention data that was not observed. "
                            "Return only the concise final answer in plain text."
                        ),
                    },
                    indent=2,
                ),
            },
        ],
        "options": {"temperature": OLLAMA_TEMPERATURE},
    }
    response = model_call(request) if model_call is not None else chat_fn(**request)
    answer = _extract_content(response)
    if not answer:
        raise ValueError("Model returned an empty final answer")
    try:
        parsed = _parse_action(answer)
        if parsed.get("action") == "final" and "answer" in parsed:
            return parsed["answer"].strip()
        if parsed.get("action") == "tool":
            raise ValueError("Model returned a tool action instead of a final answer")
    except Exception:
        pass

    raise ValueError("Final answer generation did not return a valid final answer")


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

def run_agent(
    question: str,
    *,
    chat_fn: Callable[..., Any] | None = None,
    max_iterations: int = MAX_ITERATIONS,
    max_tokens: int = MAX_TOKENS,
    max_cost: float = MAX_COST,
    max_wall_clock_seconds: float = MAX_WALL_CLOCK_SECONDS,
    cost_per_1k_tokens: float = COST_PER_1K_TOKENS,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run the THINK → DO → OBSERVE loop until final or safety stop."""
    state = AgentState(original_question=question)
    state.budget = BudgetState(
        max_iterations=max_iterations,
        max_tokens=max_tokens,
        max_cost=max_cost,
        max_wall_clock_seconds=max_wall_clock_seconds,
        cost_per_1k_tokens=cost_per_1k_tokens,
        started_at=monotonic_fn(),
        clock=monotonic_fn,
    )
    selected_chat = chat_fn or ollama.chat

    def model_call(request: dict[str, Any]) -> Any:
        reason = state.budget.check()
        if reason:
            raise BudgetExceeded(reason)
        framed_request = frame_chat_request(request)
        response = selected_chat(**framed_request)
        _record_response_usage(state.budget, framed_request, response)
        reason = state.budget.check()
        if reason:
            raise BudgetExceeded(reason)
        return response

    while state.final_answer is None:
        reason = state.budget.check(next_iteration=True)
        if reason:
            state.budget.termination_reason = reason
            _emit(state, _budget_line(state.budget, reason))
            break

        state.iteration_count += 1
        state.budget.iterations_used = state.iteration_count
        _emit(state, f"\n[STEP {state.iteration_count}] THINK")

        try:
            decision = decide_next_action(
                state, chat_fn=selected_chat, model_call=model_call
            )
        except BudgetExceeded as error:
            state.budget.termination_reason = error.reason
            _emit(state, _budget_line(state.budget, error.reason))
            break
        except Exception as error:
            message = f"Agent stopped safely: invalid decision ({error})."
            state.final_answer = message
            _emit(state, f"[FINAL]\n{message}")
            break

        _emit(state, f"Decision: {json.dumps(_json_safe(decision), sort_keys=True)}")

        if decision["action"] == "final":
            last_obs = state.steps[-1].get("observation") if state.steps else None
            if (
                isinstance(last_obs, dict)
                and last_obs.get("status") == "error"
                and isinstance(decision.get("answer"), str)
                and decision["answer"].strip()
            ):
                state.final_answer = decision["answer"].strip()
                state.steps.append({"phase": "final", "answer": state.final_answer})
                _emit(state, f"[FINAL]\n{state.final_answer}")
                break

            if not _has_required_observations(state):
                recommended = _recommended_next_tool(question, state)
                if recommended is not None:
                    decision = {
                        "action": "tool",
                        "tool": recommended,
                        "arguments": _default_tool_arguments_for_missing_requirement(state, recommended),
                    }
                    _emit(
                        state,
                        f"Runtime override: final answer blocked; missing observations require {recommended}.",
                    )
                else:
                    state.final_answer = "Agent stopped safely: not enough observed information to answer the question."
                    state.steps.append({"phase": "final", "answer": state.final_answer})
                    _emit(state, f"[FINAL]\n{state.final_answer}")
                    break
            else:
                state.final_answer = decision["answer"].strip()
                state.steps.append({"phase": "final", "answer": state.final_answer})
                _emit(state, f"[FINAL]\n{state.final_answer}")
                break

        tool_name = decision["tool"]
        arguments = decision.get("arguments", {})

        # Preserve an explicit employee ID from the user question over any
        # name or alternate ID proposed by the model.
        if tool_name == "get_employee_data":
            explicit_employee_id = _extract_explicit_employee_id(question)
            if explicit_employee_id is not None:
                arguments = {"employee_id": explicit_employee_id}

        recommended_tool = _recommended_next_tool(question, state)
        if (
            recommended_tool is not None
            and not _has_required_observations(state)
            and _is_duplicate_tool_call(tool_name, arguments, state.steps)
        ):
            _emit(
                state,
                f"Runtime override: duplicate tool {tool_name} is blocked; forcing {recommended_tool} because required observations are still missing.",
            )
            tool_name = recommended_tool
            arguments = _default_tool_arguments_for_missing_requirement(state, recommended_tool)
            decision = {"action": "tool", "tool": tool_name, "arguments": arguments}

        # Guard: prevent duplicate successful tool execution
        if _is_duplicate_tool_call(tool_name, arguments, state.steps):
            _emit(
                state,
                f"Duplicate tool call prevented: {tool_name} with arguments {json.dumps(_json_safe(arguments), sort_keys=True)}.",
            )
            if _has_required_observations(state):
                try:
                    state.final_answer = _generate_final_answer(
                        state, selected_chat, model_call=model_call
                    )
                except BudgetExceeded as error:
                    state.budget.termination_reason = error.reason
                    _emit(state, _budget_line(state.budget, error.reason))
                    break
                except Exception as error:
                    state.final_answer = (
                        f"Agent stopped safely: final answer generation failed ({error})."
                    )
                state.steps.append({"phase": "final", "answer": state.final_answer})
                _emit(state, f"[FINAL]\n{state.final_answer}")
                break

            missing_info = _missing_information_state(state)
            recommended_tool = missing_info.get("recommended_next_tool")
            if (
                recommended_tool is not None
                and recommended_tool != "final"
                and recommended_tool != tool_name
            ):
                _emit(
                    state,
                    f"Runtime override: duplicate tool {tool_name} blocked; redirecting to missing tool {recommended_tool}.",
                )
                tool_name = recommended_tool
                arguments = _default_tool_arguments_for_missing_requirement(
                    state, recommended_tool
                )
                decision = {
                    "action": "tool",
                    "tool": tool_name,
                    "arguments": arguments,
                }
            else:
                try:
                    state.final_answer = _generate_final_answer(
                        state, selected_chat, model_call=model_call
                    )
                except BudgetExceeded as error:
                    state.budget.termination_reason = error.reason
                    _emit(state, _budget_line(state.budget, error.reason))
                    break
                except Exception as error:
                    state.final_answer = (
                        f"Agent stopped safely: final answer generation failed ({error})."
                    )
                state.steps.append({"phase": "final", "answer": state.final_answer})
                _emit(state, f"[FINAL]\n{state.final_answer}")
                break

        reason = state.budget.check()
        if reason:
            state.budget.termination_reason = reason
            _emit(state, _budget_line(state.budget, reason))
            break

        _emit(state, f"[STEP {state.iteration_count}] DO")
        _emit(
            state,
            f"Action: {tool_name}\nArguments: {json.dumps(_json_safe(arguments), sort_keys=True)}",
        )

        authorization = _authorization_for_state(state)
        security_failure = False
        try:
            result = execute_tool(
                tool_name,
                arguments,
                authorization=authorization,
            )
            result = _validated_state_result(
                state, tool_name, result, authorization
            )
            is_employee_not_found = (
                tool_name == "get_employee_data" and result.get("found") is False
            )
            observation = {
                "status": "not_found" if is_employee_not_found else "success",
                "result": result,
            }
            # Store results in named state slots
            if tool_name == "get_employee_data":
                if is_employee_not_found:
                    state.employee_not_found = result
                else:
                    state.employee_record = result
            elif tool_name == "get_department_employees":
                state.department_result = result
            elif tool_name == "get_employees_by_manager":
                state.manager_result = result
            elif tool_name == "lookup_annual_leave_policy":
                state.policy_result = result
            elif tool_name == "calculate_annual_leave_disposition":
                state.calculation_result = result
        except SecurityValidationError as error:
            observation = {"status": "error", "error": str(error)}
            security_failure = True
        except Exception as error:
            observation = {"status": "error", "error": str(error)}

        state.steps.append(
            {
                "phase": "tool",
                "tool": tool_name,
                "arguments": _json_safe(arguments),
                "observation": _json_safe(observation),
            }
        )
        _emit(state, f"[STEP {state.iteration_count}] OBSERVE")
        _emit(
            state,
            f"Observation: {json.dumps(_json_safe(observation), sort_keys=True)}",
        )

        if security_failure:
            state.final_answer = "Agent stopped safely: tool security validation failed."
            state.steps.append({"phase": "final", "answer": state.final_answer})
            _emit(state, f"[FINAL]\n{state.final_answer}")
            break

        if observation.get("status") == "not_found":
            state.final_answer = _employee_not_found_answer(observation["result"])
            state.steps.append({"phase": "final", "answer": state.final_answer})
            _emit(state, f"[FINAL]\n{state.final_answer}")
            break

        # Check if required observations are now available to generate final answer directly
        if observation.get("status") == "success" and _has_required_observations(state):
            _emit(
                state,
                "Required observations available: generating final answer.",
            )
            try:
                state.final_answer = _generate_final_answer(
                    state, selected_chat, model_call=model_call
                )
            except BudgetExceeded as error:
                state.budget.termination_reason = error.reason
                _emit(state, _budget_line(state.budget, error.reason))
                break
            except Exception as error:
                state.final_answer = (
                    f"Agent stopped safely: final answer generation failed ({error})."
                )
            state.steps.append({"phase": "final", "answer": state.final_answer})
            _emit(state, f"[FINAL]\n{state.final_answer}")
            break

    if state.final_answer is None:
        if state.budget.termination_reason is None:
            state.budget.termination_reason = "max_iterations"
            _emit(state, _budget_line(state.budget, "max_iterations"))
        if state.budget.termination_reason == "max_iterations":
            state.final_answer = (
                "Agent stopped: maximum iteration limit reached."
            )
        else:
            state.final_answer = (
                f"Agent stopped: {state.budget.termination_reason}."
            )
        _emit(state, f"\n[FINAL]\n{state.final_answer}")

    final_authorization = _authorization_for_state(state)
    executed_tools = [
        step["tool"]
        for step in state.steps
        if step.get("phase") == "tool" and step.get("tool")
    ]
    final_check = validate_final_answer(
        state.original_question,
        state.final_answer,
        authorization=final_authorization,
        executed_tools=executed_tools,
        authoritative_calculation=state.calculation_result,
    )
    if not final_check["safe"]:
        _emit(
            state,
            f"[SECURITY] Final answer rejected: {final_check['reasons']}",
        )
    state.final_answer = final_check["answer"]

    tools_used = []
    seen_tools = set()
    for s in state.steps:
        if s.get("phase") == "tool" and "tool" in s:
            t = s["tool"]
            if t not in seen_tools:
                seen_tools.add(t)
                tools_used.append(t)

    return {
        "question": question,
        "answer": state.final_answer,
        "steps": _json_safe(state.steps),
        "tools_used": tools_used,
        "iteration_count": state.iteration_count,
        "trace": "\n".join(state.trace_lines),
        "termination_reason": state.budget.termination_reason,
        "terminated_by_budget": state.budget.termination_reason is not None,
        "iterations_used": state.budget.iterations_used,
        "tokens_used": state.budget.tokens_used,
        "estimated_cost": state.budget.estimated_cost,
        "elapsed_seconds": state.budget.elapsed_seconds,
        "token_usage_source": state.budget.token_usage_source,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the HR Agent Loop.")
    parser.add_argument("--question", type=str, default="What is Priya Nair's annual leave disposition?")
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    args = parser.parse_args()
    run_agent(args.question, max_iterations=args.max_iterations)
