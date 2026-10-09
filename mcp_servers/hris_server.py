from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tools import get_department_employees, get_employee_data, get_employees_by_manager
from mcp_servers._mcp_server import MCPJsonServer


def get_employee_snapshot(employee_name: str) -> dict[str, Any]:
    """Return a compact employee snapshot for HRIS chat queries.

    Use this tool when the question asks for an employee's identity, department,
    designation, annual_salary, leave_balance, or manager_name. Required
    argument: employee_name (a known employee name from the HRIS database).
    Returns: employee_id, employee_name, department, designation,
    annual_salary, leave_balance, and manager_name. Limitations: this tool
    only works for known employees; it cannot infer missing employee records and
    must not invent or guess a person's details.
    """
    record = get_employee_data(employee_name=employee_name)
    return {
        "employee_id": record["employee_id"],
        "employee_name": record["employee_name"],
        "department": record["department"],
        "designation": record["designation"],
        "annual_salary": record["annual_salary"],
        "leave_balance": record["leave_balance"],
        "manager_name": record["manager_name"],
    }


def get_employee_leave_balance(employee_name: str) -> dict[str, Any]:
    record = get_employee_data(employee_name=employee_name)
    return {
        "employee_id": record["employee_id"],
        "employee_name": record["employee_name"],
        "leave_balance": record["leave_balance"],
    }


def get_employee_grade_band(employee_name: str) -> dict[str, Any]:
    raise RuntimeError("Grade-band data source is not configured")


TOOLS: dict[str, dict[str, Any]] = {
    "hris_get_employee_snapshot": {
        "name": "hris_get_employee_snapshot",
        "description": (
            "Retrieve a compact employee snapshot for one known employee. Use this tool when the user asks for an employee's department, designation, annual_salary, leave_balance, or manager_name. Required argument: employee_name (a known employee name from the HRIS database). Returns employee_id, employee_name, department, designation, annual_salary, leave_balance, and manager_name. Limitation: this tool only works for known employees and must not invent or guess missing employee information."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"employee_name": {"type": "string"}},
            "required": ["employee_name"],
            "additionalProperties": False,
        },
        "func": get_employee_snapshot,
    },
    "hris_get_employee_leave_balance": {
        "name": "hris_get_employee_leave_balance",
        "description": (
            "Least-privilege tool for questions asking only for a known employee's annual leave balance. "
            "Prefer this tool over the full employee snapshot or general employee record for leave-balance-only requests. "
            "Returns only employee_id, employee_name, and leave_balance."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"employee_name": {"type": "string"}},
            "required": ["employee_name"],
            "additionalProperties": False,
        },
        "func": get_employee_leave_balance,
    },
    "hris_get_employee_grade_band": {
        "name": "hris_get_employee_grade_band",
        "description": "Protected HRIS grade-band capability; access is scope-controlled by the MCP gateway.",
        "inputSchema": {
            "type": "object",
            "properties": {"employee_name": {"type": "string"}},
            "required": ["employee_name"],
            "additionalProperties": False,
        },
        "func": get_employee_grade_band,
    },
    "hris_get_department_roster": {
        "name": "hris_get_department_roster",
        "description": "List the employees in a department for roster questions.",
        "inputSchema": {
            "type": "object",
            "properties": {"department_name": {"type": "string"}},
            "required": ["department_name"],
            "additionalProperties": False,
        },
        "func": lambda department_name: get_department_employees(department_name),
    },
    "hris_get_manager_team": {
        "name": "hris_get_manager_team",
        "description": "List direct reports under a manager.",
        "inputSchema": {
            "type": "object",
            "properties": {"manager_name": {"type": "string"}},
            "required": ["manager_name"],
            "additionalProperties": False,
        },
        "func": lambda manager_name: get_employees_by_manager(manager_name),
    },
}


def _employee_leave_summary_prompt(arguments: dict[str, Any]) -> dict[str, Any]:
    employee_name = arguments.get("employee_name", "the employee")
    if not isinstance(employee_name, str) or not employee_name.strip():
        raise ValueError("employee_name is required")
    return {
        "description": "Reusable host prompt for summarizing observed employee leave information.",
        "messages": [{
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Summarize the observed annual and sick leave information for {employee_name.strip()}. "
                    "Use only HRIS tool results supplied by the host. If a value is absent, say it is unavailable; do not infer it."
                ),
            },
        }],
    }


PROMPTS = {
    "employee_leave_summary": {
        "name": "employee_leave_summary",
        "description": "Reusable prompt template for a host to summarize an employee's leave balances.",
        "arguments": [{
            "name": "employee_name",
            "description": "Employee name to include in the host prompt.",
            "required": True,
        }],
        "get": _employee_leave_summary_prompt,
    }
}


if __name__ == "__main__":
    MCPJsonServer("hris_server", TOOLS, prompts=PROMPTS).run()
