"""Focused, deterministic tools for the HR employee Agent.

Each tool performs exactly one responsibility:
- Employee tools   → employee facts from SQLite
- Policy tools     → policy evidence from ChromaDB / HR PDFs
- Calculation tools → deterministic numeric calculations

No tool generates prose, calls Ollama, or crosses these boundaries.
"""

from __future__ import annotations

import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any

DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "employee.db"


# ---------------------------------------------------------------------------
# Jurisdiction enum
# ---------------------------------------------------------------------------

class Jurisdiction(str, Enum):
    """Jurisdictions supported by the employee corpus and policy documents."""

    INDIA = "INDIA"


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class EmployeeNotFoundError(LookupError):
    """Raised when no employee record matches the supplied identifier."""


class AmbiguousEmployeeError(LookupError):
    """Raised when multiple employee records match a name query."""


# ---------------------------------------------------------------------------
# Internal DB helper
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict with typed values."""
    d = dict(row)
    d["tenure_years"] = float(d["tenure_years"])
    d["leave_balance"] = float(d["leave_balance"])
    d["sick_leave_balance"] = float(d["sick_leave_balance"])
    d["annual_salary"] = float(d["annual_salary"])
    try:
        d["jurisdiction"] = Jurisdiction(d["jurisdiction"])
    except ValueError as error:
        raise ValueError(
            f"Unsupported stored jurisdiction: {d['jurisdiction']}"
        ) from error
    return d


# ===========================================================================
# EMPLOYEE TOOLS
# ===========================================================================

# Tool - 1
def get_employee_data(
    employee_id: str | None = None,
    employee_name: str | None = None,
) -> dict[str, Any]:
    """Retrieve a single employee record by ID or by name.

    Accepts either ``employee_id`` OR ``employee_name`` (not both required).
    Returns a full employee record with all stored fields.

    Raises:
        ValueError           – if neither identifier is supplied.
        EmployeeNotFoundError – if no record matches the identifier.
        AmbiguousEmployeeError – if multiple records match the name.
    """
    has_id = employee_id is not None and str(employee_id).strip()
    has_name = employee_name is not None and str(employee_name).strip()

    if not has_id and not has_name:
        raise ValueError(
            "Provide at least one of employee_id or employee_name."
        )

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        if has_id:
            row = connection.execute(
                """
                SELECT employee_id, employee_name, email, phone,
                       department, designation, employment_type, employment_status,
                       date_of_joining, tenure_years, manager_name, location,
                       jurisdiction, leave_balance, sick_leave_balance,
                       annual_salary, work_mode
                FROM employees
                WHERE employee_id = ?
                """,
                (str(employee_id).strip(),),
            ).fetchone()
            if row is None:
                raise EmployeeNotFoundError(
                    f"No employee found with ID: {employee_id}"
                )
            return _row_to_dict(row)

        # Name lookup — case-insensitive
        rows = connection.execute(
            """
            SELECT employee_id, employee_name, email, phone,
                   department, designation, employment_type, employment_status,
                   date_of_joining, tenure_years, manager_name, location,
                   jurisdiction, leave_balance, sick_leave_balance,
                   annual_salary, work_mode
            FROM employees
            WHERE LOWER(employee_name) = LOWER(?)
            """,
            (str(employee_name).strip(),),
        ).fetchall()

        if not rows:
            raise EmployeeNotFoundError(
                f"No employee found with name: {employee_name}"
            )
        if len(rows) > 1:
            ids = [r["employee_id"] for r in rows]
            raise AmbiguousEmployeeError(
                f"Multiple employees match '{employee_name}': {ids}. "
                "Supply employee_id to disambiguate."
            )
        return _row_to_dict(rows[0])

# Tool - 2
def get_department_employees(department_name: str) -> dict[str, Any]:
    """Return a list of employees in a given department.

    Input:  ``department_name`` — department name string (case-insensitive).
    Output: dict with ``department``, ``count``, and ``employees`` list.
    """
    if not department_name or not str(department_name).strip():
        raise ValueError("department_name must be a non-empty string.")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT employee_id, employee_name, designation, employment_status,
                   manager_name, work_mode
            FROM employees
            WHERE LOWER(department) = LOWER(?)
            ORDER BY employee_id
            """,
            (str(department_name).strip(),),
        ).fetchall()

    employees = [dict(r) for r in rows]
    return {
        "department": department_name,
        "count": len(employees),
        "employees": employees,
    }

# Tool - 3
def get_employees_by_manager(manager_name: str) -> dict[str, Any]:
    """Return employees whose manager_name matches the supplied name.

    Input:  ``manager_name`` — manager's full name (case-insensitive).
    Output: dict with ``manager_name``, ``count``, and ``employees`` list.
    """
    if not manager_name or not str(manager_name).strip():
        raise ValueError("manager_name must be a non-empty string.")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT employee_id, employee_name, department, designation
            FROM employees
            WHERE LOWER(manager_name) = LOWER(?)
            ORDER BY employee_id
            """,
            (str(manager_name).strip(),),
        ).fetchall()

    employees = [dict(r) for r in rows]
    return {
        "manager_name": manager_name,
        "count": len(employees),
        "employees": employees,
    }


# ===========================================================================
# POLICY TOOLS
# ===========================================================================

# Tool - 4
def lookup_annual_leave_policy(jurisdiction: Jurisdiction) -> dict[str, Any]:
    """Retrieve annual-leave carry-over and encashment policy evidence.

    Input:  ``jurisdiction`` — a typed Jurisdiction enum value.
    Output: structured policy chunks retrieved from the HR policy PDF index.
    Does NOT retrieve employee data, calculate leave, or generate text.
    """
    if not isinstance(jurisdiction, Jurisdiction):
        raise TypeError("jurisdiction must be a Jurisdiction enum value")
    if jurisdiction is not Jurisdiction.INDIA:
        raise ValueError(f"Unsupported jurisdiction: {jurisdiction.value}")

    from app.search import search

    results = search("annual leave carry over encashment unused leave balance")
    return {
        "jurisdiction": jurisdiction,
        "policy_area": "annual_leave_balance",
        "results": results,
    }


# ===========================================================================
# CALCULATION TOOLS
# ===========================================================================
# Tool - 5
def calculate_annual_leave_disposition(
    leave_balance: float,
    carry_over_limit: float,
    encashment_limit: float,
) -> dict[str, float]:
    """Classify one leave balance under supplied policy limits.

    Inputs:  leave_balance, carry_over_limit, encashment_limit (all numeric).
    Output:  carryover_days, encashable_days, lapsed_days.
    Does NOT retrieve employees or policies, call an LLM, or generate prose.
    """
    values = (leave_balance, carry_over_limit, encashment_limit)
    if any(value < 0 for value in values):
        raise ValueError("Leave balance and policy limits must be non-negative.")

    return {
        "carryover_days": min(leave_balance, carry_over_limit),
        "encashable_days": min(leave_balance, encashment_limit),
        "lapsed_days": max(leave_balance - carry_over_limit, 0.0),
    }
