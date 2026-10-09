import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import api
from app.api import RoleAccessPrincipal, get_authenticated_role_access_principal
from app.tools import DATABASE_PATH


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def isolated_employee_database(tmp_path, monkeypatch):
    test_database = tmp_path / "employee.db"
    source = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
    destination = sqlite3.connect(test_database)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    monkeypatch.setattr(api, "DATABASE_PATH", str(test_database))
    monkeypatch.setitem(globals(), "DATABASE_PATH", str(test_database))


@pytest.fixture
def super_admin_client(client):
    app.dependency_overrides[get_authenticated_role_access_principal] = lambda: RoleAccessPrincipal(
        role="Super Admin", employee_id="001"
    )
    yield client
    app.dependency_overrides.pop(get_authenticated_role_access_principal, None)


@pytest.fixture
def employee_snapshot():
    with sqlite3.connect(DATABASE_PATH) as connection:
        rows = connection.execute(
            "SELECT employee_id, employee_name, department, designation, manager_name FROM employees ORDER BY employee_id"
        ).fetchall()
    yield rows
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("DELETE FROM employees WHERE employee_id IN ('995', '996', '997', '998', '999')")


@pytest.fixture
def role_context():
    return {"role": "Super Admin", "employee_id": "001"}


def _create_employee(payload):
    return {
        "employee_id": payload["employee_id"],
        "employee_name": payload["employee_name"],
        "email": payload["email"],
        "phone": payload["phone"],
        "department": payload["department"],
        "designation": payload["designation"],
        "employment_type": payload["employment_type"],
        "employment_status": payload["employment_status"],
        "date_of_joining": payload["date_of_joining"],
        "tenure_years": payload["tenure_years"],
        "manager_name": payload["manager_name"],
        "location": payload["location"],
        "jurisdiction": payload["jurisdiction"],
        "leave_balance": payload["leave_balance"],
        "sick_leave_balance": payload["sick_leave_balance"],
        "annual_salary": payload["annual_salary"],
        "work_mode": payload["work_mode"],
    }


def test_super_admin_can_list_employees(super_admin_client):
    response = super_admin_client.get(
        "/role-access/employees",
        params={"role": "Super Admin", "employee_id": "001"},
    )

    assert response.status_code == 200
    records = response.json()["employees"]
    assert any(record["employee_id"] == "001" for record in records)
    assert response.json()["scope"] == "all employees"
    assert response.json()["permissions"] == {
        "view": True,
        "create": True,
        "update": True,
        "delete": True,
    }


def test_super_admin_can_create_employee(super_admin_client):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("DELETE FROM employees WHERE employee_id IN ('995', '996', '997', '998', '999')")
        connection.commit()

    payload = _create_employee(
        {
            "employee_id": "995",
            "employee_name": "Test Employee",
            "email": "test.employee@acmecorp.in",
            "phone": "+91-90000-00097",
            "department": "Engineering",
            "designation": "Test Engineer",
            "employment_type": "Full-Time",
            "employment_status": "Active",
            "date_of_joining": "2026-01-01",
            "tenure_years": 1.0,
            "manager_name": "Arun Kumar",
            "location": "Bangalore",
            "jurisdiction": "INDIA",
            "leave_balance": 10.0,
            "sick_leave_balance": 5.0,
            "annual_salary": 600000.0,
            "work_mode": "Hybrid",
        }
    )

    response = super_admin_client.post(
        "/role-access/employees",
        json={"role": "Super Admin", "employee_id": "001", **payload},
    )

    assert response.status_code == 201
    assert response.json()["employee"]["employee_id"] == "995"


def test_super_admin_can_update_employee(super_admin_client):
    super_admin_client.post(
        "/role-access/employees",
        json={
            "role": "Super Admin",
            "employee_id": "001",
            **_create_employee({
                "employee_id": "998",
                "employee_name": "Update Test Employee",
                "email": "update.employee@acmecorp.in",
                "phone": "+91-90000-00098",
                "department": "Engineering",
                "designation": "Senior Test Engineer",
                "employment_type": "Full-Time",
                "employment_status": "Active",
                "date_of_joining": "2025-01-01",
                "tenure_years": 2.0,
                "manager_name": "Arun Kumar",
                "location": "Bangalore",
                "jurisdiction": "INDIA",
                "leave_balance": 12.0,
                "sick_leave_balance": 4.0,
                "annual_salary": 800000.0,
                "work_mode": "Remote",
            }),
        },
    )

    response = super_admin_client.put(
        "/role-access/employees/998",
        json={
            "role": "Super Admin",
            "employee_id": "001",
            "employee_name": "Updated Test Employee",
            "designation": "Test Lead",
            "department": "Engineering",
        },
    )

    assert response.status_code == 200
    assert response.json()["employee"]["designation"] == "Test Lead"


def test_super_admin_can_delete_employee(super_admin_client):
    super_admin_client.post(
        "/role-access/employees",
        json={
            "role": "Super Admin",
            "employee_id": "001",
            **_create_employee({
                "employee_id": "999",
                "employee_name": "Delete Test Employee",
                "email": "delete.employee@acmecorp.in",
                "phone": "+91-90000-00099",
                "department": "Engineering",
                "designation": "Test Engineer",
                "employment_type": "Full-Time",
                "employment_status": "Active",
                "date_of_joining": "2024-01-01",
                "tenure_years": 3.0,
                "manager_name": "Arun Kumar",
                "location": "Bangalore",
                "jurisdiction": "INDIA",
                "leave_balance": 8.0,
                "sick_leave_balance": 3.0,
                "annual_salary": 650000.0,
                "work_mode": "Hybrid",
            }),
        },
    )

    response = super_admin_client.request(
        "DELETE",
        "/role-access/employees/999",
        json={"role": "Super Admin", "employee_id": "001"},
    )

    assert response.status_code == 200
    assert response.json()["deleted_employee_id"] == "999"


def test_manager_can_view_allowed_employee_data(client):
    response = client.get(
        "/role-access/employees",
        params={"role": "Manager", "employee_id": "004"},
    )

    assert response.status_code == 200
    records = response.json()["employees"]
    assert all(record["manager_name"] == "Arun Kumar" for record in records)
    assert response.json()["scope"] == "team / supported view"
    assert response.json()["permissions"] == {
        "view": True,
        "create": False,
        "update": False,
        "delete": False,
    }


def test_demo_manager_options_are_limited_to_supported_names(client):
    response = client.get("/role-access/managers")

    assert response.status_code == 200
    assert response.json()["managers"] == [
        {"manager_name": "Arun Kumar", "employee_id": "003"},
        {"manager_name": "Deepak Sharma", "employee_id": "005"},
    ]


def test_employee_demo_options_return_only_ids_and_names(client):
    response = client.get(
        "/role-access/employee-options",
        params={"role": "Employee", "employee_id": "001"},
    )

    assert response.status_code == 200
    assert response.json()["employees"] == [
        {"employee_id": "001", "employee_name": "Asha Rao"},
        {"employee_id": "002", "employee_name": "Vikram Shah"},
        {"employee_id": "003", "employee_name": "Neha Iyer"},
        {"employee_id": "004", "employee_name": "Arjun Menon"},
        {"employee_id": "005", "employee_name": "Priya Nair"},
        {"employee_id": "006", "employee_name": "Rahul Das"},
    ]
    assert set(response.json()["employees"][0]) == {"employee_id", "employee_name"}


def test_manager_cannot_use_employee_demo_options(client):
    response = client.get(
        "/role-access/employee-options",
        params={"role": "Manager", "employee_id": "003"},
    )

    assert response.status_code == 403


def test_manager_can_view_team_member_and_only_team_names(client):
    response = client.get(
        "/role-access/employees/004",
        params={"role": "Manager", "employee_id": "003"},
    )

    assert response.status_code == 200
    assert response.json()["employee"]["employee_id"] == "004"

    list_response = client.get(
        "/role-access/employees",
        params={"role": "Manager", "employee_id": "003"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["employee_names"] == ["Neha Iyer", "Arjun Menon"]


def test_manager_cannot_view_outside_team_member(client):
    response = client.get(
        "/role-access/employees/005",
        params={"role": "Manager", "employee_id": "003"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied: employee is outside your authorized team."}


def test_manager_for_unlisted_reporting_line_is_rejected(client):
    response = client.get(
        "/role-access/employees",
        params={"role": "Manager", "employee_id": "006"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied: unsupported demo manager."}


def test_manager_cannot_create(client):
    response = client.post(
        "/role-access/employees",
        json={
            "role": "Manager",
            "employee_id": "004",
            "employee_name": "Blocked Employee",
            "email": "blocked@acmecorp.in",
            "phone": "+91-90000-00000",
            "department": "Engineering",
            "designation": "Blocked Engineer",
            "employment_type": "Full-Time",
            "employment_status": "Active",
            "date_of_joining": "2026-01-01",
            "tenure_years": 1.0,
            "manager_name": "Arun Kumar",
            "location": "Bangalore",
            "jurisdiction": "INDIA",
            "leave_balance": 10.0,
            "sick_leave_balance": 5.0,
            "annual_salary": 600000.0,
            "work_mode": "Hybrid",
        },
    )

    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_manager_cannot_update(client):
    response = client.put(
        "/role-access/employees/003",
        json={
            "role": "Manager",
            "employee_id": "004",
            "employee_name": "Blocked Update",
        },
    )

    assert response.status_code == 403


def test_manager_cannot_delete(client):
    response = client.request(
        "DELETE",
        "/role-access/employees/003",
        json={"role": "Manager", "employee_id": "004"},
    )

    assert response.status_code == 403


def test_employee_can_view_own_demo_identity(client):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("DELETE FROM employees WHERE employee_id IN ('995', '996', '997', '998', '999')")
        connection.commit()

    response = client.get(
        "/role-access/employees",
        params={"role": "Employee", "employee_id": "001"},
    )

    assert response.status_code == 200
    assert [record["employee_id"] for record in response.json()["employees"]] == ["001"]
    assert response.json()["employee_names"] == ["Asha Rao"]
    assert response.json()["scope"] == "own demo identity"
    assert response.json()["permissions"] == {
        "view": True,
        "create": False,
        "update": False,
        "delete": False,
    }


def test_employee_cannot_view_another_employee(client):
    response = client.get(
        "/role-access/employees/002",
        params={"role": "Employee", "employee_id": "001"},
    )

    assert response.status_code == 403


def test_employee_cannot_list_other_employee_names(client):
    response = client.get(
        "/role-access/employees",
        params={"role": "Employee", "employee_id": "001"},
    )

    assert response.status_code == 200
    assert response.json()["employee_names"] == ["Asha Rao"]
    assert "Priya Nair" not in response.json()["employee_names"]


def test_employee_cannot_create(client):
    response = client.post(
        "/role-access/employees",
        json={
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Blocked Employee",
            "email": "blocked@acmecorp.in",
            "phone": "+91-90000-00000",
            "department": "Engineering",
            "designation": "Blocked Engineer",
            "employment_type": "Full-Time",
            "employment_status": "Active",
            "date_of_joining": "2026-01-01",
            "tenure_years": 1.0,
            "manager_name": "Arun Kumar",
            "location": "Bangalore",
            "jurisdiction": "INDIA",
            "leave_balance": 10.0,
            "sick_leave_balance": 5.0,
            "annual_salary": 600000.0,
            "work_mode": "Hybrid",
        },
    )

    assert response.status_code == 403


def test_employee_cannot_update(client):
    response = client.put(
        "/role-access/employees/001",
        json={
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Blocked Update",
        },
    )

    assert response.status_code == 403


def test_employee_cannot_delete(client):
    response = client.request(
        "DELETE",
        "/role-access/employees/001",
        json={"role": "Employee", "employee_id": "001"},
    )

    assert response.status_code == 403


def test_unknown_employee_returns_404(client):
    response = client.get(
        "/role-access/employees",
        params={"role": "Employee", "employee_id": "999"},
    )

    assert response.status_code == 404


def test_unauthorized_requests_return_403(client):
    response = client.put(
        "/role-access/employees/001",
        json={"role": "Employee", "employee_id": "999", "employee_name": "Attempt"},
    )

    assert response.status_code == 403


def test_super_admin_role_claim_without_trusted_principal_is_denied(client):
    response = client.get(
        "/role-access/employees",
        params={"role": "Super Admin", "employee_id": "001"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Super Admin access requires a trusted authenticated identity."
    }


def test_super_admin_mutations_require_trusted_principal(client):
    payload = {
        "role": "Super Admin",
        "employee_id": "995",
        "employee_name": "Authorization Probe",
        "email": "authorization.probe@example.invalid",
        "phone": "0000000000",
        "department": "Test",
        "designation": "Test",
        "employment_type": "Full-Time",
        "employment_status": "Active",
        "date_of_joining": "2026-10-09",
        "tenure_years": 0,
        "manager_name": "Arun Kumar",
        "location": "Test",
        "jurisdiction": "INDIA",
        "leave_balance": 0,
        "sick_leave_balance": 0,
        "annual_salary": 1,
        "work_mode": "Remote",
    }

    response = client.post("/role-access/employees", json=payload)
    assert response.status_code == 403

    response = client.put(
        "/role-access/employees/001",
        json={"role": "Super Admin", "employee_id": "001", "employee_name": "Spoofed"},
    )
    assert response.status_code == 403

    response = client.request(
        "DELETE",
        "/role-access/employees/001",
        json={"role": "Super Admin", "employee_id": "001"},
    )
    assert response.status_code == 403

    with sqlite3.connect(DATABASE_PATH) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM employees WHERE employee_id = '995'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT employee_name FROM employees WHERE employee_id = '001'"
        ).fetchone()[0] == "Asha Rao"
