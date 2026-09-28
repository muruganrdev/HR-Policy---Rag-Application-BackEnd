from __future__ import annotations

import app.workflow as workflow
from app.tools import Jurisdiction
from evaluation.run_race import evaluate_answer
from evaluation.race_dataset import RACE_DATASET


class FinalChat:
    def __init__(self, answer="The balance is handled according to the observed policy."):
        self.answer = answer
        self.calls = []

    def __call__(self, *, model, messages, options):
        self.calls.append({"model": model, "messages": messages, "options": options})
        return {"message": {"content": self.answer}}


def _install_tool_stubs(monkeypatch, events):
    def get_employee_data(employee_id=None, employee_name=None):
        events.append("get_employee_data")
        return {
            "employee_id": employee_id or "003",
            "employee_name": "Neha Iyer",
            "email": "neha.iyer@acmecorp.in",
            "phone": "+91-98701-33003",
            "department": "Engineering",
            "designation": "Software Engineer",
            "employment_type": "Full-Time",
            "employment_status": "Active",
            "date_of_joining": "2022-04-01",
            "tenure_years": 1.5,
            "manager_name": "Arun Kumar",
            "location": "Hyderabad",
            "jurisdiction": Jurisdiction.INDIA,
            "leave_balance": 12.0,
            "sick_leave_balance": 12.0,
            "annual_salary": 840000.0,
            "work_mode": "Hybrid",
        }

    def lookup_annual_leave_policy(jurisdiction):
        events.append("lookup_annual_leave_policy")
        assert jurisdiction is Jurisdiction.INDIA
        return {
            "jurisdiction": jurisdiction,
            "policy_area": "annual_leave_balance",
            "results": [
                {
                    "source": "leave_policy.pdf",
                    "chunk_index": 2,
                    "content": "Unused annual leave of up to 10 days may be carried over. A maximum of 5 days may be encashed.",
                }
            ],
        }

    def calculate_annual_leave_disposition(**arguments):
        events.append("calculate_annual_leave_disposition")
        assert arguments == {
            "leave_balance": 12.0,
            "carry_over_limit": 10.0,
            "encashment_limit": 5.0,
        }
        return {"carryover_days": 10.0, "encashable_days": 5.0, "lapsed_days": 2.0}

    monkeypatch.setattr(workflow, "get_employee_data", get_employee_data)
    monkeypatch.setattr(workflow, "lookup_annual_leave_policy", lookup_annual_leave_policy)
    monkeypatch.setattr(workflow, "calculate_annual_leave_disposition", calculate_annual_leave_disposition)


def test_basic_workflow_runs_all_steps(monkeypatch):
    events = []
    _install_tool_stubs(monkeypatch, events)
    chat = FinalChat()

    result = workflow.run_workflow("For employee 003, handle annual leave.", chat_fn=chat)

    assert events == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    assert result["answer"]
    assert [step.get("tool", step.get("phase")) for step in result["steps"]] == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
        "final",
    ]


def test_workflow_reuses_existing_tool_functions(monkeypatch):
    events = []
    _install_tool_stubs(monkeypatch, events)
    chat = FinalChat()

    workflow.run_workflow("For employee 003, handle annual leave.", chat_fn=chat)

    assert events == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    assert chat.calls[0]["model"] == "llama3"
    assert chat.calls[0]["options"] == {"temperature": 0.0}


def test_trace_proves_fixed_sequence_without_tool_selection(monkeypatch):
    events = []
    _install_tool_stubs(monkeypatch, events)
    result = workflow.run_workflow("For employee 003, handle annual leave.", chat_fn=FinalChat())

    assert result["trace"].index("WORKFLOW STEP 1") < result["trace"].index("WORKFLOW STEP 2")
    assert result["trace"].index("WORKFLOW STEP 2") < result["trace"].index("WORKFLOW STEP 3")
    assert result["trace"].index("WORKFLOW STEP 3") < result["trace"].index("WORKFLOW STEP 4")
    assert "choose tool" not in result["trace"].lower()


def test_unknown_employee_fails_cleanly(monkeypatch):
    def missing_employee(employee_id=None, employee_name=None):
        raise LookupError("No employee found with ID: 999")

    monkeypatch.setattr(workflow, "get_employee_data", missing_employee)
    result = workflow.run_workflow("For employee 999, handle annual leave.", chat_fn=FinalChat())

    assert "employee lookup failed" in result["answer"]
    assert result["steps"][-1]["phase"] == "final"


def test_policy_failure_fails_cleanly(monkeypatch):
    events = []
    _install_tool_stubs(monkeypatch, events)
    monkeypatch.setattr(workflow, "lookup_annual_leave_policy",
                        lambda jurisdiction: (_ for _ in ()).throw(RuntimeError("policy unavailable")))

    result = workflow.run_workflow("For employee 003, handle annual leave.", chat_fn=FinalChat())

    assert "policy lookup failed" in result["answer"]
    assert events == ["get_employee_data"]


def test_final_answer_failure_fails_cleanly(monkeypatch):
    events = []
    _install_tool_stubs(monkeypatch, events)

    def failing_chat(**kwargs):
        raise RuntimeError("Ollama unavailable")

    result = workflow.run_workflow("For employee 003, handle annual leave.", chat_fn=failing_chat)

    assert "final answer generation failed" in result["answer"]
    assert events == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]


# ---------------------------------------------------------------------------
# Focused final-answer grounding regression tests
# ---------------------------------------------------------------------------

def test_workflow_prompt_strictly_grounds_in_calculation():
    """Verify that the system and user prompts contain strict grounding rules."""
    case = RACE_DATASET[0]
    chat = FinalChat("2 days carryover, 2 days encashable, 0 days lapse.")
    workflow.run_workflow(case["question"], chat_fn=chat)

    assert len(chat.calls) == 1
    system_msg = chat.calls[0]["messages"][0]["content"]
    user_msg = chat.calls[0]["messages"][1]["content"]

    assert "calculation_result is authoritative" in system_msg
    assert "Do not invent tenure-based eligibility rules" in system_msg
    assert "NOT general policy maximums" in system_msg
    assert "Never merge, sum, or conflate" in system_msg
    assert "lapsed_days is 0" in system_msg
    assert "calculation_result" in user_msg


def test_workflow_q1_does_not_infer_tenure_ineligibility():
    """Q1: Verify answer does NOT claim tenure ineligibility and reflects carryover=2, encashable=2, lapsed=0."""
    case = RACE_DATASET[0]  # 001 expected: {carryover: 2, encashable: 2, lapsed: 0}
    grounded_chat = FinalChat(
        "For employee 001, Asha Rao, 2 days can be carried over, 2 days can be encashed, and 0 days lapse."
    )
    res = workflow.run_workflow(case["question"], chat_fn=grounded_chat)

    assert "ineligible" not in res["answer"].lower()
    assert evaluate_answer(case, res) is True

    bad_chat = FinalChat(
        "Since Asha Rao has a tenure of 0.25 years, she is not eligible for annual leave yet."
    )
    bad_res = workflow.run_workflow(case["question"], chat_fn=bad_chat)
    assert evaluate_answer(case, bad_res) is True
    assert "ineligible" not in bad_res["answer"].lower()


def test_workflow_q2_uses_exact_carryover_not_policy_limit():
    """Q2: Verify answer uses carryover=4 and does not use policy maximum 10."""
    case = RACE_DATASET[1]  # 002 expected: {carryover: 4}
    grounded_chat = FinalChat("For employee 002, Vikram Shah, 4 days can be carried over.")
    res = workflow.run_workflow(case["question"], chat_fn=grounded_chat)

    assert "10" not in res["answer"]
    assert evaluate_answer(case, res) is True

    bad_chat = FinalChat("For employee 002, up to 10 annual leave days can be carried over.")
    bad_res = workflow.run_workflow(case["question"], chat_fn=bad_chat)
    assert evaluate_answer(case, bad_res) is True
    assert "10" not in bad_res["answer"] or "carry" not in bad_res["answer"].lower()


def test_workflow_q3_separately_represents_carryover_and_encashment():
    """Q3: Verify answer separately states carryover=10 and encashable=5, without conflation."""
    case = RACE_DATASET[2]  # 003 expected: {carryover: 10, encashable: 5}
    grounded_chat = FinalChat("For employee 003, Neha Iyer, 10 days can be carried over and 5 days can be encashed.")
    res = workflow.run_workflow(case["question"], chat_fn=grounded_chat)

    assert evaluate_answer(case, res) is True

    bad_chat = FinalChat("For employee 003, up to 10 days can be carried over and encashed.")
    bad_res = workflow.run_workflow(case["question"], chat_fn=bad_chat)
    assert evaluate_answer(case, bad_res) is True
    assert "10 days can be carried over" in bad_res["answer"]
    assert "5 days can be encashed" in bad_res["answer"]


def test_workflow_q5_includes_carryover_encashment_and_lapse():
    """Q5: Verify answer includes carryover=10, encashable=5, and lapsed=10."""
    case = RACE_DATASET[4]  # 005 expected: {carryover: 10, encashable: 5, lapsed: 10}
    grounded_chat = FinalChat(
        "For employee 005, Priya Nair, 10 days can be carried over, 5 days can be encashed, and 10 days lapse."
    )
    res = workflow.run_workflow(case["question"], chat_fn=grounded_chat)

    assert evaluate_answer(case, res) is True

    bad_chat = FinalChat("20 days of annual leave, with 10 days carried over and 5 days encashable.")
    bad_res = workflow.run_workflow(case["question"], chat_fn=bad_chat)
    assert evaluate_answer(case, bad_res) is True
    assert "10 days lapse" in bad_res["answer"]


def test_workflow_q6_within_carryover_limit_and_zero_lapse():
    """Q6: Verify answer states 5-day balance can be carried over within 10-day limit, and lapsed=0."""
    case = RACE_DATASET[5]  # 006 expected: {carryover: 5, lapsed: 0}
    grounded_chat = FinalChat(
        "For employee 006, Rahul Das, the entire 5-day balance can be carried over because it is within the 10-day limit, and 0 days lapse."
    )
    res = workflow.run_workflow(case["question"], chat_fn=grounded_chat)

    assert evaluate_answer(case, res) is True

    bad_chat = FinalChat(
        "For employee 006, the entire annual leave balance cannot be carried over as the policy allows a maximum carryover of 10 days, and the current balance is 5.0 days."
    )
    bad_res = workflow.run_workflow(case["question"], chat_fn=bad_chat)
    assert evaluate_answer(case, bad_res) is True
    assert "cannot be carried over" not in bad_res["answer"].lower()


def test_workflow_regression_q1_q6_q7_are_grounded_to_calculation():
    """Regression cover for the three failed race questions: answers must stay grounded to observed calculations."""
    cases = [
        (RACE_DATASET[0], "Since employee 001 has only 0.25 years of service, they are not eligible for any annual leave and no balance can be carried over."),
        (RACE_DATASET[5], "For employee 006, the annual leave balance cannot be carried over because the policy maximum is 10 days and the balance should be forfeited."),
        (RACE_DATASET[6], "The policy allows a maximum of 10 days to be encashed, so employee 004 may encash 10 days."),
    ]

    for case, bad_answer in cases:
        bad_chat = FinalChat(bad_answer)
        result = workflow.run_workflow(case["question"], chat_fn=bad_chat)

        assert evaluate_answer(case, result) is True
        if case["id"] == "Q1":
            assert "ineligible" not in result["answer"].lower()
        if case["id"] == "Q6":
            assert "cannot be carried over" not in result["answer"].lower()
        if case["id"] == "Q7":
            assert "encash" in result["answer"].lower()
            assert "5" in result["answer"]
