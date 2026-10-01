import json

import pytest

import app.agent as agent
from app.security import (
    SecurityValidationError,
    authorization_for_question,
    minimum_tools_for_question,
    minimize_tool_result,
    validate_final_answer,
    validate_tool_call,
    validate_tool_result,
)
from app.tools import Jurisdiction


REGISTERED_TOOLS = frozenset(agent.TOOLS)


class AgentChat:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.requests = []

    def __call__(self, **request):
        self.requests.append(request)
        return {"message": {"content": json.dumps(next(self.actions))}}


def _agent_tool(name, arguments):
    return {"action": "tool", "tool": name, "arguments": arguments}


def _valid_policy_result(content="Unused annual leave of up to 10 days may be carried over. A maximum of 5 days may be encashed."):
    return {
        "jurisdiction": Jurisdiction.INDIA,
        "policy_area": "annual_leave_balance",
        "results": [
            {
                "source": "leave_policy.pdf",
                "chunk_index": 2,
                "content": content,
            }
        ],
    }


def _authorization(question, **kwargs):
    return authorization_for_question(question, REGISTERED_TOOLS, **kwargs)


@pytest.mark.parametrize("tool_name", ["secret_tool", "delete_employee"])
def test_unknown_tool_is_rejected_before_dispatch(tool_name):
    with pytest.raises(ValueError, match=f"Unknown tool: {tool_name}"):
        agent.execute_tool(tool_name, {})


def test_production_agent_rejects_unknown_tool_before_callable(monkeypatch):
    called = []
    monkeypatch.setattr(
        agent.TOOLS["get_employee_data"],
        "callable",
        lambda **kwargs: called.append(kwargs),
    )
    chat = AgentChat([_agent_tool("secret_tool", {})])

    result = agent.run_agent("What is Neha Iyer's annual salary?", chat_fn=chat)

    assert called == []
    assert "could not be validated" in result["answer"]


def test_production_agent_returns_not_found_for_scoped_nonexistent_employee_id(monkeypatch):
    called = []

    def missing_employee(**kwargs):
        called.append(kwargs)
        raise agent.EmployeeNotFoundError("No employee found with ID: 999")

    monkeypatch.setattr(
        agent.TOOLS["get_employee_data"],
        "callable",
        missing_employee,
    )
    chat = AgentChat([_agent_tool("get_employee_data", {"employee_id": "999"})])

    result = agent.run_agent("For employee 999, what is the annual salary?", chat_fn=chat)

    assert called == [{"employee_id": "999", "employee_name": None}]
    assert result["steps"][0]["observation"]["status"] == "not_found"
    assert "couldn't find" in result["answer"]
    assert "999" in result["answer"]


def test_production_agent_rejects_invalid_jurisdiction_before_callable(monkeypatch):
    called = []
    monkeypatch.setattr(
        agent.TOOLS["lookup_annual_leave_policy"],
        "callable",
        lambda **kwargs: called.append(kwargs),
    )
    chat = AgentChat(
        [_agent_tool("lookup_annual_leave_policy", {"jurisdiction": "MARS"})]
    )

    result = agent.run_agent(
        "What is the annual leave carry-over limit?", chat_fn=chat
    )

    assert called == []
    assert "security validation failed" in result["answer"]


@pytest.mark.parametrize(
    ("question", "tool_name", "arguments", "malformed_result"),
    [
        (
            "What is Neha Iyer's annual salary?",
            "get_employee_data",
            {"employee_name": "Neha Iyer"},
            {"employee_id": "003"},
        ),
        (
            "What is the annual leave carry-over limit?",
            "lookup_annual_leave_policy",
            {"jurisdiction": "INDIA"},
            {
                "jurisdiction": Jurisdiction.INDIA,
                "policy_area": "annual_leave_balance",
                "results": [{"content": "Up to 10 days may be carried over."}],
            },
        ),
    ],
)
def test_production_agent_stops_on_malformed_employee_or_policy_result(
    monkeypatch, question, tool_name, arguments, malformed_result
):
    dispatched = []

    def malformed_callable(**kwargs):
        dispatched.append(kwargs)
        return malformed_result

    monkeypatch.setattr(agent.TOOLS[tool_name], "callable", malformed_callable)
    result = agent.run_agent(
        question,
        chat_fn=AgentChat([_agent_tool(tool_name, arguments)]),
    )

    assert len(dispatched) == 1
    assert result["steps"][0]["observation"]["status"] == "error"
    assert not any(step.get("phase") == "tool" for step in result["steps"][1:])
    assert "security validation failed" in result["answer"]


def test_production_agent_stops_on_inconsistent_calculation_result(monkeypatch):
    monkeypatch.setattr(
        agent.TOOLS["lookup_annual_leave_policy"],
        "callable",
        lambda **kwargs: _valid_policy_result(),
    )
    monkeypatch.setattr(
        agent.TOOLS["calculate_annual_leave_disposition"],
        "callable",
        lambda **kwargs: {
            "carryover_days": 20.0,
            "encashable_days": 5.0,
            "lapsed_days": 0.0,
        },
    )
    chat = AgentChat(
        [
            _agent_tool("get_employee_data", {"employee_id": "005"}),
            _agent_tool("lookup_annual_leave_policy", {"jurisdiction": "INDIA"}),
            _agent_tool(
                "calculate_annual_leave_disposition",
                {
                    "leave_balance": 20.0,
                    "carry_over_limit": 10.0,
                    "encashment_limit": 5.0,
                },
            ),
        ]
    )

    result = agent.run_agent(
        "For employee 005, give the full annual leave disposition.", chat_fn=chat
    )

    assert result["steps"][2]["observation"]["status"] == "error"
    assert "20 days can be carried over" not in result["answer"]
    assert "security validation failed" in result["answer"]


def test_production_agent_rejects_final_answer_contradicting_calculation(monkeypatch):
    monkeypatch.setattr(
        agent.TOOLS["lookup_annual_leave_policy"],
        "callable",
        lambda **kwargs: _valid_policy_result(),
    )
    monkeypatch.setattr(
        agent,
        "_generate_final_answer",
        lambda *args, **kwargs: "20 days can be carried over, 5 days can be encashed, and 0 days lapse.",
    )
    chat = AgentChat(
        [
            _agent_tool("get_employee_data", {"employee_id": "005"}),
            _agent_tool("lookup_annual_leave_policy", {"jurisdiction": "INDIA"}),
            _agent_tool(
                "calculate_annual_leave_disposition",
                {
                    "leave_balance": 20.0,
                    "carry_over_limit": 10.0,
                    "encashment_limit": 5.0,
                },
            ),
        ]
    )

    result = agent.run_agent(
        "For employee 005, give the full annual leave disposition.", chat_fn=chat
    )

    assert "20 days can be carried over" not in result["answer"]
    assert "could not be validated" in result["answer"]


def test_production_agent_preserves_legitimate_minimized_employee_result():
    chat = AgentChat(
        [
            _agent_tool(
                "get_employee_data", {"employee_name": "Neha Iyer"}
            )
        ]
    )

    result = agent.run_agent("What is Neha Iyer's annual salary?", chat_fn=chat)

    assert "840,000" in result["answer"]
    observation = result["steps"][0]["observation"]["result"]
    assert observation == {"employee_name": "Neha Iyer", "annual_salary": 840000.0}


def test_production_agent_preserves_legitimate_policy_result(monkeypatch):
    monkeypatch.setattr(
        agent.TOOLS["lookup_annual_leave_policy"],
        "callable",
        lambda **kwargs: _valid_policy_result(),
    )
    chat = AgentChat(
        [_agent_tool("lookup_annual_leave_policy", {"jurisdiction": "INDIA"})]
    )

    result = agent.run_agent(
        "What is the annual leave carry-over limit?", chat_fn=chat
    )

    assert "10 days" in result["answer"]


def test_production_full_disposition_keeps_dynamic_tool_sequence(monkeypatch):
    monkeypatch.setattr(
        agent.TOOLS["lookup_annual_leave_policy"],
        "callable",
        lambda **kwargs: _valid_policy_result(),
    )
    chat = AgentChat(
        [
            _agent_tool("get_employee_data", {"employee_id": "005"}),
            _agent_tool("lookup_annual_leave_policy", {"jurisdiction": "INDIA"}),
            _agent_tool(
                "calculate_annual_leave_disposition",
                {
                    "leave_balance": 20.0,
                    "carry_over_limit": 10.0,
                    "encashment_limit": 5.0,
                },
            ),
        ]
    )

    result = agent.run_agent(
        "For employee 005, give the full annual leave disposition.", chat_fn=chat
    )

    assert [step["tool"] for step in result["steps"] if step.get("phase") == "tool"] == [
        "get_employee_data",
        "lookup_annual_leave_policy",
        "calculate_annual_leave_disposition",
    ]
    assert "10 days can be carried over" in result["answer"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"employee_id": ""},
        {"employee_id": "DROP TABLE employees"},
        {"employee_id": 999},
    ],
)
def test_invalid_employee_arguments_are_rejected(arguments):
    authorization = _authorization(
        "Find employee 003.",
    )
    with pytest.raises((ValueError, PermissionError)):
        validate_tool_call("get_employee_data", arguments, authorization)


def test_valid_employee_lookup_argument_is_accepted():
    authorization = _authorization("Find employee 003.")

    assert validate_tool_call(
        "get_employee_data", {"employee_id": "003"}, authorization
    ) == {"employee_id": "003"}


def test_invalid_department_and_manager_arguments_are_rejected():
    department_auth = _authorization("Which employees work in Engineering?")
    manager_auth = _authorization("Which employees report to Arun Kumar?")

    with pytest.raises(ValueError, match="department_name"):
        validate_tool_call(
            "get_department_employees", {"department_name": ""}, department_auth
        )
    with pytest.raises(ValueError, match="manager_name"):
        validate_tool_call(
            "get_employees_by_manager", {"manager_name": ""}, manager_auth
        )


def test_invalid_jurisdiction_is_rejected():
    authorization = _authorization("What is the annual leave policy limit?")

    with pytest.raises(ValueError, match="jurisdiction must be INDIA"):
        validate_tool_call(
            "lookup_annual_leave_policy",
            {"jurisdiction": "MARS"},
            authorization,
        )
    assert validate_tool_call(
        "lookup_annual_leave_policy",
        {"jurisdiction": Jurisdiction.INDIA},
        authorization,
    ) == {"jurisdiction": Jurisdiction.INDIA}


@pytest.mark.parametrize(
    "result",
    [
        {
            "employee_id": "003",
            "employee_name": "Neha Iyer",
            "department": "Engineering",
            "designation": "Engineer",
            "annual_salary": "not-a-number",
            "leave_balance": 10.0,
            "jurisdiction": Jurisdiction.INDIA,
        },
        {
            "employee_id": "003",
            "employee_name": "Neha Iyer",
            "department": "Engineering",
            "designation": "Engineer",
            "annual_salary": 840000.0,
            "leave_balance": None,
            "jurisdiction": Jurisdiction.INDIA,
        },
    ],
)
def test_malformed_employee_result_is_rejected(result):
    with pytest.raises(SecurityValidationError):
        validate_tool_result("get_employee_data", result)


@pytest.mark.parametrize(
    "result",
    [
        {
            "jurisdiction": Jurisdiction.INDIA,
            "policy_area": "annual_leave_balance",
            "results": [{"content": None}],
        },
        {
            "jurisdiction": "MARS",
            "policy_area": "annual_leave_balance",
            "results": [],
        },
    ],
)
def test_malformed_policy_result_is_rejected(result):
    with pytest.raises(SecurityValidationError):
        validate_tool_result("lookup_annual_leave_policy", result)


@pytest.mark.parametrize(
    "result",
    [
        {"carryover_days": 10.0, "encashable_days": 5.0},
        {"carryover_days": "ten", "encashable_days": 5.0, "lapsed_days": 0.0},
        {"carryover_days": -1.0, "encashable_days": 5.0, "lapsed_days": 0.0},
    ],
)
def test_malformed_calculation_results_are_rejected(result):
    with pytest.raises(SecurityValidationError):
        validate_tool_result("calculate_annual_leave_disposition", result)


def test_calculation_result_is_validated_against_authoritative_inputs():
    inputs = {
        "leave_balance": 20.0,
        "carry_over_limit": 10.0,
        "encashment_limit": 5.0,
    }
    result = {"carryover_days": 10.0, "encashable_days": 5.0, "lapsed_days": 10.0}

    assert validate_tool_result(
        "calculate_annual_leave_disposition",
        result,
        expected_calculation_inputs=inputs,
    ) == result
    with pytest.raises(SecurityValidationError, match="contradicts"):
        validate_tool_result(
            "calculate_annual_leave_disposition",
            {**result, "carryover_days": 20.0},
            expected_calculation_inputs=inputs,
        )


def test_employee_field_minimization_keeps_only_requested_value():
    question = "What is Neha Iyer's annual salary?"
    authorization = _authorization(question)
    employee = {
        "employee_id": "003",
        "employee_name": "Neha Iyer",
        "annual_salary": 840000.0,
        "email": "neha@example.test",
        "department": "Engineering",
        "location": "Hyderabad",
        "manager_name": "Arun Kumar",
        "sick_leave_balance": 12.0,
        "tenure_years": 1.5,
        "leave_balance": 10.0,
        "jurisdiction": Jurisdiction.INDIA,
        "designation": "Software Engineer",
    }

    validated = validate_tool_result("get_employee_data", employee)
    projected = minimize_tool_result("get_employee_data", validated, authorization)

    assert projected == {"employee_name": "Neha Iyer", "annual_salary": 840000.0}


def test_policy_question_gets_no_employee_capability():
    allowed = minimum_tools_for_question(
        "What is the annual leave carry-over limit?"
    )

    assert allowed == frozenset({"lookup_annual_leave_policy"})
    with pytest.raises(PermissionError):
        validate_tool_call(
            "get_employee_data",
            {"employee_id": "003"},
            _authorization("What is the annual leave carry-over limit?"),
        )


def test_salary_question_does_not_get_policy_capability():
    assert minimum_tools_for_question("What is Neha Iyer's annual salary?") == frozenset(
        {"get_employee_data"}
    )


def test_capability_sets_match_question_types():
    assert minimum_tools_for_question("Which employees work in Engineering?") == frozenset(
        {"get_department_employees"}
    )
    assert minimum_tools_for_question("Which employees report to Arun Kumar?") == frozenset(
        {"get_employees_by_manager"}
    )
    assert minimum_tools_for_question(
        "For employee 005, give the full annual leave disposition."
    ) == frozenset(
        {
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        }
    )
    assert minimum_tools_for_question(
        "Can Priya Nair carry forward her remaining annual leave?"
    ) == frozenset(
        {
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        }
    )


def test_final_answer_rejects_calculation_contradiction():
    authorization = _authorization("For employee 005, give the full annual leave disposition.")
    authoritative = {
        "carryover_days": 10.0,
        "encashable_days": 5.0,
        "lapsed_days": 10.0,
    }

    checked = validate_final_answer(
        "For employee 005, give the full annual leave disposition.",
        "20 days can be carried over, 5 days can be encashed, and 10 days lapse.",
        authorization=authorization,
        executed_tools=[
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        ],
        authoritative_calculation=authoritative,
    )

    assert checked["safe"] is False
    assert "calculation_answer_mismatch" in checked["reasons"]