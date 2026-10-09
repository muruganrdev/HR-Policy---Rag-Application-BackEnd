from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class MCPClient:
    """Small stdio MCP client that discovers and invokes configured tools."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        server_config_key: str = "servers",
    ):
        self.root = ROOT
        self.config_path = self._resolve_config_path(config_path)
        self.server_config_key = server_config_key
        self._started = False
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._tool_catalog: dict[str, dict[str, Any]] = {}
        self._resource_catalog: dict[str, dict[str, Any]] = {}
        self._prompt_catalog: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _resolve_config_path(config_path: str | Path | None) -> Path:
        if config_path is not None:
            candidate = Path(config_path)
            if candidate.exists():
                return candidate
        for candidate in (ROOT / ".vscode" / "mcp.json", ROOT / "mcp.json"):
            if candidate.exists():
                return candidate
        return ROOT / ".vscode" / "mcp.json"

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {"servers": {}}
        with self.config_path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        return config if isinstance(config, dict) else {"servers": {}}

    def _server_command(self, server_name: str, config: dict[str, Any]) -> list[str]:
        command = config.get("command")
        args = config.get("args", [])
        if command is None:
            raise ValueError(f"MCP server '{server_name}' is missing a command")
        command_path = Path(str(command))
        if command_path.name.casefold() in {"python", "python.exe", "python3", "python3.exe"}:
            command = sys.executable
        return [str(command), *[str(arg) for arg in args]]

    def _send_jsonrpc(self, process: subprocess.Popen[bytes], request: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
        framed = b"Content-Length: " + str(len(payload)).encode("utf-8") + b"\r\n\r\n" + payload
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("MCP subprocess is not configured for stdio transport")
        process.stdin.write(framed)
        process.stdin.flush()

        headers = b""
        while b"\r\n\r\n" not in headers:
            chunk = process.stdout.read(1)
            if not chunk:
                raise RuntimeError("MCP server closed stdout unexpectedly")
            headers += chunk

        header_text = headers.decode("utf-8", errors="replace")
        content_length = 0
        for line in header_text.split("\r\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                if key.strip().lower() == "content-length":
                    content_length = int(value.strip())
                    break
        if content_length <= 0:
            raise RuntimeError(f"Missing Content-Length in MCP response: {header_text!r}")

        body = process.stdout.read(content_length)
        if not body:
            raise RuntimeError("MCP server returned an empty JSON-RPC body")
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover
            raise RuntimeError(f"Invalid JSON-RPC response: {body!r}") from exc

    def _start_server(self, server_name: str, config: dict[str, Any]) -> subprocess.Popen[bytes]:
        proc = subprocess.Popen(
            self._server_command(server_name, config),
            cwd=str(self.root),
            env={
                **os.environ,
                **{str(key): str(value) for key, value in config.get("env", {}).items()},
                "PYTHONPATH": str(self.root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
            },
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._processes[server_name] = proc
        return proc

    def start(self) -> dict[str, dict[str, Any]]:
        if self._started:
            return self._tool_catalog
        config = self._load_config()
        servers = config.get(self.server_config_key, {})
        if not isinstance(servers, dict):
            self._tool_catalog = {}
            self._started = True
            return self._tool_catalog

        for server_name, server_config in servers.items():
            if not isinstance(server_config, dict):
                continue
            process = self._start_server(server_name, server_config)
            initialize = self._send_jsonrpc(
                process,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
            if "error" in initialize:
                raise RuntimeError(f"initialize failed for {server_name}: {initialize['error']}")
            listed = self._send_jsonrpc(
                process,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            if "error" in listed:
                raise RuntimeError(f"tools/list failed for {server_name}: {listed['error']}")
            for tool in listed.get("result", {}).get("tools", []):
                tool_name = tool.get("name")
                if not tool_name:
                    continue
                self._tool_catalog[tool_name] = {
                    "name": tool_name,
                    "description": tool.get("description", ""),
                    "inputSchema": tool.get("inputSchema", {"type": "object", "properties": {}}),
                    "mcp_server": server_name,
                }
            for method, catalog, result_key, identity_key in (
                ("resources/list", self._resource_catalog, "resources", "uri"),
                ("prompts/list", self._prompt_catalog, "prompts", "name"),
            ):
                response = self._send_jsonrpc(
                    process,
                    {"jsonrpc": "2.0", "id": 3, "method": method, "params": {}},
                )
                if "error" in response:
                    continue
                for metadata in response.get("result", {}).get(result_key, []):
                    identifier = metadata.get(identity_key)
                    if identifier:
                        catalog[identifier] = {**metadata, "mcp_server": server_name}
        self._started = True
        return self._tool_catalog

    def discover_tools(self) -> dict[str, dict[str, Any]]:
        return self.start()

    def discover_resources(self) -> dict[str, dict[str, Any]]:
        self.start()
        return self._resource_catalog

    def discover_prompts(self) -> dict[str, dict[str, Any]]:
        self.start()
        return self._prompt_catalog

    def _send_to_server(
        self, server_name: str, request: dict[str, Any], server_config_key: str | None = None
    ) -> dict[str, Any]:
        if not self._started:
            self.start()
        process = self._processes.get(server_name)
        if process is None:
            config_key = server_config_key or self.server_config_key
            config = self._load_config().get(config_key, {}).get(server_name)
            if not isinstance(config, dict):
                raise KeyError(f"MCP server '{server_name}' is not configured")
            process = self._start_server(server_name, config)
            initialized = self._send_jsonrpc(
                process,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
            if "error" in initialized:
                raise RuntimeError(f"initialize failed for {server_name}: {initialized['error']}")
        return self._send_jsonrpc(process, request)

    def read_resource(self, uri: str, *, server_name: str | None = None) -> dict[str, Any]:
        if not self._started:
            self.start()
        owner = server_name or self._resource_catalog.get(uri, {}).get("mcp_server")
        if owner is None:
            raise KeyError(f"MCP resource '{uri}' not found")
        response = self._send_to_server(
            owner,
            {"jsonrpc": "2.0", "id": 90, "method": "resources/read", "params": {"uri": uri}},
        )
        if "error" in response:
            raise RuntimeError(response["error"].get("message", str(response["error"])))
        return response.get("result", {})

    def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        server_name: str | None = None,
    ) -> dict[str, Any]:
        if not self._started:
            self.start()
        owner = server_name or self._prompt_catalog.get(name, {}).get("mcp_server")
        if owner is None:
            raise KeyError(f"MCP prompt '{name}' not found")
        response = self._send_to_server(
            owner,
            {
                "jsonrpc": "2.0",
                "id": 91,
                "method": "prompts/get",
                "params": {"name": name, "arguments": arguments or {}},
            },
        )
        if "error" in response:
            raise RuntimeError(response["error"].get("message", str(response["error"])))
        return response.get("result", {})

    def build_agent_tool_registry(self) -> dict[str, dict[str, Any]]:
        tools = self.discover_tools()
        registry: dict[str, dict[str, Any]] = {}
        for tool_name, tool_data in tools.items():
            server_name = tool_data["mcp_server"]

            def _call_tool(
                arguments: dict[str, Any] | None = None,
                *,
                tool_name: str = tool_name,
                server_name: str = server_name,
                **kwargs: Any,
            ) -> dict[str, Any]:
                payload = dict(arguments or {})
                payload.update(kwargs)
                return self.call_tool(tool_name, payload, server_name=server_name)

            registry[tool_name] = {
                "description": tool_data.get("description", ""),
                "parameters": tool_data.get("inputSchema", {"type": "object", "properties": {}}),
                "mcp_server": server_name,
                "callable": _call_tool,
            }
        return registry

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        server_name: str | None = None,
    ) -> dict[str, Any]:
        if not self._started:
            self.start()
        if server_name is None:
            server_name = self._tool_catalog.get(tool_name, {}).get("mcp_server")
        if server_name is None:
            available = ", ".join(sorted(self._tool_catalog))
            raise KeyError(f"MCP tool '{tool_name}' not found. Available: {available}")

        if server_name not in self._processes:
            config = self._load_config().get(self.server_config_key, {}).get(server_name)
            if not isinstance(config, dict):
                raise KeyError(f"MCP server '{server_name}' is not configured")
            self._start_server(server_name, config)
            self._send_jsonrpc(
                self._processes[server_name],
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )

        response = self._send_jsonrpc(
            self._processes[server_name],
            {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments or {}},
            },
        )
        if "error" in response:
            error = response["error"]
            payload = error.get("data") if isinstance(error, dict) else None
            if isinstance(payload, dict):
                return payload
            raise RuntimeError(error.get("message") if isinstance(error, dict) else str(error))

        result = response.get("result", {})
        if isinstance(result, dict) and "structuredContent" in result:
            return result["structuredContent"]
        if isinstance(result, dict) and "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if isinstance(item, dict) and "text" in item:
                    try:
                        parsed = json.loads(item["text"])
                    except (TypeError, json.JSONDecodeError):
                        return {"text": item["text"]}
                    return parsed
        return result

    def close(self) -> None:
        for process in list(self._processes.values()):
            if process.poll() is None:
                process.stdin.close() if process.stdin else None
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        self._processes.clear()
        self._started = False
