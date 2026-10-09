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



@pytest.fixture
def super_admin_client(client):
    app.dependency_overrides[get_authenticated_role_access_principal] = lambda: RoleAccessPrincipal(
        role="Super Admin", employee_id="001"
    )
    yield client
    app.dependency_overrides.pop(get_authenticated_role_access_principal, None)


@pytest.fixture(autouse=True)
def mock_agent_ollama_chat(monkeypatch):
    import json
    import re

    def fake_agent_chat(*args, **kwargs):
        messages = kwargs.get("messages", [])
        content = messages[-1]["content"] if messages else ""
        if "available_tools" in content:
            try:
                data = json.loads(content)
                q = data.get("question", "")
            except Exception:
                q = content

            emp_name = None
            for name in ["Asha Rao", "Vikram Shah", "Priya Nair", "Deepak Sharma", "Arun Kumar", "Vikram Malhotra", "Neha Iyer", "Arjun Menon"]:
                if name.lower() in q.lower():
                    emp_name = name
                    break
            emp_id = None
            m = re.search(r"\b0\d{2}\b", q)
            if m:
                emp_id = m.group(0)

            if "manager" in q.lower() and "report" in q.lower():
                return {"message": {"content": json.dumps({"action": "tool", "tool": "get_employees_by_manager", "arguments": {"manager_name": emp_name or "Deepak Sharma"}})}}

            args_dict = {}
            if emp_id:
                args_dict["employee_id"] = emp_id
            elif emp_name:
                args_dict["employee_name"] = emp_name
            else:
                args_dict["employee_name"] = "Priya Nair"

            return {"message": {"content": json.dumps({"action": "tool", "tool": "get_employee_data", "arguments": args_dict})}}

        return {"message": {"content": "Final answer based on observations."}}

    monkeypatch.setattr("app.agent.ollama.chat", fake_agent_chat)


# ---------------------------------------------------------------------------
# Phase 7.1: API payload and context tests
# ---------------------------------------------------------------------------

def test_ask_rejects_unsupported_role(client):
    response = client.post(
        "/ask",
        json={
            "question": "What is annual leave?",
            "conversation_id": "test-1",
            "role": "HackerRole",
        },
    )
    assert response.status_code == 400
    assert "Unsupported role 'HackerRole'" in response.json()["detail"]


def test_ask_rejects_missing_employee_id_for_employee_role(client):
    response = client.post(
        "/ask",
        json={
            "question": "What is my salary?",
            "conversation_id": "test-1",
            "role": "Employee",
        },
    )
    assert response.status_code == 400
    assert "employee_id is required" in response.json()["detail"]


def test_ask_rejects_unknown_employee_id(client):
    response = client.post(
        "/ask",
        json={
            "question": "What is my salary?",
            "conversation_id": "test-1",
            "role": "Employee",
            "employee_id": "999",
        },
    )
    assert response.status_code == 404
    assert "Employee '999' not found" in response.json()["detail"]


def test_ask_preserves_question_and_conversation_id(client, monkeypatch):
    monkeypatch.setattr("app.rag.ollama.chat", lambda *args, **kwargs: {"message": {"content": "Policy answer"}})
    response = client.post(
        "/ask",
        json={
            "question": "How many days of annual leave do I get?",
            "conversation_id": "conv-test-99",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "How many days of annual leave do I get?"
    assert "answer" in data


def test_ask_legacy_request_without_role_denies_employee_lookup(client):
    response = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "legacy-conv-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Access denied: role context is required to view employee records" in data["answer"]


# ---------------------------------------------------------------------------
# Phase 7.2: Employee role tests
# ---------------------------------------------------------------------------

def test_employee_can_view_own_salary(client, monkeypatch):
    # Asha Rao (001) asking for Asha Rao's salary
    response = client.post(
        "/ask",
        json={
            "question": "What is Asha Rao's salary?",
            "conversation_id": "emp-1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    assert "Asha Rao's annual salary is" in response.json()["answer"]


def test_employee_can_use_first_person_salary_reference(client, monkeypatch):
    # Asha Rao (001) asking "What is my salary?"
    response = client.post(
        "/ask",
        json={
            "question": "What is my salary?",
            "conversation_id": "emp-2",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    assert response.json()["question"] == "What is my salary?"
    assert "Asha Rao's annual salary is" in response.json()["answer"]


def test_employee_cannot_view_another_employee_salary(client):
    # Asha Rao (001) asking for Vikram Shah's salary (002)
    response = client.post(
        "/ask",
        json={
            "question": "What is Vikram Shah's salary?",
            "conversation_id": "emp-3",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Access denied: your selected role does not have permission to view this employee." in data["answer"]


def test_employee_cannot_view_another_employee_by_id(client):
    # Asha Rao (001) asking for employee 005
    response = client.post(
        "/ask",
        json={
            "question": "What is employee 005's salary?",
            "conversation_id": "emp-4",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Access denied: your selected role does not have permission to view this employee." in data["answer"]


# ---------------------------------------------------------------------------
# Phase 7.3: Manager role tests
# ---------------------------------------------------------------------------

def test_manager_can_view_team_member_salary(client):
    # Arun Kumar (003) is manager of Neha Iyer (003) and Arjun Menon (004)
    response = client.post(
        "/ask",
        json={
            "question": "What is Arjun Menon's salary?",
            "conversation_id": "mgr-1",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Arjun Menon's annual salary is" in data["answer"]


def test_manager_cannot_view_outside_team_member_salary(client):
    # Arun Kumar (003) asking for Priya Nair (005, reports to Deepak Sharma)
    response = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "mgr-2",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Access denied: employee is outside your authorized team." in data["answer"]


# ---------------------------------------------------------------------------
# Phase 7.4: Super Admin tests
# ---------------------------------------------------------------------------

def test_untrusted_super_admin_cannot_access_private_records_when_demo_disabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SUPER_ADMIN", "false")
    response = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "sa-disabled-1",
            "role": "Super Admin",
            "employee_id": "001",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Super Admin access requires a trusted authenticated identity." in data["answer"]


def test_super_admin_demo_mode_allows_lookup(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SUPER_ADMIN", "true")
    response = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "sa-demo-1",
            "role": "Super Admin",
            "employee_id": "001",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "1,800,000" in data["answer"]


def test_arbitrary_client_role_cannot_activate_demo_super_admin(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_SUPER_ADMIN", "false")
    response = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "sa-spoof-1",
            "role": "Super Admin",
            "employee_id": "999",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Super Admin access requires a trusted authenticated identity." in data["answer"]


def test_trusted_super_admin_can_access_employee_records(super_admin_client):
    response = super_admin_client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "sa-trusted-1",
            "role": "Super Admin",
            "employee_id": "001",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Priya Nair's annual salary is" in data["answer"]


# ---------------------------------------------------------------------------
# Phase 7.5: Enhanced Identity Validation and Conversation Isolation tests
# ---------------------------------------------------------------------------

def test_unsupported_manager_identities_rejected_with_http_400(client):
    # Employee 001 maps to Sunita Pillai (not in DEMO_MANAGER_NAMES)
    res1 = client.post(
        "/ask",
        json={
            "question": "Who reports to me?",
            "conversation_id": "mgr-unsupp-1",
            "role": "Manager",
            "employee_id": "001",
            "employee_name": "Sunita Pillai",
        },
    )
    assert res1.status_code == 400
    assert "Unsupported demo manager" in res1.json()["detail"]

    # Employee 002 maps to Ramesh Gupta (not in DEMO_MANAGER_NAMES)
    res2 = client.post(
        "/ask",
        json={
            "question": "Who reports to me?",
            "conversation_id": "mgr-unsupp-2",
            "role": "Manager",
            "employee_id": "002",
            "employee_name": "Ramesh Gupta",
        },
    )
    assert res2.status_code == 400
    assert "Unsupported demo manager" in res2.json()["detail"]

    # Employee 006 maps to Preethi Nanda (not in DEMO_MANAGER_NAMES)
    res3 = client.post(
        "/ask",
        json={
            "question": "Who reports to me?",
            "conversation_id": "mgr-unsupp-3",
            "role": "Manager",
            "employee_id": "006",
            "employee_name": "Preethi Nanda",
        },
    )
    assert res3.status_code == 400
    assert "Unsupported demo manager" in res3.json()["detail"]

    # Name mismatch: 003 is Arun Kumar, not Sunita Pillai
    res4 = client.post(
        "/ask",
        json={
            "question": "Who reports to me?",
            "conversation_id": "mgr-mismatch-1",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Sunita Pillai",
        },
    )
    assert res4.status_code == 400
    assert "Manager identity mismatch" in res4.json()["detail"]


def test_arun_kumar_supported_direct_reports_accessible(client):
    response = client.post(
        "/ask",
        json={
            "question": "What is Neha Iyer's salary?",
            "conversation_id": "mgr-arun-1",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
        },
    )
    assert response.status_code == 200
    assert "840,000" in response.json()["answer"]

    response2 = client.post(
        "/ask",
        json={
            "question": "What is Arjun Menon's salary?",
            "conversation_id": "mgr-arun-2",
            "role": "Manager",
            "employee_id": "003",
            "employee_name": "Arun Kumar",
        },
    )
    assert response2.status_code == 200
    assert "1,200,000" in response2.json()["answer"]


def test_deepak_sharma_supported_direct_reports_accessible(client):
    response = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "mgr-deepak-1",
            "role": "Manager",
            "employee_id": "005",
            "employee_name": "Deepak Sharma",
        },
    )
    assert response.status_code == 200
    assert "1,800,000" in response.json()["answer"]


def test_employee_overloaded_ids_resolve_to_employee(client):
    # ID 003 as Employee must resolve to Neha Iyer, not Arun Kumar
    res1 = client.post(
        "/ask",
        json={
            "question": "What is my salary?",
            "conversation_id": "emp-neha-1",
            "role": "Employee",
            "employee_id": "003",
            "employee_name": "Neha Iyer",
        },
    )
    assert res1.status_code == 200
    assert "840,000" in res1.json()["answer"]

    # ID 005 as Employee must resolve to Priya Nair, not Deepak Sharma
    res2 = client.post(
        "/ask",
        json={
            "question": "What is my salary?",
            "conversation_id": "emp-priya-1",
            "role": "Employee",
            "employee_id": "005",
            "employee_name": "Priya Nair",
        },
    )
    assert res2.status_code == 200
    assert "1,800,000" in res2.json()["answer"]


def test_employee_rejects_spoofed_employee_name(client):
    # Client sends employee_id 001 (Asha Rao) but claims name is Vikram Shah
    response = client.post(
        "/ask",
        json={
            "question": "What is my salary?",
            "conversation_id": "emp-spoof-1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Vikram Shah",
        },
    )
    assert response.status_code == 400
    assert "does not match record for employee ID '001'" in response.json()["detail"]


def test_conversation_isolation_across_role_switch(client):
    from app.api import _conversation_memory

    # Step 1: Super Admin asks for Priya Nair's salary in conv-switch-1
    res1 = client.post(
        "/ask",
        json={
            "question": "What is Priya Nair's salary?",
            "conversation_id": "conv-switch-1",
            "role": "Super Admin",
            "employee_id": "001",
        },
    )
    assert res1.status_code == 200
    assert "1,800,000" in res1.json()["answer"]

    # Verify history is stored for Super Admin
    history1 = _conversation_memory.get_history("conv-switch-1", role="Super Admin", employee_id="001")
    assert len(history1) > 0

    # Step 2: Employee 001 reuses the exact same conversation_id
    # Conversation memory MUST evict the previous Super Admin history
    history_as_emp = _conversation_memory.get_history("conv-switch-1", role="Employee", employee_id="001")
    assert len(history_as_emp) == 0, "Conversation history must be evicted on role switch"

    # Step 3: Employee asks a question in the same conversation
    res2 = client.post(
        "/ask",
        json={
            "question": "What is my salary?",
            "conversation_id": "conv-switch-1",
            "role": "Employee",
            "employee_id": "001",
            "employee_name": "Asha Rao",
        },
    )
    assert res2.status_code == 200
    assert "480,000" in res2.json()["answer"]


def test_local_and_mcp_tool_paths_enforce_same_security_policy():
    from app.security import authorization_for_question, validate_tool_call

    tools = frozenset({"get_employee_data", "hris_get_employee_snapshot"})
    emp_auth = authorization_for_question(
        "What is Asha Rao's salary?",
        registered_tools=tools,
        role_context={"role": "Employee", "employee_id": "001", "employee_name": "Asha Rao"},
    )

    # 1. Local get_employee_data self vs other
    dec_local_self = validate_tool_call("get_employee_data", {"employee_name": "Asha Rao"}, emp_auth)
    assert dec_local_self == {"employee_name": "Asha Rao"}

    with pytest.raises(PermissionError):
        validate_tool_call("get_employee_data", {"employee_name": "Vikram Shah"}, emp_auth)

    # 2. MCP equivalent tools must have the exact same decision
    dec_mcp_self = validate_tool_call("hris_get_employee_snapshot", {"employee_name": "Asha Rao"}, emp_auth)
    assert dec_mcp_self == {"employee_name": "Asha Rao"}

    with pytest.raises(PermissionError):
        validate_tool_call("hris_get_employee_snapshot", {"employee_name": "Vikram Shah"}, emp_auth)
