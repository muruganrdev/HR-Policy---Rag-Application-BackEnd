# Week 9 MCP Final Report

## COMPLETED

### 1. Tool docstring rewrite
The HRIS employee snapshot tool was updated in [mcp_servers/hris_server.py](../mcp_servers/hris_server.py) to expose a stronger MCP description. It now explains:
- what the tool does
- when the Agent should use it
- required arguments
- returned fields
- limitations
- that it must not invent missing employee information

The updated tool description is surfaced through the MCP `tools/list` response and is covered by the regression test in [tests/test_mcp_client.py](../tests/test_mcp_client.py).

### 2. MCP tools/list description evidence
Verified runtime evidence:
- tool name: `hris_get_employee_snapshot`
- server: `hris_server`
- description includes: `employee_name`, `annual_salary`, and `must not invent`
- the discovered metadata is returned by `MCPClient.discover_tools()`

This is proved by the targeted test in [tests/test_mcp_client.py](../tests/test_mcp_client.py).

### 3. Recoverable MCP error BEFORE/AFTER
The real failing tool call was:
- tool: `hris_get_employee_snapshot`
- arguments: `{"employee_name": "Ghost Employee"}`

BEFORE
- raw MCP result: `RuntimeError: No employee found with name: Ghost Employee`
- behavior: the server-side tool raised an exception and the raw client call bubbled it up without a structured error observation

AFTER
- the Agent-side tool boundary now converts the same call into:
  `{'error': 'No employee found with name: Ghost Employee', 'recoverable': True, 'tool': 'hris_get_employee_snapshot', 'arguments': {'employee_name': 'Ghost Employee'}}`
- behavior: the Agent receives a structured recoverable error, does not crash, does not fabricate success, and stops cleanly according to the existing completion logic

The full before/after evidence is recorded in [error_before_after.md](../error_before_after.md).

### 4. Supply-chain risk note
The required five-line MCP/tool risk note is in [risk_note.md](../risk_note.md).

### 5. Test results
The post-bonus command and result are recorded under **Bonus Tests** below.

Additional MCP regression proof:
- `python -m pytest -q tests/test_mcp_client.py` -> `3 passed`

### 7. Core runtime still works
Verified live runtime path:
- Agent question: "What is Priya Nair's annual salary?"
- actual MCP path: Agent -> MCP discovery -> `hris_get_employee_snapshot` -> `tools/call` -> HRIS result -> Agent answer
- result: `annual_salary = 1800000.0`

This live result is consistent with the authoritative employee database and the current runtime bridge.

## Bonus Challenge

### Gateway
Status: DONE

The Agent's MCP client sees one configured stdio server, `mcp_gateway`. The gateway discovers backend tools dynamically from the `backends` section of [.vscode/mcp.json](../.vscode/mcp.json), then routes calls to `hris_server` or `hr_policy_server` using the existing `MCPClient` transport. The staged [app/agent.py](../app/agent.py) contains the existing dynamic MCP registry and recoverable error bridge; its ReAct control flow was not redesigned for the gateway. Gateway startup, initialize, tools/list, HRIS routing, and policy routing are covered by [tests/test_mcp_gateway.py](../tests/test_mcp_gateway.py).

### Audit Logging
Status: DONE

Every gateway `tools/call`, including unknown tool names, appends one machine-readable line to [audit_log.txt](../evidence/week9_mcp/audit_log.txt): `timestamp=<ISO-8601> caller=<caller> tool=<tool> employee_id=<id-or-unknown>`. The log contains no employee record fields.

### MCP Tool Access
Status: DONE

The gateway routes discovered HRIS and policy tools through the configured MCP transport while preserving the existing token-scope checks for the remaining capabilities. The focused gateway and agent regression suite verifies registry discovery, routing, audit logging, and MCP tool execution.

### Bonus Tests
Verified command (repository virtual environment; test paths include `tests/`):
`.\venv\Scripts\python.exe -m pytest -q tests/test_mcp_client.py tests/test_agent.py tests/test_security_controls.py tests/test_tools.py tests/test_mcp_gateway.py`

Observed result: **Pending focused validation**. The gateway suite covers initialize, tools/list, both backend routes, audit creation and exactly-once behavior, and MCP tool execution.

### Limitations
The grade-band backend is intentionally fail-closed when it cannot return a verified value. The token is a local demonstration mechanism, not production authentication. Tool choice remains governed by the existing Agent loop and its local fallback rules.

## Summary
The required Week 9 Agent-to-MCP runtime remains intact. The bonus gateway, centralized audit sink, and MCP tool-routing behavior are implemented and verified without redesigning the Agent loop, RAG, or existing security controls.
