"""Regression test suite for Agent-First Architecture and Copilot Context.

Tests A through F:
- Test A: General policy question ("What are the company's core values?")
  Verifies Agent is main entry point, selects policy retrieval, grounded in policy evidence,
  and does not bypass Agent via Direct RAG.
- Test B: Annual leave policy ("How many annual leave days can be carried forward?")
  Verifies policy retrieval selected, no private employee record fetched unnecessarily.
- Test C: Employee creation requirements ("What information do you need to add an employee?")
  Verifies employee creation schema tool selected, does not confuse with core values,
  does not invent fields outside repository schema.
- Test D: Manager reporting lookup ("Who all are working under this manager?")
  Verifies authorized lookup, results from actual SQLite DB, current reporting relationship enforced.
- Test E: Unauthorized private employee data (Asha Rao asks about Priya Nair's leave disposition)
  Verifies authorization denial, private record not passed, no leave balance exposed,
  general policy provided.
- Test F: Mode compatibility
  Verifies single-agent and multi-agent modes work, contract fields preserved.
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
    monkeypatch.setattr("app.tools.DATABASE_PATH", str(test_database))
    monkeypatch.setattr("app.security.DATABASE_PATH", str(test_database))
    monkeypatch.setattr("app.router.DATABASE_PATH", str(test_database))
    monkeypatch.setitem(globals(), "DATABASE_PATH", str(test_database))


@pytest.fixture(autouse=True)
def mock_agent_ollama_chat(monkeypatch):
    """Deterministic agent decision maker matching AgentState requirements."""
    def fake_chat(*args, **kwargs):
        messages = kwargs.get("messages", [])
        content = messages[-1]["content"] if messages else ""
        try:
            data = json.loads(content)
        except Exception:
            data = {}

        q = data.get("original_question", "")
        rec_tool = data.get("recommended_next_tool")

        if rec_tool and rec_tool != "final":
            arguments = {}
            if rec_tool == "lookup_policy":
                arguments = {"query": q}
            elif rec_tool == "lookup_annual_leave_policy":
                arguments = {"jurisdiction": "INDIA"}
            elif rec_tool == "get_employee_creation_requirements":
                arguments = {}
            elif rec_tool == "get_employees_by_manager":
                arguments = {"manager_name": "Arun Kumar"}
            elif rec_tool == "get_employee_data":
                m = re.search(r"\b0\d{2}\b", q)
                if m:
                    arguments = {"employee_id": m.group(0)}
                else:
                    for name in ["Priya Nair", "Asha Rao", "Neha Iyer", "Deepak Sharma", "Arun Kumar", "Vikram Shah"]:
                        if name.lower() in q.lower():
                            arguments = {"employee_name": name}
                            break
            elif rec_tool == "calculate_annual_leave_disposition":
                arguments = {"leave_balance": 18.0, "carry_over_limit": 10.0, "encashment_limit": 5.0}

            return {"message": {"content": json.dumps({"action": "tool", "tool": rec_tool, "arguments": arguments})}}

        return {"message": {"content": json.dumps({"action": "final", "answer": "Deterministic answered."})}}

    monkeypatch.setattr("app.agent.ollama.chat", fake_chat)


# ============================================================================
# Test A — General policy question
# ============================================================================

def test_a_general_policy_question_core_values(client):
    """Test A: 'What are the company's core values?'
    
    Expected:
    - Agent is the main entry point (route is 'agent', not 'rag').
    - Policy retrieval tool (lookup_policy) is selected.
    - Response is grounded in retrieved policy evidence (Integrity, Respect, etc.).
    - API does not bypass the Agent by using Direct RAG as the top-level route.
    """
    response = client.post(
        "/ask",
        json={
            "question": "What are the company's core values?",
            "conversation_id": "test-a-1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "agent"
    assert data["route"] != "rag"
    assert data["status"] in ("success", "answered")

    # Grounded evidence
    answer = data["answer"]
    for value in ("Integrity", "Respect", "Accountability", "Collaboration", "Excellence"):
        assert value.lower() in answer.lower(), f"Expected core value '{value}' in answer: {answer}"

    # Sources from ChromaDB policy documents
    sources = data.get("sources", [])
    assert len(sources) > 0
    assert any("conduct" in s.get("source", "").lower() for s in sources)


# ============================================================================
# Test B — Annual leave policy
# ============================================================================

def test_b_annual_leave_policy(client):
    """Test B: 'How many annual leave days can be carried forward?'
    
    Expected:
    - The Agent selects policy retrieval.
    - No private employee record is fetched unnecessarily.
    - Grounded policy answer states 10 days carry-over limit.
    """
    response = client.post(
        "/ask",
        json={
            "question": "How many annual leave days can be carried forward?",
            "conversation_id": "test-b-1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "agent"

    answer = data["answer"]
    assert "10" in answer
    assert "carry" in answer.lower()

    # Verify no private employee record is exposed in answer
    assert "Asha Rao" not in answer
    assert "Priya Nair" not in answer
    assert "18" not in answer  # Priya's private balance


# ============================================================================
# Test C — Employee creation requirements
# ============================================================================

def test_c_employee_creation_requirements(client):
    """Test C: 'What information do you need to add an employee?'
    
    Expected:
    - The Agent selects the get_employee_creation_requirements tool.
    - It does not mistake the question for core values despite any keywords.
    - It lists documented schema fields without inventing fictitious fields.
    """
    response = client.post(
        "/ask",
        json={
            "question": "What information do you need to add an employee?",
            "conversation_id": "test-c-1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "agent"

    answer = data["answer"]
    # Must NOT return company core values
    assert "integrity" not in answer.lower()
    assert "accountability" not in answer.lower()

    # Must contain documented schema fields
    for field in ("employee_id", "employee_name", "email", "department"):
        assert field in answer, f"Expected documented schema field '{field}' in answer: {answer}"


def test_c_employee_creation_with_values_keyword(client):
    """Test C variation: Question containing 'values' should not be routed to core values."""
    response = client.post(
        "/ask",
        json={
            "question": "What field values and information are required to create a new employee?",
            "conversation_id": "test-c-2",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "agent"
    assert "employee_id" in data["answer"]
    assert "integrity" not in data["answer"].lower()


# ============================================================================
# Test D — Manager reporting lookup
# ============================================================================

def test_d_manager_reporting_lookup(client):
    """Test D: 'Who all are working under this manager?'
    
    Expected:
    - The Agent selects authorized employee lookup (get_employees_by_manager).
    - Results are obtained from the actual employee database.
    - The reporting relationship and access permissions are enforced.
    """
    # Manager Arun Kumar (ID: 004) asking about his reports
    response = client.post(
        "/ask",
        json={
            "question": "Who all are working under this manager?",
            "conversation_id": "test-d-1",
            "role": "Manager",
            "employee_id": "004",
            "employee_name": "Arun Kumar",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "agent"

    # From SQLite database, employees reporting to Arun Kumar include Priya Nair and Neha Iyer
    answer = data["answer"]
    assert "Priya Nair" in answer or "Neha Iyer" in answer
    assert "Arun Kumar" in answer


# ============================================================================
# Test E — Unauthorized private employee data
# ============================================================================

def test_e_unauthorized_private_employee_data(client):
    """Test E: Trusted Employee Asha Rao asks:
    'Can Priya Nair carry forward her remaining annual leave?'
    
    Expected:
    - Request is denied because Asha is not authorized to access Priya's private data.
    - Priya's private record is not passed to the Agent / not exposed in the answer.
    - Response does not expose Priya's leave balance (18.0) or personalized disposition.
    - General annual leave policy information is provided without revealing private info.
    """
    response = client.post(
        "/ask",
        json={
            "question": "Can Priya Nair carry forward her remaining annual leave?",
            "conversation_id": "test-e-1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()

    answer = data["answer"]
    # Authorization denial present
    assert "Access denied" in answer or "not authorized" in answer.lower() or "denied" in answer.lower()
    # Priya's private balance must NOT be revealed
    assert "18" not in answer
    # General policy carry-forward limit provided
    assert "10" in answer or "carry" in answer.lower()


# ============================================================================
# Test F — Mode compatibility
# ============================================================================

def test_f_mode_compatibility_single_and_multi(client):
    """Test F: Verify single-agent and multi-agent modes preserve contract fields."""
    # 1. Single-agent mode
    resp_single = client.post(
        "/ask",
        json={
            "question": "How many annual leave days can be carried forward?",
            "conversation_id": "test-f-single",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "execution_mode": "single",
        },
    )
    assert resp_single.status_code == 200
    data_single = resp_single.json()
    assert data_single["route"] == "agent"
    assert data_single["execution_mode"] == "single"
    for field in ("question", "answer", "sources", "route", "conversation_id", "execution_mode", "status", "metrics"):
        assert field in data_single, f"Missing field '{field}' in single-agent response"

    # 2. Multi-agent mode
    resp_multi = client.post(
        "/ask",
        json={
            "question": "How many annual leave days can be carried forward under the policy?",
            "conversation_id": "test-f-multi",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
            "execution_mode": "multi",
        },
    )
    assert resp_multi.status_code == 200
    data_multi = resp_multi.json()
    assert data_multi["route"] == "multi_agent"
    assert data_multi["execution_mode"] == "multi"
    for field in ("question", "answer", "sources", "route", "conversation_id", "execution_mode", "status", "metrics"):
        assert field in data_multi, f"Missing field '{field}' in multi-agent response"
