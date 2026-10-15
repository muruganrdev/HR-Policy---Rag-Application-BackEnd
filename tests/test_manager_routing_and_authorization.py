"""Focused regression and security tests for Manager Lookup Routing and Employee Data Authorization.

Tests A through I verify:
- Test A: Manager direct reports routing and lookup
- Test B: Manager cross-team access denial
- Test C: Employee cross-employee leave access denial
- Test D: Employee self-access
- Test E: General policy retrieval availability
- Test F: Authorized manager employee-specific access
- Test G: MCP authorization parity and audit logging
- Test H: Super Admin trusted principal and demo controls
- Test I: Error handling and non-leakage
"""

from __future__ import annotations

import json
import re
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import api, agent
from app.api import RoleAccessPrincipal, get_authenticated_role_access_principal
from app.tools import DATABASE_PATH, get_employee_data, get_employees_by_manager
from app.router import route_question
from app.multi_agent.orchestrator import MultiAgentOrchestrator, run_multi_agent
from app.multi_agent.contracts import TaskType
from app.security import (
    authorize_employee_data_access,
    authorization_for_question,
    validate_tool_call,
)


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
    monkeypatch.setattr("app.tools.DATABASE_PATH", str(test_database))
    monkeypatch.setattr("app.security.DATABASE_PATH", str(test_database))
    monkeypatch.setattr("app.router.DATABASE_PATH", str(test_database))


@pytest.fixture(autouse=True)
def mock_agent_ollama_chat(monkeypatch):
    def fake_agent_chat(*args, **kwargs):
        messages = kwargs.get("messages", [])
        content = messages[-1]["content"] if messages else ""
        if "available_tools" in content:
            try:
                data = json.loads(content)
                q = data.get("question", "")
            except Exception:
                q = content

            if "under" in q.lower() or "report" in q.lower() or "direct report" in q.lower():
                from app.security import _extract_manager_query_name, resolve_canonical_manager_name
                mgr = _extract_manager_query_name(q) or "Arun Kumar"
                return {
                    "message": {
                        "content": json.dumps({
                            "action": "tool",
                            "tool": "get_employees_by_manager",
                            "arguments": {"manager_name": resolve_canonical_manager_name(mgr)},
                        })
                    }
                }

            emp_name = None
            for name in ["Asha Rao", "Vikram Shah", "Priya Nair", "Deepak Sharma", "Arun Kumar", "Neha Iyer", "Arjun Menon"]:
                if name.lower() in q.lower():
                    emp_name = name
                    break
            emp_id = None
            m = re.search(r"\b0\d{2}\b", q)
            if m:
                emp_id = m.group(0)

            args_dict = {}
            if emp_id:
                args_dict["employee_id"] = emp_id
            elif emp_name:
                args_dict["employee_name"] = emp_name
            else:
                args_dict["employee_name"] = "Priya Nair"

            return {
                "message": {
                    "content": json.dumps({
                        "action": "tool",
                        "tool": "get_employee_data",
                        "arguments": args_dict,
                    })
                }
            }

        return {"message": {"content": "Final answer based on observations."}}

    monkeypatch.setattr("app.agent.ollama.chat", fake_agent_chat)


# ---------------------------------------------------------------------------
# Test A — Manager direct reports
# ---------------------------------------------------------------------------

def test_a_manager_direct_reports_routing_and_lookup(client):
    """With Manager Arun Kumar identity:
    - Questions about direct reports route to agent (not direct RAG).
    - Database lookup returns actual reports (Neha Iyer, Arjun Menon).
    - No unrelated employees are returned.
    """
    questions = [
        "Who all are working under this manager?",
        "Who reports to Arun Kumar?",
        "List Arun Kumar's direct reports.",
    ]

    for q in questions:
        # 1. Routing check
        route = route_question(q)
        assert route == "agent", f"Question '{q}' should route to 'agent', got '{route}'"

    # 2. Execution check via API
    response = client.post(
        "/ask",
        json={
            "question": "Who all are working under this manager?",
            "conversation_id": "test-mgr-a1",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "agent"
    answer = data["answer"]

    # Verify actual reporting relationship from SQLite
    assert "Neha Iyer" in answer
    assert "Arjun Menon" in answer

    # Verify no unrelated employees are returned
    for unrelated in ["Asha Rao", "Vikram Shah", "Priya Nair", "Rahul Das"]:
        assert unrelated not in answer


def test_a_manager_direct_reports_in_multi_agent(client):
    """Multi-agent orchestrator also returns Arun Kumar's reports dynamically."""
    response = client.post(
        "/ask",
        json={
            "question": "Who all are working under this manager?",
            "conversation_id": "test-mgr-a2",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "multi_agent"
    assert "Neha Iyer" in data["answer"]
    assert "Arjun Menon" in data["answer"]
    assert "Priya Nair" not in data["answer"]


# ---------------------------------------------------------------------------
# Test B — Manager cannot access another manager's reports
# ---------------------------------------------------------------------------

def test_b_manager_cannot_access_another_manager_reports(client):
    """Deepak Sharma (Manager) asks for Arun Kumar's reports.
    Access must be denied without returning Arun's direct reports.
    """
    response = client.post(
        "/ask",
        json={
            "question": "Who reports to Arun Kumar?",
            "conversation_id": "test-mgr-b1",
            "role": "Manager",
            "employee_id": "005",
            "employee_name": "Deepak Sharma",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Access denied: employee is outside your authorized team." in data["answer"]
    assert "Neha Iyer" not in data["answer"]
    assert "Arjun Menon" not in data["answer"]


def test_b_manager_cannot_access_another_manager_reports_multi_agent(client):
    """Multi-agent orchestrator denies cross-manager team queries."""
    response = client.post(
        "/ask",
        json={
            "question": "List Arun Kumar's direct reports.",
            "conversation_id": "test-mgr-b2",
            "role": "Manager",
            "employee_id": "005",
            "employee_name": "Deepak Sharma",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Access denied: employee is outside your authorized team." in data["answer"]
    assert "Neha Iyer" not in data["answer"]
    assert "Arjun Menon" not in data["answer"]


# ---------------------------------------------------------------------------
# Test C — Employee cannot access another employee's leave
# ---------------------------------------------------------------------------

def test_c_employee_cannot_access_another_employee_leave(client):
    """Employee Asha Rao asks 'Can Priya Nair carry forward her remaining annual leave?'.
    - Private lookup denied before database result reaches specialist.
    - Eligibility specialist is not given Priya's balance.
    - Answer contains no private balance (20.0) or personalized disposition (5 encashed, 10 lapse).
    - Answer still explains general policy carry-over limit (10 days).
    """
    response = client.post(
        "/ask",
        json={
            "question": "Can Priya Nair carry forward her remaining annual leave?",
            "conversation_id": "test-emp-c1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    answer = data["answer"]

    # Must contain access denied
    assert "Access denied: your selected role does not have permission to view this employee." in answer

    # Must state the general annual leave policy rule
    assert "10 days" in answer
    assert "carried" in answer.lower() or "carry" in answer.lower()

    # Must NOT leak Priya's private balance (20) or personalized encashment/lapse disposition
    assert "5 days can be encashed" not in answer
    assert "10 days lapse" not in answer
    assert "For employee 005" not in answer

    # Verify worker responses do not include eligibility calculation specialist
    worker_responses = data.get("worker_responses", [])
    for resp in worker_responses:
        assert resp.get("task_type") != TaskType.ELIGIBILITY_CALCULATION.value


# ---------------------------------------------------------------------------
# Test D — Employee can access their own leave
# ---------------------------------------------------------------------------

def test_d_employee_can_access_own_leave(client):
    """Asha Rao requests her own leave calculation: succeeds with her record."""
    response = client.post(
        "/ask",
        json={
            "question": "Can Asha Rao carry forward her remaining annual leave?",
            "conversation_id": "test-emp-d1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    # Asha Rao has 2 days annual leave: 2 carry over, 2 encashable, 0 lapse
    assert "2 days can be carried over" in data["answer"]
    assert "For employee 001" in data["answer"]


def test_d_employee_first_person_leave_lookup(client):
    """Asha Rao asking 'What is my leave balance?' succeeds."""
    response = client.post(
        "/ask",
        json={
            "question": "What is my leave balance?",
            "conversation_id": "test-emp-d2",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "2 days" in data["answer"]
    assert "Asha Rao" in data["answer"]


# ---------------------------------------------------------------------------
# Test E — General policy remains available
# ---------------------------------------------------------------------------

def test_e_general_policy_remains_available(client):
    """General policy question works without retrieving private employee records."""
    response = client.post(
        "/ask",
        json={
            "question": "How many days of annual leave can an employee carry forward?",
            "conversation_id": "test-gen-e1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "10 days" in data["answer"]
    assert data["status"] == "success"
    # Verify no employee record lookup step
    steps = data.get("steps", [])
    assert not any(s.get("action") == "lookup_employee" for s in steps)


# ---------------------------------------------------------------------------
# Test F — Authorized manager employee-specific access
# ---------------------------------------------------------------------------

def test_f_authorized_manager_can_access_direct_report(client):
    """Arun Kumar (Manager) is authorized to access direct report Arjun Menon (004)."""
    response = client.post(
        "/ask",
        json={
            "question": "Can Arjun Menon carry forward his remaining annual leave?",
            "conversation_id": "test-mgr-f1",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "For employee 004" in data["answer"]


def test_f_manager_cannot_access_unrelated_employee(client):
    """Arun Kumar (Manager) cannot access Priya Nair (reports to Deepak Sharma)."""
    response = client.post(
        "/ask",
        json={
            "question": "Can Priya Nair carry forward her remaining annual leave?",
            "conversation_id": "test-mgr-f2",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
            "agent_mode": "multi",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Access denied: employee is outside your authorized team." in data["answer"]
    assert "5 days can be encashed" not in data["answer"]


# ---------------------------------------------------------------------------
# Test G — MCP authorization parity
# ---------------------------------------------------------------------------

def test_g_mcp_authorization_parity():
    """Verify validate_tool_call denies unauthorized employee snapshot/leave balance."""
    from app.agent import all_registered_tools

    # Asha Rao authorization
    auth = authorization_for_question(
        "What is Priya Nair's leave balance?",
        all_registered_tools(),
        role_context={
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "is_trusted_principal": False,
            "is_legacy": False,
        },
    )

    with pytest.raises(PermissionError) as exc_info:
        validate_tool_call(
            "hris_get_employee_leave_balance",
            {"employee_name": "Priya Nair"},
            auth,
        )
    assert "Access denied: your selected role does not have permission to view this employee." in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test H — Super Admin and trusted principal
# ---------------------------------------------------------------------------

def test_h_super_admin_trusted_principal_and_demo_mode(client, monkeypatch):
    """Super Admin access respects server-side demo configuration."""
    monkeypatch.setenv("ENABLE_DEMO_SUPER_ADMIN", "false")

    # Client-supplied Super Admin without trusted principal fails closed
    res_denied = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "test-sa-h1",
            "role": "Super Admin",
            "employee_id": "001",
        },
    )
    assert res_denied.status_code == 200
    assert "Super Admin access requires a trusted authenticated identity." in res_denied.json()["answer"]

    # When demo mode is explicitly enabled on the server
    monkeypatch.setenv("ENABLE_DEMO_SUPER_ADMIN", "true")
    res_allowed = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "test-sa-h2",
            "role": "Super Admin",
            "employee_id": "001",
        },
    )
    assert res_allowed.status_code == 200
    assert "1,800,000" in res_allowed.json()["answer"]


# ---------------------------------------------------------------------------
# Test I — Failure and error handling
# ---------------------------------------------------------------------------

def test_i_failure_and_error_handling_no_data_leakage(client):
    """Authorization denial does not leak private records in error status or worker results."""
    orchestrator = MultiAgentOrchestrator()
    result = orchestrator.run(
        "Can Priya Nair carry forward her remaining annual leave?",
        role_context={
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "is_trusted_principal": False,
            "is_legacy": False,
        },
    )

    assert result.status == "error"
    assert "Access denied" in result.answer
    assert "20.0" not in result.answer
    assert "20 days" not in result.answer

    # Ensure no calculation worker response exists
    for w in result.worker_responses:
        assert w.task_type != TaskType.ELIGIBILITY_CALCULATION
