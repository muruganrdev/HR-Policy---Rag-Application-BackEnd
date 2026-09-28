"""Initialize the synthetic HR employee database with an expanded schema.

Run this script directly to (re)create data/employee.db:

    python data/init_db.py

The database is the single source of truth for employee-specific facts.
HR policy rules remain in ChromaDB / the policy PDF documents.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
DATABASE_PATH = DATA_DIR / "employee.db"

# ---------------------------------------------------------------------------
# Schema — 17 meaningful HR columns
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    employee_id        TEXT PRIMARY KEY,
    employee_name      TEXT    NOT NULL,
    email              TEXT    NOT NULL,
    phone              TEXT    NOT NULL,
    department         TEXT    NOT NULL,
    designation        TEXT    NOT NULL,
    employment_type    TEXT    NOT NULL CHECK (employment_type IN ('Full-Time', 'Part-Time', 'Contract')),
    employment_status  TEXT    NOT NULL CHECK (employment_status IN ('Active', 'On Leave', 'Resigned', 'Terminated')),
    date_of_joining    TEXT    NOT NULL,
    tenure_years       REAL    NOT NULL CHECK (tenure_years >= 0),
    manager_name       TEXT    NOT NULL,
    location           TEXT    NOT NULL,
    jurisdiction       TEXT    NOT NULL,
    leave_balance      REAL    NOT NULL CHECK (leave_balance >= 0),
    sick_leave_balance REAL    NOT NULL CHECK (sick_leave_balance >= 0),
    annual_salary      REAL    NOT NULL CHECK (annual_salary > 0),
    work_mode          TEXT    NOT NULL CHECK (work_mode IN ('On-Site', 'Hybrid', 'Remote'))
)
"""

# ---------------------------------------------------------------------------
# Synthetic employee records — IDs: 001 … 006
# Existing leave_balance and tenure_years values are preserved exactly.
# ---------------------------------------------------------------------------

SYNTHETIC_EMPLOYEES = [
    # (id, name, email, phone, dept, designation, emp_type, emp_status,
    #  date_of_joining, tenure_years, manager, location, jurisdiction,
    #  leave_balance, sick_leave_balance, annual_salary, work_mode)
    (
        "001", "Asha Rao",
        "asha.rao@acmecorp.in", "+91-98450-11001",
        "Human Resources", "HR Executive",
        "Full-Time", "Active",
        "2023-10-01", 0.25,
        "Sunita Pillai", "Bangalore", "INDIA",
        2.0, 10.0, 480000.0, "On-Site",
    ),
    (
        "002", "Vikram Shah",
        "vikram.shah@acmecorp.in", "+91-99300-22002",
        "Finance", "Finance Analyst",
        "Full-Time", "Active",
        "2023-07-01", 0.50,
        "Ramesh Gupta", "Mumbai", "INDIA",
        4.0, 12.0, 600000.0, "Hybrid",
    ),
    (
        "003", "Neha Iyer",
        "neha.iyer@acmecorp.in", "+91-98701-33003",
        "Engineering", "Software Engineer",
        "Full-Time", "Active",
        "2022-04-01", 1.50,
        "Arun Kumar", "Hyderabad", "INDIA",
        10.0, 12.0, 840000.0, "Hybrid",
    ),
    (
        "004", "Arjun Menon",
        "arjun.menon@acmecorp.in", "+91-97890-44004",
        "Engineering", "Senior Software Engineer",
        "Full-Time", "Active",
        "2021-01-01", 3.00,
        "Arun Kumar", "Bangalore", "INDIA",
        12.0, 12.0, 1200000.0, "Hybrid",
    ),
    (
        "005", "Priya Nair",
        "priya.nair@acmecorp.in", "+91-96780-55005",
        "Product", "Product Manager",
        "Full-Time", "Active",
        "2017-04-01", 6.50,
        "Deepak Sharma", "Bangalore", "INDIA",
        20.0, 12.0, 1800000.0, "Remote",
    ),
    (
        "006", "Rahul Das",
        "rahul.das@acmecorp.in", "+91-95670-66006",
        "Sales", "Sales Lead",
        "Full-Time", "Active",
        "2015-10-01", 8.00,
        "Preethi Nanda", "Chennai", "INDIA",
        5.0, 8.0, 1440000.0, "On-Site",
    ),
]


INSERT_SQL = """
INSERT INTO employees (
    employee_id, employee_name, email, phone,
    department, designation, employment_type, employment_status,
    date_of_joining, tenure_years, manager_name, location, jurisdiction,
    leave_balance, sick_leave_balance, annual_salary, work_mode
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(employee_id) DO UPDATE SET
    employee_name      = excluded.employee_name,
    email              = excluded.email,
    phone              = excluded.phone,
    department         = excluded.department,
    designation        = excluded.designation,
    employment_type    = excluded.employment_type,
    employment_status  = excluded.employment_status,
    date_of_joining    = excluded.date_of_joining,
    tenure_years       = excluded.tenure_years,
    manager_name       = excluded.manager_name,
    location           = excluded.location,
    jurisdiction       = excluded.jurisdiction,
    leave_balance      = excluded.leave_balance,
    sick_leave_balance = excluded.sick_leave_balance,
    annual_salary      = excluded.annual_salary,
    work_mode          = excluded.work_mode
"""


def initialize_database(database_path: Path = DATABASE_PATH) -> None:
    """Create the employee table and insert synthetic records idempotently."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(SCHEMA)
        connection.executemany(INSERT_SQL, SYNTHETIC_EMPLOYEES)
        connection.commit()


if __name__ == "__main__":
    initialize_database()
    print(f"Initialized {DATABASE_PATH} with {len(SYNTHETIC_EMPLOYEES)} employees.")
    # Quick inspection printout
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT employee_id, employee_name, department, designation, leave_balance "
            "FROM employees ORDER BY employee_id"
        ).fetchall()
        print(f"\n{'ID':<6} {'Name':<18} {'Department':<18} {'Designation':<30} {'Leave':>6}")
        print("-" * 82)
        for r in rows:
            print(f"{r['employee_id']:<6} {r['employee_name']:<18} {r['department']:<18} {r['designation']:<30} {r['leave_balance']:>6.1f}")
