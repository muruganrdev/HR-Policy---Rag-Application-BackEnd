import json
import sys
from pathlib import Path

import pytest

from app.mcp_client import MCPClient
from mcp_servers.gateway_server import MCPGateway, ROOT


def _config(path: Path, audit_path: Path) -> Path:
    config_path = path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "servers": {
                    "mcp_gateway": {
                        "type": "stdio",
                        "command": sys.executable,
                        "args": [str(ROOT / "mcp_servers" / "gateway_server.py")],
                        "env": {
                            "MCP_GATEWAY_TOKEN": "test-agent-token",
                            "MCP_GATEWAY_CONFIG": str(path / "mcp.json"),
                        },
                    }
                },
                "backends": {
                    "hris_server": {
                        "type": "stdio",
                        "command": sys.executable,
                        "args": [str(ROOT / "mcp_servers" / "hris_server.py")],
                    },
                    "hr_policy_server": {
                        "type": "stdio",
                        "command": sys.executable,
                        "args": [str(ROOT / "mcp_servers" / "hr_policy_server.py")],
                    },
                },
                "scoped_tokens": {
                    "test-agent-token": {
                        "caller": "agent",
                        "scopes": [
                            "employee_snapshot:read",
                            "department_roster:read",
                            "manager_team:read",
                            "policy:read",
                            "leave_disposition:calculate",
                            "tool:invoke",
                        ],
                    }
                },
                "audit_log": str(audit_path),
            }
        ),
        encoding="utf-8",
    )
    return config_path


@pytest.fixture
def gateway_client(tmp_path):
    audit_path = tmp_path / "audit_log.txt"
    config_path = _config(tmp_path, audit_path)
    client = MCPClient(config_path=config_path)
    try:
        yield client, audit_path
    finally:
        client.close()


def test_gateway_initialize(gateway_client):
    client, _ = gateway_client
    client.start()
    response = client._send_jsonrpc(
        client._processes["mcp_gateway"],
        {"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}},
    )
    assert response["result"]["serverInfo"]["name"] == "mcp_gateway"


def test_gateway_tools_list_exposes_configured_backend_tools(gateway_client):
    client, _ = gateway_client
    tools = client.discover_tools()
    assert "hris_get_employee_leave_balance" in tools
    assert "hris_get_employee_grade_band" in tools
    assert "lookup_annual_leave_policy" in tools
    assert {tool["mcp_server"] for tool in tools.values()} == {"mcp_gateway"}


def test_gateway_resource_discovery_and_read(gateway_client):
    client, _ = gateway_client
    resources = client.discover_resources()

    assert "hr://policy/annual-leave" in resources
    assert resources["hr://policy/annual-leave"]["mcp_server"] == "mcp_gateway"
    response = client.read_resource("hr://policy/annual-leave")
    assert len(response["contents"]) == 1
    content = response["contents"][0]["text"]
    assert "Unused annual leave of up to 10 days may be carried over" in content
    assert "Source: leave_policy.pdf (chunk 2)" in content


def test_gateway_prompt_discovery_and_get(gateway_client):
    client, _ = gateway_client
    prompts = client.discover_prompts()

    assert "employee_leave_summary" in prompts
    assert prompts["employee_leave_summary"]["mcp_server"] == "mcp_gateway"
    response = client.get_prompt(
        "employee_leave_summary", {"employee_name": "Priya Nair"}
    )
    assert response["messages"][0]["role"] == "user"
    assert "Priya Nair" in response["messages"][0]["content"]["text"]
    assert "do not infer it" in response["messages"][0]["content"]["text"]


def test_gateway_routes_hris_tool(gateway_client):
    client, _ = gateway_client
    result = client.call_tool(
        "hris_get_employee_leave_balance", {"employee_name": "Priya Nair"}
    )
    assert result == {
        "employee_id": "005",
        "employee_name": "Priya Nair",
        "leave_balance": 20.0,
    }


def test_gateway_routes_policy_tool(gateway_client):
    client, _ = gateway_client
    result = client.call_tool("lookup_annual_leave_policy", {"jurisdiction": "INDIA"})
    assert result["policy_area"] == "annual_leave_balance"


def test_gateway_writes_audit_entry(gateway_client):
    client, audit_path = gateway_client
    client.call_tool("hris_get_employee_leave_balance", {"employee_name": "Priya Nair"})
    audit = audit_path.read_text(encoding="utf-8")
    assert "caller=agent" in audit
    assert "tool=hris_get_employee_leave_balance" in audit
    assert "employee_id=005" in audit


def test_gateway_writes_exactly_one_audit_entry_per_call(gateway_client):
    client, audit_path = gateway_client
    client.call_tool("hris_get_employee_leave_balance", {"employee_name": "Priya Nair"})
    entries = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(entries) == 1


def test_gateway_audits_unknown_tools_call_once(gateway_client):
    client, audit_path = gateway_client
    client.start()
    response = client._send_jsonrpc(
        client._processes["mcp_gateway"],
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        },
    )
    assert response["error"]["code"] == -32603
    entries = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(entries) == 1
    assert "tool=unknown_tool" in entries[0]
    assert "employee_id=unknown" in entries[0]


def test_agent_can_use_authorized_mcp_department_roster(gateway_client, monkeypatch):
    import app.agent as agent

    client, _ = gateway_client
    registry = client.build_agent_tool_registry()
    monkeypatch.setitem(
        agent.MCP_TOOLS,
        "hris_get_department_roster",
        agent.ToolSpec(
            name="hris_get_department_roster",
            description="List employees in a department.",
            callable=registry["hris_get_department_roster"]["callable"],
        ),
    )
    chat = iter([
        {
            "message": {
                "content": json.dumps({
                    "action": "tool",
                    "tool": "hris_get_department_roster",
                    "arguments": {"department_name": "Engineering"},
                })
            }
        }
    ])

    result = agent.run_agent(
        "Who works in the Engineering department?",
        chat_fn=lambda **_: next(chat),
    )

    tool_step = next(step for step in result["steps"] if step.get("phase") == "tool")
    assert tool_step["tool"] == "hris_get_department_roster"
    assert tool_step["observation"]["status"] == "success"
    assert result["answer"] == "Neha Iyer and Arjun Menon work in Engineering."


@pytest.mark.parametrize(
    ("question", "local_tool", "arguments", "mcp_tool", "expected_answer"),
    [
        (
            "What is Priya Nair's leave balance?",
            "get_employee_data",
            {"employee_name": "Priya Nair"},
            "hris_get_employee_leave_balance",
            "Priya Nair's annual leave balance is 20.0.",
        ),
        (
            "Who reports to Deepak Sharma?",
            "get_employees_by_manager",
            {"manager_name": "Deepak Sharma"},
            "hris_get_manager_team",
            "Priya Nair reports to Deepak Sharma.",
        ),
        (
            "What is the annual leave policy for India?",
            "lookup_annual_leave_policy",
            {"jurisdiction": "INDIA"},
            "mcp_lookup_annual_leave_policy",
            "India's annual leave policy allows up to 10 days",
        ),
    ],
)
def test_agent_prefers_configured_mcp_capability(
    gateway_client, monkeypatch, question, local_tool, arguments, mcp_tool, expected_answer
):
    import app.agent as agent

    client, _ = gateway_client
    registry = client.build_agent_tool_registry()
    backend_tool = "lookup_annual_leave_policy" if mcp_tool == "mcp_lookup_annual_leave_policy" else mcp_tool
    monkeypatch.setitem(
        agent.MCP_TOOLS,
        mcp_tool,
        agent.ToolSpec(
            name=mcp_tool,
            description="MCP gateway tool; scoped and audited.",
            callable=registry[backend_tool]["callable"],
            input_schema=registry[backend_tool]["parameters"],
        ),
    )
    scripted = iter([{"message": {"content": json.dumps({
        "action": "tool",
        "tool": local_tool,
        "arguments": arguments,
    })}}])

    result = agent.run_agent(
        question,
        chat_fn=lambda **_: next(scripted),
        prefer_mcp_tools=True,
    )

    executed = next(step for step in result["steps"] if step.get("phase") == "tool")
    assert executed["tool"] == mcp_tool
    assert executed["observation"]["status"] == "success"
    if mcp_tool == "mcp_lookup_annual_leave_policy":
        assert expected_answer in result["answer"]
    else:
        assert result["answer"] == expected_answer