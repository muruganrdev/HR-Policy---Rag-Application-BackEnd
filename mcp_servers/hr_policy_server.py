from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tools import (
    Jurisdiction,
    get_department_employees,
    get_employee_data,
    get_employees_by_manager,
    lookup_annual_leave_policy,
)
from mcp_servers._mcp_server import MCPJsonServer


def _lookup_annual_leave_policy(jurisdiction: str) -> dict[str, Any]:
    return lookup_annual_leave_policy(Jurisdiction(jurisdiction))


def _read_annual_leave_resource() -> str:
    result = _lookup_annual_leave_policy("INDIA")
    return "\n\n".join(
        f"Source: {item['source']} (chunk {item['chunk_index']})\n{item['content']}"
        for item in result["results"]
    )


TOOLS: dict[str, dict[str, Any]] = {
    "get_employee_data": {
        "name": "get_employee_data",
        "description": "Fetch one employee record by ID or name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": ["string", "null"]},
                "employee_name": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "func": get_employee_data,
    },
    "get_department_employees": {
        "name": "get_department_employees",
        "description": "List employees in a department.",
        "inputSchema": {
            "type": "object",
            "properties": {"department_name": {"type": "string"}},
            "required": ["department_name"],
            "additionalProperties": False,
        },
        "func": get_department_employees,
    },
    "get_employees_by_manager": {
        "name": "get_employees_by_manager",
        "description": "List the direct reports to a manager.",
        "inputSchema": {
            "type": "object",
            "properties": {"manager_name": {"type": "string"}},
            "required": ["manager_name"],
            "additionalProperties": False,
        },
        "func": get_employees_by_manager,
    },
    "lookup_annual_leave_policy": {
        "name": "lookup_annual_leave_policy",
        "description": "Fetch annual leave policy evidence for INDIA.",
        "inputSchema": {
            "type": "object",
            "properties": {"jurisdiction": {"type": "string"}},
            "required": ["jurisdiction"],
            "additionalProperties": False,
        },
        "func": _lookup_annual_leave_policy,
    },
}

RESOURCES = {
    "hr://policy/annual-leave": {
        "uri": "hr://policy/annual-leave",
        "name": "annual-leave-policy-india",
        "title": "India annual leave policy",
        "description": "Read-only annual-leave policy passages retrieved from the existing HR policy collection.",
        "mimeType": "text/plain",
        "read": _read_annual_leave_resource,
    }
}


if __name__ == "__main__":
    MCPJsonServer("hr_policy_server", TOOLS, resources=RESOURCES).run()
