from __future__ import annotations

import sqlite3

import pytest

from app.tools import (
    DATABASE_PATH,
    AmbiguousEmployeeError,
    EmployeeNotFoundError,
    Jurisdiction,
    calculate_annual_leave_disposition,
    get_department_employees,
    get_employee_data,
    get_employees_by_manager,
    lookup_annual_leave_policy,
)


@pytest.fixture(scope="module", autouse=True)
def require_employee_database():
    if not DATABASE_PATH.exists():
        pytest.fail("Run python data/init_db.py before the tool tests.")


# ---------------------------------------------------------------------------
# get_employee_data — by ID
# ---------------------------------------------------------------------------

def test_known_employee_by_id_returns_full_record():
    record = get_employee_data(employee_id="003")

    assert record["employee_id"] == "003"
    assert record["employee_name"] == "Neha Iyer"
    assert record["tenure_years"] == 1.5
    assert record["jurisdiction"] is Jurisdiction.INDIA
    assert record["leave_balance"] == 10.0
    assert record["email"] == "neha.iyer@acmecorp.in"
    assert record["department"] == "Engineering"
    assert record["designation"] == "Software Engineer"
    assert record["employment_type"] == "Full-Time"


# ---------------------------------------------------------------------------
# get_employee_data — by name
# ---------------------------------------------------------------------------

def test_known_employee_by_name_returns_same_record():
    record = get_employee_data(employee_name="Priya Nair")

    assert record["employee_id"] == "005"
    assert record["employee_name"] == "Priya Nair"
    assert record["leave_balance"] == 20.0
    assert record["tenure_years"] == 6.5
    assert record["department"] == "Product"


def test_name_lookup_is_case_insensitive():
    record = get_employee_data(employee_name="priya nair")
    assert record["employee_id"] == "005"

    record2 = get_employee_data(employee_name="PRIYA NAIR")
    assert record2["employee_id"] == "005"


# ---------------------------------------------------------------------------
# get_employee_data — error cases
# ---------------------------------------------------------------------------

def test_unknown_employee_by_id_raises():
    with pytest.raises(EmployeeNotFoundError):
        get_employee_data(employee_id="999")


def test_unknown_employee_by_name_raises():
    with pytest.raises(EmployeeNotFoundError):
        get_employee_data(employee_name="Unknown Person")


def test_missing_both_identifiers_raises():
    with pytest.raises(ValueError, match="at least one"):
        get_employee_data()


# ---------------------------------------------------------------------------
# get_department_employees
# ---------------------------------------------------------------------------

def test_department_employees_returns_list():
    result = get_department_employees("Engineering")

    assert result["department"] == "Engineering"
    assert result["count"] == 2
    names = {emp["employee_name"] for emp in result["employees"]}
    assert names == {"Neha Iyer", "Arjun Menon"}


def test_department_employees_empty_for_unknown():
    result = get_department_employees("Unknown Department")
    assert result["count"] == 0
    assert result["employees"] == []


def test_department_employees_case_insensitive():
    result = get_department_employees("engineering")
    assert result["count"] == 2


# ---------------------------------------------------------------------------
# get_employees_by_manager
# ---------------------------------------------------------------------------

def test_employees_by_manager():
    result = get_employees_by_manager("Arun Kumar")

    assert result["manager_name"] == "Arun Kumar"
    assert result["count"] == 2
    names = {emp["employee_name"] for emp in result["employees"]}
    assert names == {"Neha Iyer", "Arjun Menon"}


# ---------------------------------------------------------------------------
# Jurisdiction
# ---------------------------------------------------------------------------

def test_jurisdiction_enum_accepts_only_supported_value():
    assert Jurisdiction("INDIA") is Jurisdiction.INDIA
    with pytest.raises(ValueError):
        Jurisdiction("AUSTRALIA")


# ---------------------------------------------------------------------------
# lookup_annual_leave_policy
# ---------------------------------------------------------------------------

def test_policy_lookup_returns_results_without_answer_generation(monkeypatch):
    calls = []

    def fake_search(query):
        calls.append(query)
        return [{"source": "leave_policy.pdf", "chunk_index": 2, "content": "10 days carry over; 5 days encash."}]

    import app.search

    monkeypatch.setattr(app.search, "search", fake_search)
    result = lookup_annual_leave_policy(Jurisdiction.INDIA)

    assert calls == ["annual leave carry over encashment unused leave balance"]
    assert result["policy_area"] == "annual_leave_balance"
    assert result["results"][0]["source"] == "leave_policy.pdf"
    assert "answer" not in result


def test_policy_lookup_rejects_untyped_jurisdiction():
    with pytest.raises(TypeError):
        lookup_annual_leave_policy("INDIA")


# ---------------------------------------------------------------------------
# calculate_annual_leave_disposition
# ---------------------------------------------------------------------------

def test_leave_disposition_calculates_correctly():
    result = calculate_annual_leave_disposition(12.0, 10.0, 5.0)

    assert result == {
        "carryover_days": 10.0,
        "encashable_days": 5.0,
        "lapsed_days": 2.0,
    }
    assert set(result) == {"carryover_days", "encashable_days", "lapsed_days"}


# ---------------------------------------------------------------------------
# Expanded schema verification
# ---------------------------------------------------------------------------

def test_employee_table_has_more_than_10_columns():
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.execute("PRAGMA table_info(employees)")
        columns = [row[1] for row in cursor.fetchall()]
        assert len(columns) > 10, f"Expected >10 columns, got {len(columns)}: {columns}"


def test_all_six_employees_present():
    with sqlite3.connect(DATABASE_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        assert count == 6


def test_tools_do_not_modify_database():
    before = DATABASE_PATH.stat().st_mtime_ns
    record = get_employee_data(employee_id="001")
    after = DATABASE_PATH.stat().st_mtime_ns

    assert record["jurisdiction"] is Jurisdiction.INDIA
    assert before == after
    assert not hasattr(record, "answer")
