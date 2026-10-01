from __future__ import annotations

import json

import pytest

import app.agent as agent
from app.router import route_question
from app.security import _database_value_exists
from app.tools import (
    EmployeeNotFoundError,
    Jurisdiction,
    get_employee_data as database_get_employee_data,
)


class ChatSequence:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.prompts = []
        self.calls = 0

    def __call__(self, *, model, messages, options, **kwargs):
        self.calls += 1
        self.prompts.append(json.loads(messages[-1]["content"]))
        return {"message": {"content": json.dumps(next(self.payloads))}}


class UsageChat(ChatSequence):
    def __init__(self, payloads, prompt_tokens=4, completion_tokens=2):
        super().__init__(payloads)
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def __call__(self, *, model, messages, options, **kwargs):
        response = super().__call__(model=model, messages=messages, options=options, **kwargs)
        response.update(
            prompt_eval_count=self.prompt_tokens,
            eval_count=self.completion_tokens,
        )
        return response


def _install_policy_stub(monkeypatch):
    spec = agent.TOOLS["lookup_annual_leave_policy"]
    monkeypatch.setattr(
        spec,
        "callable",
        lambda jurisdiction: {
            "jurisdiction": jurisdiction,
            "policy_area": "annual_leave_balance",
            "results": [{
                "source": "leave_policy.pdf",
                "chunk_index": 2,
                "content": (
                    "Unused annual leave of up to 10 days may be carried over. "
                    "A maximum of 5 days may be encashed per calendar year."
                ),
            }],
        },
    )


# ---------------------------------------------------------------------------
# Dynamic tool selection tests
# ---------------------------------------------------------------------------

def test_employee_lookup_by_name_is_selected_and_traced(monkeypatch):
    """Agent selects get_employee_data with employee_name argument."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Priya Nair"}},
        {"action": "final", "answer": "Priya Nair's email is priya.nair@acmecorp.in."},
    ])

    result = agent.run_agent("What is Priya Nair's email?", chat_fn=chat)

    assert result["steps"][0]["tool"] == "get_employee_data"
    assert "Action: get_employee_data" in result["trace"]


def test_employee_lookup_by_id_works(monkeypatch):
    """Agent selects get_employee_data with employee_id argument."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
        {"action": "final", "answer": "Neha Iyer is in Engineering department."},
    ])

    result = agent.run_agent("What department does employee 003 belong to?", chat_fn=chat)

    assert result["steps"][0]["tool"] == "get_employee_data"
    assert result["answer"] == "Neha Iyer's department is Engineering."


def test_department_lookup_uses_correct_tool(monkeypatch):
    """Agent uses get_department_employees for department queries."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_department_employees", "arguments": {"department_name": "Engineering"}},
        {"action": "final", "answer": "Neha Iyer and Arjun Menon work in Engineering."},
    ])

    result = agent.run_agent("Which employees work in Engineering?", chat_fn=chat)

    assert result["steps"][0]["tool"] == "get_department_employees"
    assert result["steps"][0]["observation"]["status"] == "success"


def test_simple_employee_question_does_not_call_policy_or_calc():
    """For a pure employee-info question, only get_employee_data should be called."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Priya Nair"}},
        {"action": "final", "answer": "Priya Nair's email is priya.nair@acmecorp.in."},
    ])

    result = agent.run_agent("What is Priya Nair's email?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employee_data"]
    assert "lookup_annual_leave_policy" not in str(result["trace"])
    assert "calculate_annual_leave_disposition" not in str(result["trace"])


# ---------------------------------------------------------------------------
# Full disposition flow (employee → policy → calculation)
# ---------------------------------------------------------------------------

def test_agent_reaches_final_answer_after_full_disposition(monkeypatch):
    _install_policy_stub(monkeypatch)
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {"action": "tool", "tool": "calculate_annual_leave_disposition",
         "arguments": {"leave_balance": 10, "carry_over_limit": 10, "encashment_limit": 5}},
        {"action": "final", "answer": "The balance supports 10 carry-over days and 5 encashable days."},
    ])

    result = agent.run_agent("How should 003's annual leave balance be handled?", chat_fn=chat)

    assert result["answer"]
    assert result["steps"][-1] == {
        "phase": "final",
        "answer": "10 days can be carried over, 5 days can be encashed, and 0 days lapse.",
    }
    assert "[FINAL]" in result["trace"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_unknown_employee_id_is_a_terminal_not_found_observation():
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "999"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "999"}},
    ])

    result = agent.run_agent("Find employee 999.", chat_fn=chat)

    observation = result["steps"][0]["observation"]
    assert observation["status"] == "not_found"
    assert observation["result"]["found"] is False
    assert "999" in result["answer"]
    assert "couldn't find" in result["answer"]
    assert len([step for step in result["steps"] if step.get("phase") == "tool"]) == 1
    assert result["iteration_count"] == 1
    assert result["termination_reason"] is None


def test_unknown_employee_name_is_a_terminal_not_found_without_rag_fallback():
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Ravi Kumar"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Ravi Kumar"}},
    ])

    assert route_question("What is Ravi Kumar's annual salary?") == "agent"
    result = agent.run_agent("What is Ravi Kumar's annual salary?", chat_fn=chat)

    assert result["steps"][0]["observation"]["status"] == "not_found"
    assert "Ravi Kumar" in result["answer"]
    assert "couldn't find" in result["answer"]
    assert "salary is" not in result["answer"]
    assert len([step for step in result["steps"] if step.get("phase") == "tool"]) == 1
    assert result["termination_reason"] is None


def test_arjun_not_found_response_when_lookup_reports_missing(monkeypatch):
    original_exists = _database_value_exists
    monkeypatch.setattr(
        agent.TOOLS["get_employee_data"],
        "callable",
        lambda **kwargs: (_ for _ in ()).throw(
            EmployeeNotFoundError("No employee found with name: Arjun Menon")
        ),
    )
    monkeypatch.setattr(
        "app.security._database_value_exists",
        lambda column, value: (
            False if column == "employee_name" and value.casefold() == "arjun menon"
            else original_exists(column, value)
        ),
    )
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Arjun Menon"}},
    ])

    result = agent.run_agent("What department does Arjun Menon work in?", chat_fn=chat)

    assert result["steps"][0]["observation"]["status"] == "not_found"
    assert "Arjun Menon" in result["answer"]
    assert "department is" not in result["answer"]
    assert result["termination_reason"] is None


def test_existing_arjun_department_is_returned_from_database():
    result = agent.run_agent(
        "What department does Arjun Menon work in?",
        chat_fn=ChatSequence([
            {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Arjun Menon"}},
        ]),
    )

    assert result["answer"] == "Arjun Menon's department is Engineering."
    assert result["termination_reason"] is None


def test_existing_priya_department_is_returned_from_database():
    result = agent.run_agent(
        "What department does Priya Nair work in?",
        chat_fn=ChatSequence([
            {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Priya Nair"}},
        ]),
    )

    assert result["answer"] == "Priya Nair's department is Product."


def test_employee_id_department_regression():
    result = agent.run_agent(
        "What department does employee 003 work in?",
        chat_fn=ChatSequence([
            {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
        ]),
    )

    assert result["answer"] == "Neha Iyer's department is Engineering."


def test_invalid_tool_request_is_rejected():
    with pytest.raises(ValueError, match="Unknown tool"):
        agent.execute_tool("run_arbitrary_python", {})


# ---------------------------------------------------------------------------
# Budget tests
# ---------------------------------------------------------------------------

def test_iteration_limit_stops_before_required_calculation(monkeypatch):
    _install_policy_stub(monkeypatch)
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "005"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
    ])

    result = agent.run_agent(
        "For employee 005, give the full annual leave disposition.",
        chat_fn=chat,
        max_iterations=2,
    )

    assert result["iteration_count"] == 2
    assert result["termination_reason"] == "max_iterations"


def test_token_budget_accumulates_and_stops():
    chat = UsageChat([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
    ])

    result = agent.run_agent("Keep computing annual leave disposition for 003.", chat_fn=chat, max_tokens=5)

    assert chat.calls == 1
    assert result["tokens_used"] == 6
    assert result["termination_reason"] == "max_tokens"


def test_cost_budget_accumulates_and_stops():
    chat = UsageChat([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
    ])

    result = agent.run_agent(
        "Keep looking up 003.",
        chat_fn=chat,
        max_cost=0.005,
        cost_per_1k_tokens=1.0,
    )

    assert chat.calls == 1
    assert result["estimated_cost"] == 0.006
    assert result["termination_reason"] == "max_cost"


def test_wall_clock_budget_uses_injectable_clock():
    chat = UsageChat([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
    ])
    clock_calls = {"count": 0}

    def monotonic_clock():
        clock_calls["count"] += 1
        return 0.0 if clock_calls["count"] <= 3 else 2.0

    result = agent.run_agent(
        "Find 003.",
        chat_fn=chat,
        max_wall_clock_seconds=1.0,
        monotonic_fn=monotonic_clock,
    )

    assert chat.calls == 1
    assert result["termination_reason"] == "wall_clock"


def test_budget_result_exposes_usage_source_and_normal_success(monkeypatch):
    _install_policy_stub(monkeypatch)
    chat = UsageChat([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {"action": "tool", "tool": "calculate_annual_leave_disposition",
         "arguments": {"leave_balance": 10, "carry_over_limit": 10, "encashment_limit": 5}},
        {"action": "final", "answer": "The balance is supported by the observed policy."},
    ])

    result = agent.run_agent(
        "How should 003's annual leave balance be handled?",
        chat_fn=chat,
        max_iterations=10,
        max_tokens=10000,
        max_cost=10.0,
        max_wall_clock_seconds=60.0,
    )

    assert result["answer"] == "10 days can be carried over, 5 days can be encashed, and 0 days lapse."
    assert result["termination_reason"] is None
    assert result["terminated_by_budget"] is False
    assert result["token_usage_source"] == "ollama_metadata"


def test_finalizes_full_leave_disposition_without_post_observation_llm_call(monkeypatch):
    calls = {"employee": 0, "policy": 0, "calculation": 0}
    chat = UsageChat([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "002"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {"action": "tool", "tool": "calculate_annual_leave_disposition", "arguments": {
            "leave_balance": 4.0, "carry_over_limit": 10.0, "encashment_limit": 5.0,
        }},
    ])
    monkeypatch.setattr(agent.ollama, "chat", chat)

    def get_employee_data(employee_id=None, employee_name=None):
        calls["employee"] += 1
        assert employee_id == "002"
        return database_get_employee_data(employee_id=employee_id)

    def lookup_policy(jurisdiction):
        calls["policy"] += 1
        return {
            "jurisdiction": jurisdiction,
            "policy_area": "annual_leave_balance",
            "results": [{
                "source": "leave_policy.pdf",
                "chunk_index": 2,
                "content": (
                    "Unused annual leave of up to 10 days may be carried over. "
                    "A maximum of 5 days may be encashed per calendar year."
                ),
            }],
        }

    def calculate_disposition(leave_balance, carry_over_limit, encashment_limit):
        calls["calculation"] += 1
        assert (leave_balance, carry_over_limit, encashment_limit) == (4.0, 10.0, 5.0)
        return {"carryover_days": 4.0, "encashable_days": 4.0, "lapsed_days": 0.0}

    monkeypatch.setattr(agent.TOOLS["get_employee_data"], "callable", get_employee_data)
    monkeypatch.setattr(agent.TOOLS["lookup_annual_leave_policy"], "callable", lookup_policy)
    monkeypatch.setattr(agent.TOOLS["calculate_annual_leave_disposition"], "callable", calculate_disposition)

    result = agent.run_agent("For employee 002, how should the current annual leave balance be handled?")

    assert result["tools_used"] == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    assert calls == {"employee": 1, "policy": 1, "calculation": 1}
    assert chat.calls == 3
    assert "4 days can be carried over" in result["answer"]
    assert "4 days can be encashed" in result["answer"]
    assert "0 days lapse" in result["answer"]
    assert result["termination_reason"] is None
    assert result["terminated_by_budget"] is False


def test_policy_limit_finalizes_without_calculation_or_post_observation_llm_call(monkeypatch):
    calls = {"employee": 0, "policy": 0, "calculation": 0}
    chat = UsageChat([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "004"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
    ])
    monkeypatch.setattr(agent.ollama, "chat", chat)

    def get_employee_data(employee_id=None, employee_name=None):
        calls["employee"] += 1
        return database_get_employee_data(employee_id=employee_id)

    def lookup_policy(jurisdiction):
        calls["policy"] += 1
        return {
            "jurisdiction": jurisdiction,
            "policy_area": "annual_leave_balance",
            "results": [{
                "source": "leave_policy.pdf",
                "chunk_index": 2,
                "content": "A maximum of 5 days may be encashed per calendar year."
            }],
        }

    def unexpected_calculation(**kwargs):
        calls["calculation"] += 1
        raise AssertionError("Policy-limit questions must not calculate disposition")

    monkeypatch.setattr(agent.TOOLS["get_employee_data"], "callable", get_employee_data)
    monkeypatch.setattr(agent.TOOLS["lookup_annual_leave_policy"], "callable", lookup_policy)
    monkeypatch.setattr(agent.TOOLS["calculate_annual_leave_disposition"], "callable", unexpected_calculation)

    result = agent.run_agent(
        "For employee 004, what is the maximum number of days that may be encashed?"
    )

    assert result["tools_used"] == ["get_employee_data", "lookup_annual_leave_policy"]
    assert calls == {"employee": 1, "policy": 1, "calculation": 0}
    assert chat.calls == 2
    assert result["answer"] == "Employees may encash a maximum of 5 days per calendar year."
    assert result["termination_reason"] is None


def test_employee_only_question_finalizes_from_record_without_policy_tools(monkeypatch):
    calls = {"employee": 0, "policy": 0, "calculation": 0}
    chat = UsageChat([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Neha Iyer"}},
    ])
    monkeypatch.setattr(agent.ollama, "chat", chat)

    def get_employee_data(employee_id=None, employee_name=None):
        calls["employee"] += 1
        return database_get_employee_data(employee_name=employee_name)

    def unexpected_policy(**kwargs):
        calls["policy"] += 1
        raise AssertionError("Employee-only questions must not look up policy")

    def unexpected_calculation(**kwargs):
        calls["calculation"] += 1
        raise AssertionError("Employee-only questions must not calculate disposition")

    monkeypatch.setattr(agent.TOOLS["get_employee_data"], "callable", get_employee_data)
    monkeypatch.setattr(agent.TOOLS["lookup_annual_leave_policy"], "callable", unexpected_policy)
    monkeypatch.setattr(agent.TOOLS["calculate_annual_leave_disposition"], "callable", unexpected_calculation)

    result = agent.run_agent("What is Neha Iyer's annual salary?")

    assert result["tools_used"] == ["get_employee_data"]
    assert calls == {"employee": 1, "policy": 0, "calculation": 0}
    assert chat.calls == 1
    assert result["answer"] == "Neha Iyer's annual salary is 840,000."
    assert result["termination_reason"] is None


def test_employee_question_with_multiple_fields_answers_all_requested_fields():
    chat = ChatSequence([
        {
            "action": "tool",
            "tool": "get_employee_data",
            "arguments": {"employee_name": "Priya Nair"},
        },
    ])

    result = agent.run_agent(
        "What is Priya Nair's leave balance and annual salary?",
        chat_fn=chat,
    )

    assert "Priya Nair's annual salary is 1,800,000" in result["answer"]
    assert "leave balance is 20.0" in result["answer"]
    assert result["tools_used"] == ["get_employee_data"]
    assert chat.calls == 1
    assert result["termination_reason"] is None


def test_deterministic_final_answer_uses_only_calculation_observation():
    state = agent.AgentState(
        original_question="For employee 002, give the full annual leave disposition.",
        employee_record={"employee_id": "002", "tenure_years": 99.0},
        policy_result={"results": [{"content": "Unrelated policy claim: 99 days."}]},
        calculation_result={"carryover_days": 4.0, "encashable_days": 4.0, "lapsed_days": 0.0},
    )

    def unexpected_llm_call(**kwargs):
        raise AssertionError("Structured calculation finalization must not call the LLM")

    answer = agent._generate_final_answer(state, unexpected_llm_call)

    assert answer == "4 days can be carried over, 4 days can be encashed, and 0 days lapse."


# ---------------------------------------------------------------------------
# Generalized completion and duplicate protection tests
# ---------------------------------------------------------------------------

def test_neha_salary_single_tool_execution():
    """Verify single-tool employee questions generate final answer without policy/calc or duplicate tool calls."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Neha Iyer"}},
        {"action": "final", "answer": "Neha Iyer's annual salary is ₹8,40,000."},
    ])

    result = agent.run_agent("What is Neha Iyer's annual salary?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employee_data"]
    assert len(tool_names) == 1
    assert "lookup_annual_leave_policy" not in str(result["trace"])
    assert "calculate_annual_leave_disposition" not in str(result["trace"])
    assert "840000" in str(result["steps"][0]["observation"]) or "840000" in result["answer"]


def test_employee_plus_policy_question_does_not_call_calc(monkeypatch):
    """Verify employee + policy question calls get_employee_data and lookup_annual_leave_policy but not calc."""
    _install_policy_stub(monkeypatch)
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Neha Iyer"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {"action": "final", "answer": "Neha Iyer has 10 days leave balance compared with policy carryover limit of 10 days."},
    ])

    result = agent.run_agent("What is Neha Iyer's leave balance compared with the annual leave policy?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employee_data", "lookup_annual_leave_policy"]
    assert "calculate_annual_leave_disposition" not in tool_names


def test_carry_forward_remaining_leave_uses_existing_disposition_flow(monkeypatch):
    _install_policy_stub(monkeypatch)
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Priya Nair"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {
            "action": "tool",
            "tool": "calculate_annual_leave_disposition",
            "arguments": {
                "leave_balance": 20.0,
                "carry_over_limit": 10.0,
                "encashment_limit": 5.0,
            },
        },
    ])

    result = agent.run_agent(
        "Can Priya Nair carry forward her remaining annual leave?",
        chat_fn=chat,
    )

    assert [
        step["tool"] for step in result["steps"] if step.get("phase") == "tool"
    ] == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    assert "10 days can be carried over" in result["answer"]


def test_duplicate_tool_call_protection_prevents_infinite_loop():
    """Verify duplicate successful tool calls are prevented from looping."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Neha Iyer"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Neha Iyer"}},  # duplicate attempt
        {"action": "final", "answer": "Neha Iyer's annual salary is ₹8,40,000."},
    ])

    result = agent.run_agent("What is Neha Iyer's annual salary?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employee_data"]
    assert result["termination_reason"] is None


def test_leave_calculation_questions_are_detected_for_race_cases():
    """Questions about carry-over, encashment, lapse, or full disposition require calculation."""
    cases = [
        "For employee 003, how many days can be carried over and encashed?",
        "For employee 005, how many unused annual leave days lapse?",
        "For employee 001, does any annual leave balance lapse?",
        "For employee 005, give the full annual leave disposition.",
        "For employee 006, report the annual leave carry-over, encashment, and lapse amounts.",
    ]
    for question in cases:
        assert agent._question_requires_calculation(question.lower()) is True

    policy_only = "For employee 004, what is the maximum number of days that may be encashed?"
    assert agent._question_requires_calculation(policy_only.lower()) is False


def test_duplicate_employee_call_continues_when_policy_is_missing(monkeypatch):
    """A duplicate employee lookup must be overridden by the missing policy tool."""
    _install_policy_stub(monkeypatch)
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "005"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "005"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {"action": "tool", "tool": "calculate_annual_leave_disposition",
         "arguments": {"leave_balance": 20, "carry_over_limit": 10, "encashment_limit": 5}},
        {"action": "final", "answer": "10 carry-over, 5 encashable, and 10 lapsed days."},
    ])

    result = agent.run_agent("For employee 005, give the full annual leave disposition.", chat_fn=chat)

    tool_names = [step["tool"] for step in result["steps"] if step.get("phase") == "tool"]
    assert tool_names == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    assert tool_names.count("get_employee_data") == 1
    assert result["answer"] == "10 days can be carried over, 5 days can be encashed, and 10 days lapse."


def test_recommended_next_tool_is_enforced_for_missing_policy_state(monkeypatch):
    """If a required tool is missing, the agent must follow the missing-information recommendation instead of repeating a completed tool."""
    _install_policy_stub(monkeypatch)
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "005"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {"action": "tool", "tool": "calculate_annual_leave_disposition",
         "arguments": {"leave_balance": 20, "carry_over_limit": 10, "encashment_limit": 5}},
        {"action": "final", "answer": "10 carry-over, 5 encashable, and 10 lapsed days."},
    ])

    result = agent.run_agent("For employee 005, give the full annual leave disposition.", chat_fn=chat)

    tool_names = [step["tool"] for step in result["steps"] if step.get("phase") == "tool"]
    assert tool_names == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    assert result["answer"] == "10 days can be carried over, 5 days can be encashed, and 10 days lapse."


def test_explicit_employee_id_overrides_model_name():
    """An ID in the question is dispatched as that exact ID."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Priya Nair"}},
        {"action": "final", "answer": "No annual leave balance lapses."},
    ])

    result = agent.run_agent(
        "For employee 001, does any annual leave balance lapse?",
        chat_fn=chat,
    )

    first_tool = next(step for step in result["steps"] if step.get("phase") == "tool")
    assert first_tool["arguments"] == {"employee_id": "001"}
    assert first_tool["observation"]["result"]["employee_id"] == "001"


def test_missing_information_state_employee_only():
    state = agent.AgentState(original_question="What is Neha Iyer's annual salary?")
    state.employee_record = {"employee_id": "003", "annual_salary": 840000.0}

    guidance = agent._missing_information_state(state)

    assert guidance["observations"] == {
        "employee_record": True,
        "policy_result": False,
        "calculation_result": False,
    }
    assert guidance["requirements"] == {
        "employee_record": True,
        "annual_leave_policy": False,
        "leave_disposition_calculation": False,
    }
    assert guidance["missing_information"] == []
    assert guidance["recommended_next_tool"] is None
    assert guidance["sufficient_for_final"] is True


def test_missing_information_state_policy_only():
    state = agent.AgentState(
        original_question="For employee 004, what is the maximum number of days that may be encashed?",
        employee_record={"employee_id": "004", "leave_balance": 12.0},
    )

    guidance = agent._missing_information_state(state)

    assert guidance["missing_information"] == ["annual_leave_policy"]
    assert guidance["recommended_next_tool"] == "lookup_annual_leave_policy"
    assert guidance["requirements"]["leave_disposition_calculation"] is False


def test_missing_information_state_calculation_progression():
    state = agent.AgentState(
        original_question="For employee 005, give the full annual leave disposition.",
        employee_record={"employee_id": "005", "leave_balance": 20.0},
    )

    before_policy = agent._missing_information_state(state)
    assert before_policy["missing_information"] == [
        "annual_leave_policy",
        "leave_disposition_calculation",
    ]
    assert before_policy["recommended_next_tool"] == "lookup_annual_leave_policy"

    state.policy_result = {"policy_area": "annual_leave_balance"}
    after_policy = agent._missing_information_state(state)
    assert after_policy["missing_information"] == ["leave_disposition_calculation"]
    assert after_policy["recommended_next_tool"] == "calculate_annual_leave_disposition"


def test_tool_registry_contains_all_expected_tools():
    expected = {
        "get_employee_data",
        "get_department_employees",
        "get_employees_by_manager",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    }
    assert set(agent.TOOLS.keys()) == expected
