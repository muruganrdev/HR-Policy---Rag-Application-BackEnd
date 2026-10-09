from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP

from app.tools import get_employee_data

mcp = FastMCP("hr-policy-fastmcp-demo")


@mcp.tool
def get_employee_leave_summary(employee_name: str) -> dict[str, Any]:
    """Return an employee's verified annual and sick leave balances."""
    record = get_employee_data(employee_name=employee_name)
    return {
        "employee_id": record["employee_id"],
        "employee_name": record["employee_name"],
        "leave_balance": record["leave_balance"],
        "sick_leave_balance": record["sick_leave_balance"],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
