"""HR Agent trajectory benchmark -- 10 official Task Set C cases.

Each case supplies:
  question                 - the question sent to run_agent
    expected_tool_sequences  - list of accepted ordered tool sequences
    expected_arguments       - expected values keyed by tool name
  expected_answer_contains - phrases every correct answer must contain
  class                    - question category label
"""

from __future__ import annotations

TRAJECTORY_DATASET = [
    {
        "id": "TQ01",
        "question": "What is Neha Iyer's annual salary?",
        "expected_tool_sequences": [["get_employee_data"]],
        "expected_arguments": {"get_employee_data": {"employee_name": "Neha Iyer"}},
        "expected_answer_contains": ["Neha Iyer", "840,000"],
        "class": "employee_only",
    },
    {
        "id": "TQ02",
        "question": "What is Rahul Das's annual leave balance?",
        "expected_tool_sequences": [["get_employee_data"]],
        "expected_arguments": {"get_employee_data": {"employee_name": "Rahul Das"}},
        "expected_answer_contains": ["Rahul Das", "5"],
        "class": "employee_only",
    },
    {
        "id": "TQ03",
        "question": "Which employees work in Engineering?",
        "expected_tool_sequences": [["get_department_employees"]],
        "expected_arguments": {"get_department_employees": {"department_name": "Engineering"}},
        "expected_answer_contains": ["Neha Iyer", "Arjun Menon"],
        "class": "department",
    },
    {
        "id": "TQ04",
        "question": "Which employees report to Arun Kumar?",
        "expected_tool_sequences": [["get_employees_by_manager"]],
        "expected_arguments": {"get_employees_by_manager": {"manager_name": "Arun Kumar"}},
        "expected_answer_contains": ["Neha Iyer", "Arjun Menon"],
        "class": "manager",
    },
    {
        "id": "TQ05",
        "question": "What is the annual leave carry-over limit under the policy?",
        "expected_tool_sequences": [["lookup_annual_leave_policy"]],
        "expected_arguments": {"lookup_annual_leave_policy": {"jurisdiction": "INDIA"}},
        "expected_answer_contains": ["10 days"],
        "class": "policy_only",
    },
    {
        "id": "TQ06",
        "question": "What is the maximum annual leave encashment allowed by policy?",
        "expected_tool_sequences": [["lookup_annual_leave_policy"]],
        "expected_arguments": {"lookup_annual_leave_policy": {"jurisdiction": "INDIA"}},
        "expected_answer_contains": ["5 days"],
        "class": "policy_only",
    },
    {
        "id": "TQ07",
        "question": "Compare Priya Nair's annual leave balance with the annual leave carry-over limit.",
        "expected_tool_sequences": [
            ["get_employee_data", "lookup_annual_leave_policy"],
            ["lookup_annual_leave_policy", "get_employee_data"],
        ],
        "expected_arguments": {
            "get_employee_data": {"employee_name": "Priya Nair"},
            "lookup_annual_leave_policy": {"jurisdiction": "INDIA"},
        },
        "expected_answer_contains": ["Priya Nair", "20", "10"],
        "class": "employee_and_policy",
    },
    {
        "id": "TQ08",
        "question": "For employee 005, give the full annual leave disposition.",
        "expected_tool_sequences": [[
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        ]],
        "expected_arguments": {
            "get_employee_data": {"employee_id": "005"},
            "lookup_annual_leave_policy": {"jurisdiction": "INDIA"},
            "calculate_annual_leave_disposition": {
                "leave_balance": 20.0,
                "carry_over_limit": 10.0,
                "encashment_limit": 5.0,
            },
        },
        "expected_answer_contains": [
            "10 days can be carried over",
            "5 days can be encashed",
            "10 days lapse",
        ],
        "class": "full_leave_disposition",
    },
    {
        "id": "TQ09",
        "question": "For employee 006, report the annual leave carry-over, encashment, and lapse amounts.",
        "expected_tool_sequences": [[
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        ]],
        "expected_arguments": {
            "get_employee_data": {"employee_id": "006"},
            "lookup_annual_leave_policy": {"jurisdiction": "INDIA"},
            "calculate_annual_leave_disposition": {
                "leave_balance": 5.0,
                "carry_over_limit": 10.0,
                "encashment_limit": 5.0,
            },
        },
        "expected_answer_contains": [
            "5 days can be carried over",
            "5 days can be encashed",
            "0 days lapse",
        ],
        "class": "full_leave_disposition",
    },
    {
        "id": "TQ10",
        "question": "For employee 004, what portion of the annual leave balance lapses?",
        "expected_tool_sequences": [[
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        ]],
        "expected_arguments": {
            "get_employee_data": {"employee_id": "004"},
            "lookup_annual_leave_policy": {"jurisdiction": "INDIA"},
            "calculate_annual_leave_disposition": {
                "leave_balance": 12.0,
                "carry_over_limit": 10.0,
                "encashment_limit": 5.0,
            },
        },
        "expected_answer_contains": ["2 days lapse"],
        "class": "dependent_leave_calculation",
    },
]

assert len(TRAJECTORY_DATASET) == 10

