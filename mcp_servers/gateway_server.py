from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.mcp_client import MCPClient
from mcp_servers._mcp_server import MCPJsonServer

ROOT = Path(__file__).resolve().parents[1]


class _AuditedGatewayServer(MCPJsonServer):
    def __init__(
        self,
        gateway: "MCPGateway",
        tools: dict[str, dict[str, Any]],
        *,
        resources: dict[str, dict[str, Any]],
        prompts: dict[str, dict[str, Any]],
    ):
        super().__init__("mcp_gateway", tools, resources=resources, prompts=prompts)
        self.gateway = gateway

    def _dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        if message.get("method") != "tools/call":
            return super()._dispatch(message)
        params = message.get("params", {})
        tool_name = params.get("name", "unknown")
        arguments = params.get("arguments") or {}
        employee_id = arguments.get("employee_id", "unknown")
        token_record = self.gateway._token_record()
        caller = token_record.get("caller", "unknown") if token_record else "unknown"
        try:
            result = super()._dispatch(message)
            content = result.get("structuredContent") if isinstance(result, dict) else None
            if isinstance(content, dict) and content.get("employee_id"):
                employee_id = content["employee_id"]
            return result
        finally:
            self.gateway._audit(caller, tool_name, employee_id)


class MCPGateway:
    """Config-driven MCP front door with scoped calls and a central audit sink."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        client: MCPClient | None = None,
        token: str | None = None,
        audit_path: str | Path | None = None,
    ):
        self.config_path = Path(config_path) if config_path else ROOT / ".vscode" / "mcp.json"
        with self.config_path.open("r", encoding="utf-8") as handle:
            self.config = json.load(handle)
        self.client = client or MCPClient(self.config_path, server_config_key="backends")
        self.token = token if token is not None else os.environ.get("MCP_GATEWAY_TOKEN", "")
        configured_audit_path = audit_path or self.config.get("audit_log", "evidence/week9_mcp/audit_log.txt")
        self.audit_path = Path(configured_audit_path)
        if not self.audit_path.is_absolute():
            self.audit_path = ROOT / self.audit_path
        self.tool_catalog = self.client.discover_tools()
        self.resource_catalog = self.client.discover_resources()
        self.prompt_catalog = self.client.discover_prompts()
        self.server = _AuditedGatewayServer(
            self,
            self._gateway_tools(),
            resources=self._gateway_resources(),
            prompts=self._gateway_prompts(),
        )

    def _gateway_tools(self) -> dict[str, dict[str, Any]]:
        tools = {}
        for tool_name, metadata in self.tool_catalog.items():
            def invoke(*, _tool_name: str = tool_name, **arguments: Any) -> dict[str, Any]:
                return self._call_tool(_tool_name, arguments)

            tools[tool_name] = {
                "name": tool_name,
                "description": metadata.get("description", ""),
                "inputSchema": metadata.get("inputSchema", {"type": "object", "properties": {}}),
                "func": invoke,
            }
        return tools

    def _gateway_resources(self) -> dict[str, dict[str, Any]]:
        resources = {}
        for uri, metadata in self.resource_catalog.items():
            server_name = metadata["mcp_server"]

            def read(*, _uri: str = uri, _server_name: str = server_name) -> str:
                response = self.client.read_resource(_uri, server_name=_server_name)
                return "\n\n".join(
                    item.get("text", "")
                    for item in response.get("contents", [])
                    if isinstance(item, dict)
                )

            resources[uri] = {
                key: metadata[key]
                for key in ("uri", "name", "title", "description", "mimeType")
                if key in metadata
            }
            resources[uri]["read"] = read
        return resources

    def _gateway_prompts(self) -> dict[str, dict[str, Any]]:
        prompts = {}
        for name, metadata in self.prompt_catalog.items():
            server_name = metadata["mcp_server"]

            def get(arguments: dict[str, Any], *, _name: str = name, _server_name: str = server_name) -> dict[str, Any]:
                return self.client.get_prompt(_name, arguments, server_name=_server_name)

            prompts[name] = {
                key: metadata[key]
                for key in ("name", "description", "arguments")
                if key in metadata
            }
            prompts[name]["get"] = get
        return prompts

    @staticmethod
    def _required_scope(tool_name: str) -> str:
        if "snapshot" in tool_name:
            return "employee_snapshot:read"
        if "department_roster" in tool_name:
            return "department_roster:read"
        if "manager_team" in tool_name:
            return "manager_team:read"
        if "policy" in tool_name or tool_name == "lookup_annual_leave_policy":
            return "policy:read"
        if "disposition" in tool_name:
            return "leave_disposition:calculate"
        return "tool:invoke"

    @staticmethod
    def _safe_field(value: Any, fallback: str = "unknown") -> str:
        normalized = re.sub(r"[^A-Za-z0-9_.-]", "_", str(value or ""))
        return normalized[:100] or fallback

    def _audit(self, caller: str, tool_name: str, employee_id: Any) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        entry = (
            f"timestamp={timestamp} caller={self._safe_field(caller)} "
            f"tool={self._safe_field(tool_name)} "
            f"employee_id={self._safe_field(employee_id)}\n"
        )
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(entry)

    def _token_record(self) -> dict[str, Any] | None:
        tokens = self.config.get("scoped_tokens", {})
        token_record = tokens.get(self.token) if isinstance(tokens, dict) else None
        return token_record if isinstance(token_record, dict) else None

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        token_record = self._token_record()
        required_scope = self._required_scope(tool_name)
        scopes = token_record.get("scopes", []) if token_record else []
        if not token_record or required_scope not in scopes:
            return {
                "_mcp_is_error": True,
                "structuredContent": {
                    "error": "Scoped authorization denied",
                    "code": "authorization_denied",
                    "recoverable": True,
                    "tool": tool_name,
                    "required_scope": required_scope,
                },
            }
        return self.client.call_tool(tool_name, arguments)

    def dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        return self.server(message)

    def run(self) -> None:
        self.server.run()

    def close(self) -> None:
        self.client.close()


if __name__ == "__main__":
    gateway = MCPGateway(os.environ.get("MCP_GATEWAY_CONFIG"))
    try:
        gateway.run()
    finally:
        gateway.close()