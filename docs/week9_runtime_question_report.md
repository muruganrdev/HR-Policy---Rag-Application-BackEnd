# Week 9 MCP Runtime Question Report

Runtime verification was executed against the local stdio implementation on 2026-10-08. The fix was limited to department intent/argument scoping, Agent completion from validated department results, and tests; MCP server/client/gateway protocol code was not changed. The questions were run through the real API route and Ollama-backed Agent, with direct gateway calls used to distinguish server behavior from Agent routing.

## Current Configuration and Discovery

The Agent is configured with one stdio front door: `mcp_gateway`, from [.vscode/mcp.json](../.vscode/mcp.json). The gateway dynamically discovers two configured backends, `hris_server` and `hr_policy_server`.

The Agent-facing `tools/list` catalog exposes these nine tools, each attributed to the gateway front door:

| Discovered tool | Backend owner |
|---|---|
| `get_department_employees` | `hr_policy_server` |
| `get_employee_data` | `hr_policy_server` |
| `get_employees_by_manager` | `hr_policy_server` |
| `lookup_annual_leave_policy` | `hr_policy_server` |
| `hris_get_department_roster` | `hris_server` |
| `hris_get_employee_grade_band` | `hris_server` |
| `hris_get_employee_leave_balance` | `hris_server` |
| `hris_get_employee_snapshot` | `hris_server` |
| `hris_get_manager_team` | `hris_server` |

The configured front door is the gateway. The regression check runs the live Agent internally without exposing the ten questions in this Markdown report. A separate gateway-backed Agent regression verifies the MCP department tool, result validation, and security boundary. Discovery and protocol handling were unchanged.

The Agent validates a proposed tool call before dispatch in [`execute_tool`](../app/agent.py#L893) via [`validate_tool_call`](../app/security.py#L440). The gateway separately checks token scopes in [`_call_tool`](../mcp_servers/gateway_server.py#L116) before its backend client call.

## Engineering Department Investigation

### Direct MCP Verification

A direct `tools/call` was sent through the configured gateway using the exact discovered tool and schema:

```json
{"name":"hris_get_department_roster","arguments":{"department_name":"Engineering"}}
```

The gateway returned `structuredContent` with `department="Engineering"`, `count=2`, and employees `Neha Iyer` (`003`) and `Arjun Menon` (`004`). These exact names and values match `app.tools.get_department_employees("Engineering")` against SQLite. The protocol response included both JSON text content and the same `structuredContent`. Therefore the MCP gateway, HRIS routing, HRIS tool, and database result work for this call.

### Actual Agent Trace

```text
Question: Who works in the Engineering department?
Route: agent
Selected action: get_department_employees
Arguments: {"department_name":"Engineering"}
Observation: {"status":"success","result":{"department":"Engineering","count":2,"employees":[{"employee_name":"Neha Iyer","designation":"Software Engineer"},{"employee_name":"Arjun Menon","designation":"Senior Software Engineer"}]}}
Final: Neha Iyer and Arjun Menon work in Engineering.
```

The unassisted model selected the local tool. A separate gateway-backed Agent regression selected `hris_get_department_roster` with the same argument and verified successful `tools/call`, observation, and final answer.

### Root Cause

The original failure was **security authorization**, not discovery, argument shape, backend execution, or result schema. The shared department-intent matcher now recognizes natural roster wording and feeds the existing `department_roster` capability. Discovered names containing `department` or `roster` receive that capability only when department intent is present. Department arguments remain grounded to the extracted department and checked against SQLite.

1. `hris_get_department_roster` is discovered with required `department_name: string` and belongs to `hris_server` behind `mcp_gateway`.
2. The model instead selects local `get_department_employees` with the correct argument `{"department_name":"Engineering"}`.
3. Before the fix, `minimum_tools_for_question` missed “Who works in the Engineering department?” and left `minimum_tools`, `allowed_tools`, and `allowed_department_names` empty.
4. The updated `_DEPARTMENT_QUERY` recognizes “who works in”, “who is in”, “which employees work in”, and list/show employee forms. It grants the existing `department_roster` capability and extracts `Engineering` into `allowed_department_names`.
5. `validate_tool_call`, called before execution by `execute_tool`, still checks registration, task authorization, and that the requested department exists in SQLite. Both `get_department_employees` and discovered `hris_get_department_roster` are authorized for this intent; unrelated tools remain unauthorized.
6. The Agent stores the validated department result for either supported tool name and deterministically renders the roster answer from that result.

A direct `validate_tool_result("hris_get_department_roster", result)` and the local department result validator both accept the structure (`department`, integer `count`, and `employees` list). Result validation was not the original cause. Department state storage now handles both the local and MCP tool names.

### A–I Findings

| Question | Finding |
|---|---|
| A. Correct MCP tool discovered? | Yes, `hris_get_department_roster`. |
| B. Correct MCP tool selected in the unassisted live run? | No; it selected local `get_department_employees`. The gateway-backed Agent regression separately selected and executed the MCP tool. |
| C. Correct argument sent? | Yes, `department_name=Engineering`; the direct MCP call used the discovered schema. |
| D. Did MCP server return Engineering employees? | Yes, direct gateway call returned Neha Iyer and Arjun Menon. |
| E. Did security reject the result? | Before the fix it rejected the proposed tool call; after the fix it authorizes local and MCP roster capabilities for department intent. |
| F. Did final-answer validation reject? | Before the fix, it rejected `unauthorized_tool_execution`; after the fix, the live final answer passes. |
| G. Did Agent use local instead? | Yes in the unassisted live run; the MCP alternative is now covered by a gateway-backed Agent test. |
| H. Is discovered name different? | No; exact expected name is present. |
| I. Is result schema incompatible? | No. Both MCP and local department result validators accept the returned structure. |

## Other Runtime Details

### Test 4: Manager Data

SQLite and direct backend data show Deepak Sharma has one report: Priya Nair (`005`), Product, Product Manager. The live Agent's local manager tool returned `count=1` and that employee. The Agent then called its model final-answer path; it failed with `Final answer generation did not return a valid final answer`. This is an Agent completion/model-output failure, not an MCP or database failure.

### Test 5: Exact Actual Answers

The first response from the 10-question run was:

> Based on the provided policy context, the annual leave policy for India is as follows:
>
> * All full-time employees are entitled to 20 working days of annual leave per calendar year (Policy Text: 2. Annual Leave (Vacation Leave)).
> * Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week (Policy Text: 2. Annual Leave (Vacation Leave)).
> * Annual leave accrues at a rate of 1.67 days per month of service (Policy Text: 2. Annual Leave (Vacation Leave)).
> * Unused annual leave of up to 10 days may be carried over to the next calendar year. Any balance exceeding 10 days will lapse on December 31st (Policy Text: 2. Annual Leave (Vacation Leave)).
> * Employees wishing to encash unused leave must submit a request to HR by November 30th. A maximum of 5 days may be encashed per calendar year (Policy Text: 2. Annual Leave (Vacation Leave)).
> * Annual leave must be applied at least 5 working days in advance through the HR portal. The direct manager must approve leave requests within 2 working days of submission (Policy Text: 2. Annual Leave (Vacation Leave)).
>
> Additionally, employees are entitled to all gazetted public holidays as declared by the Government of India (Policy Text: 6. Public Holidays and Policy Text: 8. Public Holidays).

A separate real repeat request returned a different answer:

> Based on the provided policy context, the answer is:
>
> * All full-time employees are entitled to 20 working days of annual leave per calendar year (Policy Text: Chunk 2, Policy Text: 2. Annual Leave (Vacation Leave))
> * Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week (Policy Text: Chunk 2, Policy Text: 2. Annual Leave (Vacation Leave))
> * Employees are entitled to all gazetted public holidays as declared by the Government of India (Policy Text: Chunk 7, Policy Text: 6. Public Holidays)
> * Employees required to work on a public holiday will receive compensatory leave (Policy Text: Chunk 7, Policy Text: 6. Public Holidays)
> * Employees are entitled to all public holidays as declared by the Government of India and as published in the company's annual holiday calendar (Policy Text: Chunk 8, Policy Text: 8. Public Holidays)
> * Employees required to work on public holidays will receive a compensatory day off (Policy Text: Chunk 8, Policy Text: 8. Public Holidays)
>
> Note: The provided policy context does not contain any specific information on the annual leave policy for India, but it does mention that employees are entitled to all gazetted public holidays as declared by the Government of India.

Retrieved sources included `leave_policy.pdf` chunks 1, 2, 7, and 0, plus `working_hours_policy.pdf` chunk 8. The answer cites annual leave entitlement from chunk 2 but then says no specific annual-leave information exists; it also adds public-holiday information not responsive to the question. This is a RAG retrieval/answer-grounding issue, not HR Policy MCP execution.

### Test 6: Actual Sequence

The Agent used only local tool names, not MCP. This satisfies the conceptual data → policy → calculation → grounded-answer path:

1. `get_employee_data(employee_name="Priya Nair")` → employee `005`, `leave_balance=20.0`, `jurisdiction=INDIA`.
2. `lookup_annual_leave_policy(jurisdiction="INDIA")` → ChromaDB policy result, including `leave_policy.pdf` chunk 2: up to 10 days carry-over; excess lapses; max 5 days encashment.
3. `calculate_annual_leave_disposition(leave_balance=20.0, carry_over_limit=10.0, encashment_limit=5.0)` → `carryover_days=10.0`, `encashable_days=5.0`, `lapsed_days=10.0`.
4. Final answer: `10 days can be carried over, 5 days can be encashed, and 10 days lapse.`

The functional answer is supported; MCP integration was not exercised. This is counted PASS for the requested conceptual path, while remaining a gap in MCP usage.

### Test 7: Data Premise

SQLite lookup for Arjun Menon returned employee ID `004`, department Engineering, and annual salary `1200000.0`. The Agent's answer matches this record. The test expectation is corrected to the actual salary; the separate not-found regression now uses verified-missing `Ghost Employee`. Employee `999` remains the absent-ID case in Test 8.

### Test 9–10: Scope Probes

A direct call through the configured gateway to `hris_get_employee_leave_balance` returned `{"employee_id":"005","employee_name":"Priya Nair","leave_balance":20.0}`. The configured token permits this gateway-discovered tool.

The grade-band MCP tool remains available for discovery and invocation; its implementation is not gated by the removed capability-scope demonstration. The unassisted live question did not select that MCP tool, so it did not exercise that path.

## Existing Test Results

Pre-fix focused verification command:

```powershell
.\venv\Scripts\python.exe -m pytest -q tests/test_mcp_client.py tests/test_agent.py tests/test_security_controls.py tests/test_mcp_gateway.py tests/test_tools.py
```

Baseline result: **96 passed, 0 failed, 0 skipped, 2 warnings** in 31.19 seconds.

Post-fix focused command:

```powershell
.\venv\Scripts\python.exe -m pytest -q tests/test_mcp_client.py tests/test_mcp_gateway.py tests/test_agent.py tests/test_security_controls.py tests/test_tools.py tests/test_agent_completion.py tests/test_prompt_injection.py tests/test_short_term_conversation.py
```

Result: **136 passed, 0 failed, 0 skipped, 2 warnings** in 45.79 seconds. Warnings were a ChromaDB `asyncio.iscoroutinefunction` deprecation and a pytest cache permission warning. The new gateway-backed Agent roster test also passed in an immediate focused run (5 passed across that test plus four live-loop phrase variants).

Baseline full-suite result: **232 passed, 2 failed, 0 skipped, 9 warnings** in 223.38 seconds. The failures were `test_label_template_is_unassigned` and the missing `evaluation.run_judge_v3` module.

Post-fix full-suite command: ` .\venv\Scripts\python.exe -m pytest -q `

Post-fix result: **243 passed, 2 failed, 0 skipped, 9 warnings** in 273.04 seconds. The same two unrelated failures remain:

- `tests/test_blind_labeling.py::test_label_template_is_unassigned`: current label fixture contains non-null human labels.
- `tests/test_judge.py::test_v3_summary_formatting_keeps_disagreement_ids_separate_from_mode_counts`: `evaluation.run_judge_v3` module is missing.

These failures are outside MCP. Warnings included ChromaDB/Langfuse deprecations, Mem0 embedding deprecations, and pytest cache access warnings.

## Root Cause Summary and Minimal Fixes to Consider

- **Engineering roster (fixed):** expanded intent and department extraction; local and discovered roster tools share the existing narrow capability; the requested department remains DB-grounded; final roster text comes from the validated result.
- **MCP tool selection:** unassisted model runs still select local overlapping tools. The discovered MCP equivalent is authorized and covered with a gateway-backed Agent test, but deterministic selection of MCP tools in live prompts remains unproven.
- **Manager final answer (remaining FAIL):** the local manager result is valid, but current final generation returns an invalid model response. A deterministic answer path for `manager_result` remains a separate follow-up.
- **Policy question (remaining FAIL):** the router sends this query to RAG, not HR Policy MCP; repeated answers were inconsistent with the retrieved evidence. Routing and answer grounding remain unresolved.
- **Grade-band request (remaining FAIL):** the unassisted Agent selects local employee lookup rather than the protected MCP capability; therefore the denial does not reach the Agent in the live run. Direct gateway scope denial and no-backend-call tests pass.
- **Arjun expectation (corrected):** employee `004` exists with salary `1200000.0`; the unknown-name test uses verified-missing `Ghost Employee` instead.
