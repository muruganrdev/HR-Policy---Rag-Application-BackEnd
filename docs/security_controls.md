# Week 8 — Least Privilege & Output Validation

**Production flow:** `app/agent.py` calls the existing `app/security.py`
authorization helpers before dispatch, validates and minimizes each tool result
before storing it in Agent state, frames every model request with explicit
untrusted-data boundaries, and validates the final answer before returning it.
Direct/indirect injection unit scenarios also retain an isolated guarded harness;
separate tests exercise the production `run_agent()` path.

## 1. Least-privilege model

### Available Tools
The HR employee system defines five deterministic tools, each with exactly one bounded responsibility:
1. `get_employee_data`: Queries the SQLite database for a single employee's records (by ID or name).
2. `get_department_employees`: Queries SQLite for the roster of employees assigned to a given department.
3. `get_employees_by_manager`: Queries SQLite for direct reports of a given manager.
4. `lookup_annual_leave_policy`: Queries ChromaDB / HR PDF policy chunks for annual leave carry-over and encashment evidence in a specific jurisdiction.
5. `calculate_annual_leave_disposition`: Computes numerical carry-over, encashable, and lapsed days given numeric balance and policy limits.

### Capability Boundaries & Why Each Tool Exists
Each tool exists solely to provide factual or computational evidence for specific classes of HR queries:
- **Employee fact retrieval** requires access to personal employee records but never policy chunks or leave arithmetic.
- **Department/Manager queries** require organizational roster data but do not need sensitive personal fields (e.g. salary, personal leave balances).
- **Policy queries** require authoritative statutory or company rules from HR policy documents, requiring no employee database access.
- **Leave disposition calculations** require numeric inputs derived from validated employee facts and validated policy limits, operating purely deterministically.

### Capability Mapping (Minimum Required Tool Set)
The authorization helper computes and the production dispatcher enforces the
following task-scoped minimum capability set:

| Question Type | Allowed Capability | Tools Authorized |
| :--- | :--- | :--- |
| Employee fact (salary, location, email, etc.) | Employee fact lookup | `get_employee_data` |
| Department roster | Department listing | `get_department_employees` |
| Manager reports | Manager direct reports | `get_employees_by_manager` |
| Policy rule (carry-over limit, encashment limit) | Policy evidence lookup | `lookup_annual_leave_policy` |
| Employee vs Policy comparison | Employee fact + Policy lookup | `get_employee_data`, `lookup_annual_leave_policy` |
| Leave disposition | Employee fact + Policy lookup + Arithmetic | `get_employee_data`, `lookup_annual_leave_policy`, `calculate_annual_leave_disposition` |

Questions requiring only policy information are strictly prohibited from invoking employee data tools. Conversely, questions requiring pure employee facts are prohibited from accessing policy tools.

---

## 2. Tool allowlisting

### Registry
All available tools are registered in `TOOLS` in `app/agent.py` as explicit `ToolSpec` definitions containing the canonical tool name, descriptive usage guidance, and the backing callable.

### Dispatcher
All tool calls pass through the centralized dispatcher `execute_tool(tool_name: str, arguments: dict[str, Any])`. Tool calls cannot execute arbitrarily or bypass this entry point.

### Unknown-Tool Rejection
Before any tool execution or database interaction occurs, the dispatcher verifies that `tool_name` is present in `TOOLS`. If an unauthorized or fabricated tool name (such as `secret_tool` or `delete_employee`) is invoked, the dispatcher immediately raises a `ValueError` without executing any underlying logic.

---

## 3. Argument validation

`execute_tool()` invokes `validate_tool_call()` before dispatch. In addition to
shape and task scope, arguments are grounded in the current SQLite employee data
or the supported jurisdiction enum. A well-formed employee name/ID explicitly
requested by the user is allowed one scoped lookup even when no row exists; the
tool returns a validated `found: false` observation, and no employee data is
exposed.

- **Employee ID**:
  - Must be a non-empty string.
  - Must match the exact 3-digit pattern (`r"^\d{3}$"`).
  - Malformed strings, non-numeric values, empty strings, and SQL injection strings (e.g., `DROP TABLE employees`) are rejected.
  - If a task-scoped employee authorization allowlist exists, IDs outside the authorized set are rejected with `PermissionError`.
- **Employee Name**:
  - Must be a non-empty string.
  - When constrained by task authorization, must match the authorized employee name.
- **Department Name**:
  - Must be a non-empty string.
  - Empty or whitespace-only inputs are rejected with `ValueError`.
- **Manager Name**:
  - Must be a non-empty string.
  - Empty or whitespace-only inputs are rejected with `ValueError`.
- **Jurisdiction**:
  - Must match the supported `Jurisdiction` enum (`Jurisdiction.INDIA`).
  - Unsupported values (e.g., `"MARS"`, `"US"`) are strictly rejected.

---

## 4. Tool-result validation

After a tool returns, `run_agent()` invokes `validate_tool_result()` before
committing anything to Agent state:

- **Employee Result Validation**:
  - Must be a dictionary containing required schema fields (`employee_id`, `employee_name`, `department`, `designation`, `annual_salary`, `leave_balance`, `jurisdiction`).
  - `employee_id` must match the 3-digit pattern.
  - Numeric fields (`annual_salary`, `leave_balance`) must be finite, non-null, and non-negative numbers. Malformed values (e.g., `"not-a-number"`, `None`, or negative values) fail validation with `SecurityValidationError`.
  - Jurisdiction must match `Jurisdiction.INDIA`.
- **Policy Result Validation**:
  - Result structure must contain `jurisdiction`, `policy_area`, and structured `results` chunks with non-empty `source`, non-negative integer `chunk_index`, and string `content`.
- **Calculation Result Validation**:
  - Must contain `carryover_days`, `encashable_days`, and `lapsed_days`.
  - All values must be numeric, finite, and non-negative.
  - If authoritative inputs are provided, the calculation results are verified against the mathematical invariants:
    - $\text{carryover} = \min(\text{balance}, \text{carry\_limit})$
    - $\text{encashable} = \min(\text{balance}, \text{encash\_limit})$
    - $\text{lapsed} = \max(\text{balance} - \text{carry\_limit}, 0)$
  - Contradictory calculation results are rejected with `SecurityValidationError`.

---

## 5. Output validation

### Field Minimization
Employee records in SQLite store extensive personal data (salary, email, phone, location, tenure, manager, leave balances, work mode). Before results enter Agent state or a later model prompt, `run_agent()` calls `minimize_tool_result`; a salary-only query retains the employee name and salary, not email, manager, tenure, or leave data. Disposition queries retain the internal employee ID, leave balance, and jurisdiction needed for the validated calculation.

### Calculation Grounding & Contradiction Detection
Before `run_agent()` returns its API result, it calls `validate_final_answer` with the authorized tools/entities and any authoritative calculation:
- Answers addressing calculated leave disposition are checked against authoritative calculation results.
- If authoritative calculation outputs indicate `carryover_days = 10.0`, any final answer stating a contradictory value (such as `"20 days can be carried over"`) is flagged with `calculation_answer_mismatch` and rejected.
- Answers containing raw unrequested employee fields or unauthorized employee IDs are detected and replaced with a safe refusal response.

---

## 6. Security tests

All tests were executed against `tests/test_security_controls.py` and `tests/test_prompt_injection.py`:

```powershell
.\venv\Scripts\python -m pytest tests/test_security_controls.py tests/test_prompt_injection.py -q
```

### Results Summary
- **31 / 31** tests passed in `test_security_controls.py`
- **9 / 9** tests passed in `test_prompt_injection.py`
- **Total: 40 / 40 passing security tests**

### Specific Test Coverage
1. Unknown-tool tests reject `secret_tool` and `delete_employee` before callable dispatch; a production-path test verifies no tool callable is reached.
2. `test_invalid_employee_arguments_are_rejected`: Rejects empty string, SQL injection strings, and invalid numeric employee IDs.
3. `test_valid_employee_lookup_argument_is_accepted`: Accepts valid 3-digit employee ID `"003"`.
4. `test_invalid_department_and_manager_arguments_are_rejected`: Rejects empty department and manager arguments.
5. `test_invalid_jurisdiction_is_rejected`: Rejects invalid jurisdiction `"MARS"`, accepts `Jurisdiction.INDIA`.
6. `test_malformed_employee_result_is_rejected`: Rejects non-numeric salary `"not-a-number"` and null leave balance `None`.
7. `test_malformed_calculation_results_are_rejected`: Rejects missing calculation keys, non-numeric strings, and negative values.
8. `test_malformed_policy_result_is_rejected`: Rejects unsupported jurisdictions and malformed policy chunk content.
9. `test_calculation_result_is_validated_against_authoritative_inputs`: Validates calculation outputs against ground truth inputs and catches contradictions.
10. `test_employee_field_minimization_keeps_only_requested_value`: Verifies only requested salary field is retained.
11. `test_policy_question_gets_no_employee_capability`: Confirms policy questions are isolated from employee tools.
12. `test_salary_question_does_not_get_policy_capability`: Confirms employee questions do not receive policy or calculation tools.
13. `test_capability_sets_match_question_types`: Confirms exact minimal capability mappings for department, manager, and disposition questions.
14. `test_final_answer_rejects_calculation_contradiction`: Detects and rejects final answers contradicting calculation outputs.
15. Production Agent tests cover pre-dispatch rejection, grounded ID/jurisdiction checks, malformed employee/policy/calculation results, field minimization, final contradiction rejection, and legitimate employee/policy/disposition paths.

---

## 7. Production vs Harness Coverage

**Production-integrated:** Registered-tool allowlisting, task-scoped capability and entity checks, database grounding for IDs/names/departments/managers, jurisdiction validation, tool-result schemas, calculation input/output grounding, result minimization, untrusted request/result framing, and final-answer validation.

**Harness-only:** The `GuardedChat` injection experiment adds a test-scoped authorization boundary and reports attack provenance. It supplements, but does not replace, production checks. The harness-only provenance reporting is not a production control. Tests do not prove protection against every novel or obfuscated multi-turn injection.

**Residual limitation:** Final-answer checks use deterministic field and numeric-pattern validation; they are not general semantic verification or formal proof of every natural-language claim.

---

## 8. Security Test Coverage

These are isolated test cases, not production attack rates. The test suite
passed all covered rejection expectations; see the integration boundary above.

| Category | Cases | Expected behavior |
| :--- | ---: | :--- |
| Unknown tool allowlisting | 2 | `secret_tool` and `delete_employee` rejected before dispatch |
| Invalid argument validation | 6 | 6 rejected by the authorization helper |
| Malformed result validation | 7 | 7 rejected (2 employee, 2 policy, 3 calculation) |
| Unauthorized capability | 2 | 2 rejected by the scoped authorization helper |
| Output validation | 2 | 2 rejected or minimized as expected |


---

## 9. OWASP LLM Top 10 Mapping

This is an evidence map, not a claim of comprehensive OWASP protection. Status
reflects the integrated production checks and their remaining coverage limits.

| # | OWASP Category | Status | Evidence and boundary |
|---|---|---|---|
| LLM01 | Prompt Injection | Partially addressed | Production requests frame the user task and all tool results as untrusted; production direct and indirect injection tests verify scope and dynamic next-tool behavior. Novel/obfuscated multi-turn attacks are not exhaustively covered. |
| LLM02 | Insecure Output Handling | Partially addressed | Production final answers are checked against task scope and authoritative calculation results; deterministic patterns do not provide general natural-language semantic validation. |
| LLM03 | Training Data Poisoning | Not evaluated | No training-data provenance or poisoning evaluation is present. |
| LLM04 | Model Denial of Service | Demonstrated | The Agent enforces iteration, token, cost, and wall-clock budgets. This does not evaluate external volumetric denial of service. |
| LLM05 | Supply Chain Vulnerabilities | Not evaluated | Dependency provenance and supply-chain auditing are outside this evaluation. |
| LLM06 | Sensitive Information Disclosure | Partially addressed | Production tool results are minimized before entering state or subsequent prompts; broader side-channel and all-output disclosure testing is not performed. |
| LLM07 | Insecure Plugin Design | Demonstrated | The production dispatcher validates the tool registry and task authorization before invoking a callable; argument schemas and live-data grounding are also enforced. |
| LLM08 | Excessive Agency | Partially addressed | Production dispatch enforces question-scoped capabilities and entity limits. The intent-to-capability mapping remains heuristic and is not a general authorization policy engine. |
| LLM09 | Overreliance | Partially addressed | The Agent prompts for observed-data grounding and the evaluator checks benchmark answer phrases; this is not comprehensive factuality measurement. |
| LLM10 | Model Theft | Not evaluated | Model access control and extraction resistance are outside this evaluation. |

**Summary:** Demonstrated: LLM04, LLM07. Partially addressed: LLM01, LLM02,
LLM06, LLM08, LLM09. Not evaluated: LLM03, LLM05, LLM10.
