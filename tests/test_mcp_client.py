import json

import pytest

from app.agent import execute_tool
from app.mcp_client import MCPClient


def test_mcp_client_discovers_server_tools(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps(
            {
                "servers": {
                    "hr_policy_server": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["mcp_servers/hr_policy_server.py"],
                    },
                    "hris_server": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["mcp_servers/hris_server.py"],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    client = MCPClient(config_path=config)
    discovered = client.discover_tools()

    assert "get_department_employees" in discovered
    assert "hris_get_employee_snapshot" in discovered
    assert discovered["hris_get_employee_snapshot"]["mcp_server"] == "hris_server"
    description = discovered["hris_get_employee_snapshot"]["description"]
    assert "employee snapshot" in description.lower()
    assert "employee_name" in description
    assert "annual_salary" in description.lower()
    assert "must not invent" in description.lower()


def test_mcp_error_is_structured_and_recoverable(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps(
            {
                "servers": {
                    "hris_server": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["mcp_servers/hris_server.py"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    client = MCPClient(config_path=config)
    client.start()
    try:
        with pytest.raises(RuntimeError, match="No employee found with name: Ghost Employee"):
            client.call_tool("hris_get_employee_snapshot", {"employee_name": "Ghost Employee"})
    finally:
        client.close()

    result = execute_tool("hris_get_employee_snapshot", {"employee_name": "Ghost Employee"})
    assert result["recoverable"] is True
    assert result["tool"] == "hris_get_employee_snapshot"
    assert "No employee found with name: Ghost Employee" in result["error"]


def test_execute_tool_uses_mcp_call_for_hris_snapshot(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps(
            {
                "servers": {
                    "hris_server": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["mcp_servers/hris_server.py"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    client = MCPClient(config_path=config)
    client.start()
    try:
        registry = client.build_agent_tool_registry()
        tool = registry["hris_get_employee_snapshot"]
        result = tool["callable"]({"employee_name": "Priya Nair"})
        assert result["employee_name"] == "Priya Nair"
        assert result["annual_salary"] == 1800000.0
    finally:
        client.close()

    tool_result = execute_tool("get_employee_data", {"employee_name": "Priya Nair"})
    assert tool_result["employee_name"] == "Priya Nair"
