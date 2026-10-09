from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
EVIDENCE_DIR = ROOT / "evidence" / "week9_mcp"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def send_request(server_script: str, method: str, params: dict | None = None, request_id: int = 1):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    request_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    process = subprocess.Popen(
        [sys.executable, str(ROOT / server_script)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    framed = b"Content-Length: " + str(len(request_bytes)).encode("utf-8") + b"\r\n\r\n" + request_bytes
    stdout, stderr = process.communicate(framed)
    if process.returncode != 0:
        raise RuntimeError(f"{server_script} failed: {stderr.decode('utf-8', 'replace')}")
    if not stdout:
        raise RuntimeError(f"{server_script} returned no stdout for {method}")
    try:
        body_start = stdout.find(b"\r\n\r\n")
        body = stdout[body_start + 4 :] if body_start != -1 else stdout
        response = json.loads(body.decode("utf-8"))
        return response
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to parse response from {server_script}: {stdout!r}") from exc


if __name__ == "__main__":
    servers = [
        ("mcp_servers/hr_policy_server.py", "hr_policy_server"),
        ("mcp_servers/hris_server.py", "hris_server"),
    ]
    summary = {}
    for script, label in servers:
        init = send_request(script, "initialize", request_id=1)
        listed = send_request(script, "tools/list", request_id=2)
        summary[label] = {
            "initialize": init,
            "tool_count": len(listed.get("result", {}).get("tools", [])),
            "tools": listed.get("result", {}).get("tools", []),
        }
        if label == "hris_server":
            call = send_request(
                script,
                "tools/call",
                {"name": "hris_get_department_roster", "arguments": {"department_name": "Engineering"}},
                request_id=3,
            )
            summary[label]["department_roster_call"] = call
            snapshot = send_request(
                script,
                "tools/call",
                {"name": "hris_get_employee_snapshot", "arguments": {"employee_name": "Priya Nair"}},
                request_id=4,
            )
            summary[label]["employee_snapshot_call"] = snapshot

    (EVIDENCE_DIR / "server_tool_discovery.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total_tools = sum(item["tool_count"] for item in summary.values())
    summary_overview = {
        "before_mcp_tools": 5,
        "after_mcp_tools": total_tools,
        "discovery_delta": total_tools - 5,
        "servers": list(summary.keys()),
    }
    (EVIDENCE_DIR / "week9_tool_discovery_summary.json").write_text(
        json.dumps(summary_overview, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary_overview, ensure_ascii=False, indent=2))
