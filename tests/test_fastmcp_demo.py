from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_servers" / "fastmcp_demo_server.py"


def _result_data(result):
    if isinstance(result, dict):
        data = result.get("structuredContent") or result.get("structured_content")
        if data is not None:
            return data
        content = result.get("content", [])
    else:
        data = getattr(result, "structured_content", None)
        if data is not None:
            return data
        content = getattr(result, "content", [])
    for item in content:
        text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError("FastMCP call returned no structured or text result")


def test_fastmcp_stdio_server_discovers_and_calls_hr_tool():
    async def run_probe():
        transport = PythonStdioTransport(
            script_path=SERVER,
            python_cmd=sys.executable,
            cwd=str(ROOT),
        )
        async with Client(transport) as client:
            tools = await client.list_tools()
            result = await client.call_tool(
                "get_employee_leave_summary", {"employee_name": "Priya Nair"}
            )
            return tools, result

    tools, result = asyncio.run(run_probe())
    assert "get_employee_leave_summary" in {tool.name for tool in tools}
    assert _result_data(result) == {
        "employee_id": "005",
        "employee_name": "Priya Nair",
        "leave_balance": 20.0,
        "sick_leave_balance": 12.0,
    }
