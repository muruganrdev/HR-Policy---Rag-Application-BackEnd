"""Focused regression tests for Week 8 Step 5 completion-state and TOOL_LOOP mitigation."""

import json
import pytest

import app.agent as agent


class ChatSequence:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = 0

    def __call__(self, **kwargs):
        self.calls += 1
        return {"message": {"content": json.dumps(next(self.payloads))}}


def test_1_employee_only_no_repeated_calls():
    """Test 1: Employee-only question stops after get_employee_data without loops."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Neha Iyer"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Neha Iyer"}},
    ])

    result = agent.run_agent("What is Neha Iyer's annual salary?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employee_data"]
    assert "840,000" in result["answer"] or "840000" in result["answer"]
    assert result["iteration_count"] == 1


def test_2_policy_only_no_employee_calls():
    """Test 2: Policy-only question stops after lookup_annual_leave_policy without employee calls."""
    chat = ChatSequence([
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
    ])

    result = agent.run_agent("What is the annual leave carry-over limit under the policy?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["lookup_annual_leave_policy"]
    assert "10 days" in result["answer"]
    assert result["iteration_count"] == 1


def test_3_department_query_stops_after_department_tool():
    """Test 3: Department question stops after get_department_employees."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_department_employees", "arguments": {"department_name": "Engineering"}},
        {"action": "final", "answer": "Neha Iyer and Arjun Menon work in Engineering."},
    ])

    result = agent.run_agent("Which employees work in Engineering?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_department_employees"]
    assert result["iteration_count"] == 1


def test_4_manager_query_stops_after_manager_tool():
    """Test 4: Manager question stops after get_employees_by_manager."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employees_by_manager", "arguments": {"manager_name": "Arun Kumar"}},
        {"action": "final", "answer": "Neha Iyer and Arjun Menon report to Arun Kumar."},
    ])

    result = agent.run_agent("Which employees report to Arun Kumar?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employees_by_manager"]
    assert result["iteration_count"] == 1


def test_5_employee_plus_policy_comparison():
    """Test 5: Comparison question requires employee then policy then final."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_name": "Priya Nair"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
    ])

    result = agent.run_agent(
        "Compare Priya Nair's annual leave balance with the annual leave carry-over limit.",
        chat_fn=chat,
    )

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employee_data", "lookup_annual_leave_policy"]
    assert "20" in result["answer"]
    assert "10" in result["answer"]


def test_6_full_disposition_no_extra_decision_call_after_calculation():
    """Test 6: Full disposition finishes immediately after calculate_annual_leave_disposition."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "005"}},
        {"action": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {
            "action": "tool",
            "tool": "calculate_annual_leave_disposition",
            "arguments": {"leave_balance": 20.0, "carry_over_limit": 10.0, "encashment_limit": 5.0},
        },
    ])

    result = agent.run_agent("For employee 005, give the full annual leave disposition.", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    # Required observations are sufficient after calculation, so the Agent finalizes without a 4th decision call.
    assert chat.calls == 1
    assert "10 days can be carried over" in result["answer"]


def test_7_duplicate_successful_tool_checked_and_not_looped():
    """Test 7: A duplicate tool call is prevented and completion state produces final answer."""
    chat = ChatSequence([
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
        {"action": "tool", "tool": "get_employee_data", "arguments": {"employee_id": "003"}},
    ])

    result = agent.run_agent("What is Neha Iyer's annual salary?", chat_fn=chat)

    tool_names = [s["tool"] for s in result["steps"] if s.get("phase") == "tool"]
    assert tool_names == ["get_employee_data"]
    assert "840,000" in result["answer"] or "840000" in result["answer"]
    assert result["termination_reason"] is None


def test_8_missing_policy_recommends_policy_not_repeated_employee():
    """Test 8: Having employee_record but missing policy recommends policy lookup."""
    state = agent.AgentState(
        original_question="How much annual leave can Priya Nair carry over under the policy?",
        employee_record={"employee_id": "005", "employee_name": "Priya Nair", "leave_balance": 25.0},
    )

    guidance = agent._missing_information_state(state)

    assert "annual_leave_policy" in guidance["missing_information"]
    assert "employee_record" not in guidance["missing_information"]
    assert guidance["recommended_next_tool"] == "lookup_annual_leave_policy"
