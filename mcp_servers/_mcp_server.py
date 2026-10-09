from __future__ import annotations

import json
import sys
from typing import Any, Callable


class MCPJsonServer:
    """Minimal JSON-RPC MCP server for stdio transport."""

    def __init__(
        self,
        server_name: str,
        tools: dict[str, dict[str, Any]],
        *,
        resources: dict[str, dict[str, Any]] | None = None,
        prompts: dict[str, dict[str, Any]] | None = None,
    ):
        self.server_name = server_name
        self.tools = tools
        self.resources = resources or {}
        self.prompts = prompts or {}

    @staticmethod
    def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in metadata.items() if key not in {"func", "read", "get"}}

    def _tool_metadata(self, tool_name: str) -> dict[str, Any]:
        metadata = self.tools[tool_name]
        return {
            "name": metadata["name"],
            "description": metadata["description"],
            "inputSchema": metadata["inputSchema"],
        }

    def _dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        method = message.get("method")
        request_id = message.get("id")

        if method == "initialize":
            capabilities: dict[str, Any] = {"tools": {"listChanged": False}}
            if self.resources:
                capabilities["resources"] = {"listChanged": False, "subscribe": False}
            if self.prompts:
                capabilities["prompts"] = {"listChanged": False}
            return {
                "protocolVersion": "2025-06-18",
                "capabilities": capabilities,
                "serverInfo": {"name": self.server_name, "version": "1.0.0"},
            }

        if method == "tools/list":
            return {"tools": [self._tool_metadata(name) for name in self.tools]}

        if method == "resources/list":
            return {
                "resources": [
                    self._public_metadata(resource)
                    for resource in self.resources.values()
                ]
            }

        if method == "resources/read":
            uri = message.get("params", {}).get("uri")
            resource = self.resources.get(uri)
            if resource is None:
                raise KeyError(f"Unknown resource: {uri}")
            text = resource["read"]()
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": resource.get("mimeType", "text/plain"),
                    "text": str(text),
                }]
            }

        if method == "prompts/list":
            return {
                "prompts": [
                    self._public_metadata(prompt)
                    for prompt in self.prompts.values()
                ]
            }

        if method == "prompts/get":
            params = message.get("params", {})
            name = params.get("name")
            prompt = self.prompts.get(name)
            if prompt is None:
                raise KeyError(f"Unknown prompt: {name}")
            arguments = params.get("arguments") or {}
            return prompt["get"](arguments)

        if method == "tools/call":
            params = message.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            if tool_name not in self.tools:
                raise KeyError(f"Unknown tool: {tool_name}")
            func = self.tools[tool_name]["func"]
            result = func(**arguments)
            is_error = isinstance(result, dict) and result.pop("_mcp_is_error", False)
            structured_result = result.pop("structuredContent", result) if is_error else result
            payload = {
                **({"isError": True} if is_error else {}),
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(structured_result, ensure_ascii=False, indent=2),
                    }
                ],
                "structuredContent": structured_result,
            }
            return payload

        if method == "ping":
            return {}

        raise NotImplementedError(f"Unsupported MCP method: {method}")

    def run(self) -> None:
        buffer = b""
        while True:
            chunk = sys.stdin.buffer.read(1)
            if not chunk:
                break
            buffer += chunk
            if chunk == b"\n":
                continue
            if b"\r\n\r\n" in buffer:
                header_end = buffer.index(b"\r\n\r\n")
                headers_block = buffer[:header_end].decode("utf-8", errors="replace")
                body_start = header_end + 4
                content_length = 0
                for line in headers_block.split("\r\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        if key.strip().lower() == "content-length":
                            content_length = int(value.strip())
                            break
                if content_length <= 0:
                    continue
                if len(buffer) - body_start >= content_length:
                    body = buffer[body_start : body_start + content_length]
                    buffer = buffer[body_start + content_length :]
                    request = json.loads(body.decode("utf-8"))
                    try:
                        response = self._dispatch(request)
                        response_payload = {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": response,
                        }
                    except Exception as exc:  # pragma: no cover
                        response_payload = {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "error": {
                                "code": -32603,
                                "message": str(exc),
                            },
                        }
                    payload = json.dumps(response_payload, ensure_ascii=False).encode("utf-8")
                    stdout = (
                        b"Content-Length: " + str(len(payload)).encode("utf-8") + b"\r\n\r\n" + payload
                    )
                    sys.stdout.buffer.write(stdout)
                    sys.stdout.buffer.flush()
            elif b"Content-Length" in buffer:
                # Let the loop collect the full header body before parsing.
                continue

    def __call__(self, message: dict[str, Any]) -> dict[str, Any]:
        return self._dispatch(message)
