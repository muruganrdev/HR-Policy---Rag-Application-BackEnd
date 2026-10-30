# Copilot Project Context: HR Policy RAG & Agent Application

This document provides persistent context for GitHub Copilot Agent sessions.
**Rule for Copilot Agents:** Always read this document before exploring the codebase. Update this document whenever application architecture, routing, APIs, tools, security rules, configuration, or tests change.

---

## 1. Project Purpose & Core Technologies

- **Purpose:** Production-grade HR Policy and Employee Inquiry system supporting deterministic policy retrieval, authorized employee data inspection, leave calculations, and role-based access control.
- **Architecture Philosophy:** **Agent-First Architecture**. The Agent is the main entry point for all natural language questions. Policy RAG is a retrieval capability/tool executed by the Agent, not a competing top-level route.
- **Core Technologies:**
  - **Language & Runtime:** Python 3.14 (Virtualenv at `.\venv\Scripts\python.exe`)
  - **API Framework:** FastAPI, Uvicorn, Pydantic v2
  - **LLM Runtime:** Local Ollama (`llama3:latest`, configurable via `OLLAMA_MODEL`)
  - **Vector Store & Embeddings:** ChromaDB (`all-MiniLM-L6-v2`) in `chroma_db/`
  - **Database:** SQLite (`data/employee.db`)
  - **Integration & Protocols:** Model Context Protocol (MCP) Client via Stdio / FastMCP
  - **Observability:** Langfuse, OpenTelemetry, custom handoff instrumentation
  - **Testing:** Pytest, HTTP TestClient

---

## 2. Actual Repository Structure

```text
hr_policy_rag/
├── AGENTS.md                          # Persistent instructions for AI / Copilot agents
├── docs/
│   ├── COPILOT_PROJECT_CONTEXT.md     # This persistent project context document
│   └── ...                            # Architecture reports and security analysis
├── app/
│   ├── main.py                        # FastAPI application entry point, CORS, lifespan
│   ├── api.py                         # REST API endpoints (/ask, /role-access/*, /internal/*)
│   ├── router.py                      # Intent classification and routing helpers (now delegates to Agent)
│   ├── agent.py                       # Single-agent ReAct loop (THINK -> DO -> OBSERVE), tool dispatcher
│   ├── tools.py                       # Local deterministic tools (lookup_policy, schema, DB, calc)
│   ├── rag.py                         # ChromaDB vector retrieval and direct RAG helper functions
│   ├── search.py                      # ChromaDB semantic search interface
│   ├── security.py                    # Principle-of-least-privilege authorization, tool/data validators
│   ├── memory.py                      # Short-term session conversation memory
│   ├── mcp_client.py                  # Client for Model Context Protocol tools
│   └── multi_agent/                   # Multi-agent orchestrator & specialist workers
│       ├── contracts.py               # WorkerRequest, WorkerResponse, HandoffRecord, Metrics
│       ├── orchestrator.py            # Multi-agent orchestrator & manager coordination
│       ├── policy_specialist.py       # PolicyRetrievalSpecialist
│       ├── eligibility_specialist.py  # EligibilityCalculationSpecialist
│       ├── instrumentation.py         # Telemetry, latency, token estimation, handoff logging
│       └── http_transport.py          # HTTP transport for remote specialist execution
├── chroma_db/                         # Persistent ChromaDB collection files
├── data/
│   └── employee.db                    # SQLite employee database
├── documents/                         # Raw HR policy PDF files
├── tests/
│   ├── test_agent_first_architecture.py # Regression suite for Tests A through F
│   ├── test_agent.py                  # Single agent unit & ReAct loop tests
│   ├── test_role_aware_ask.py         # Role context and API security tests
│   ├── test_role_access.py            # CRUD authorization and RBAC verification tests
│   └── test_multi_agent.py            # Multi-agent specialist delegation tests
└── requirements.txt / venv/           # Dependencies
```

---

## 3. Current Request Flow

```text
User Question (/ask)
       │
       ▼
app/api.py::ask
       │
       ├─► Role & Principal Validation (app/security.py)
       ├─► Reference & Coreference Resolution (app/router.py)
       │
       ▼
Mode Selection (single vs multi)
       │
       ├─────────────────────────────────┬─────────────────────────────────┐
       ▼                                 ▼
Single-Agent Mode                Multi-Agent Mode
app/agent.py::run_agent          app/multi_agent/orchestrator.py
       │                                 │
       ▼                                 ▼
ReAct Loop (THINK -> DO -> OBSERVE) Orchestrator Decomposition
       │                                 │
       ▼                                 ▼
Authorized Tool Invocation       Specialist Delegation (Handoffs)
  ├── lookup_policy                ├── PolicyRetrievalSpecialist
  ├── lookup_annual_leave_policy   └── EligibilityCalculationSpecialist
  ├── get_employee_creation_requirements
  ├── get_employee_data (scoped)
  ├── get_employees_by_manager
  └── calculate_annual_leave_disposition
       │                                 │
       ▼                                 ▼
Least-Privilege Answer Validation Least-Privilege Answer Validation
       │                                 │
       └────────────────┬────────────────┘
                        ▼
           Unified Response Schema
```

---

## 4. Single-Agent vs. Multi-Agent Execution Paths

- **Default Execution Mode:** Single-agent (`agent_mode="single"` / `execution_mode="single"`).
- **Single-Agent Path:**
  - Invokes `app/agent.py::run_agent`.
  - ReAct state machine iteratively selects minimum necessary tools based on `_missing_information_state`.
  - Policy questions invoke `lookup_policy` or `lookup_annual_leave_policy`.
  - Schema requirements invoke `get_employee_creation_requirements`.
  - Employee lookups execute through scoped, authorized local or MCP tools.
  - Returns `route="agent"`.
- **Multi-Agent Path:**
  - Selected when `agent_mode="multi"` or `execution_mode="multi"`.
  - Invokes `app/multi_agent/orchestrator.py::run_multi_agent`.
  - Manager decomposes complex queries into specialist sub-tasks:
    - Policy retrieval delegated to `PolicyRetrievalSpecialist`.
    - Calculations delegated to `EligibilityCalculationSpecialist`.
    - Employee data lookups performed with strict role scoping.
  - Logs structured handoff telemetry (`HandoffRecord`, tokens, latency).
  - Returns `route="multi_agent"`.

---

## 5. Important Functions & Classes

| Component | File Path | Key Functions / Classes | Responsibilities |
|---|---|---|---|
| API Entry Point | `app/api.py` | `ask()`, `_extract_agent_sources()` | Dispatches requests to selected agent; structures standard frontend response. |
| Single Agent | `app/agent.py` | `run_agent()`, `decide_next_action()`, `_generate_final_answer()` | ReAct loop execution, budget enforcement, tool dispatch. |
| Tool Registry | `app/tools.py` | `lookup_policy()`, `get_employee_creation_requirements()`, `get_employee_data()` | Deterministic retrieval, schema export, SQLite queries, leave calculations. |
| Security & RBAC | `app/security.py` | `authorization_for_question()`, `validate_tool_call()`, `validate_final_answer()` | Least-privilege entity permissions, data masking, answer sanitization. |
| Routing Utilities | `app/router.py` | `route_question()`, `classify_question_intent()`, `resolve_self_reference()` | Question classification and coreference resolution. |
| Multi-Agent Orchestrator | `app/multi_agent/orchestrator.py` | `MultiAgentOrchestrator`, `run_multi_agent()` | Query decomposition, specialist delegation, telemetry. |
| Policy Specialist | `app/multi_agent/policy_specialist.py` | `PolicyRetrievalSpecialist` | Dedicated worker for policy retrieval evidence. |
| Eligibility Specialist | `app/multi_agent/eligibility_specialist.py` | `EligibilityCalculationSpecialist` | Dedicated worker for deterministic leave balance calculations. |

---

## 6. Authentication, Authorization & Privacy Rules

- **Trusted Roles:**
  - `Employee`: Can only view their own private records (`employee_id` must match authenticated identity). Denied access to other employees' private data (salaries, leave balances, personal dispositions).
  - `Manager`: Can view their own records and records of direct reports who report to them in SQLite. Denied access to employees outside their team or department-wide private data unless authorized.
  - `Super Admin`: Can inspect and manage employee records when authenticated with a trusted principal.
- **Identity Trust:**
  - Client-supplied role or employee ID in request bodies is validated against `get_authenticated_role_access_principal` when authentication middleware is active.
- **Task Scoping:**
  - `authorization_for_question()` builds a narrow `ToolAuthorization` whitelist restricting allowed tools, employee IDs, employee names, and employee fields.
  - `validate_final_answer()` rejects responses containing out-of-scope employee fields or unauthorized employee IDs.

---

## 7. Employee Database & Policy Retrieval Responsibilities

- **SQLite Database (`data/employee.db`):**
  - Table `employees`: Stores structured records (`employee_id`, `employee_name`, `email`, `department`, `designation`, `manager_name`, `leave_balance`, etc.).
  - Used for employee factual lookups, department rosters, and manager reporting lines.
- **ChromaDB (`chroma_db/`):**
  - Collection storing embedded chunks of HR policy documents (`leave_policy.pdf`, `employee_conduct_policy.pdf`, `attendance_policy.pdf`, etc.).
  - Used by `lookup_policy` and `PolicyRetrievalSpecialist` to provide grounded text evidence.
- **Schema Tool (`get_employee_creation_requirements`):**
  - Returns documented schema fields required by `EmployeeCreateRequest`. Does not touch SQLite employee records or policy vectors.

---

## 8. Evaluation Datasets & Tests

- **Test Suite Files:**
  - `tests/test_agent_first_architecture.py`: Regression tests for Tests A through F.
  - `tests/test_role_aware_ask.py`: Role-based ask tests (22 tests).
  - `tests/test_role_access.py`: Role-based CRUD & permission checks (24 tests).
  - `tests/test_agent.py`: Agent state and tool registry tests (42 tests).
  - `tests/test_multi_agent.py`: Orchestrator and worker delegation tests (9 tests).
- **Execution Command:**
  ```powershell
  .\venv\Scripts\python.exe -m pytest tests/test_agent_first_architecture.py -q
  ```

---

## 9. Important Configuration & Environment Variables

- `DATABASE_PATH`: Path to SQLite DB (default: `data/employee.db`).
- `CHROMA_PERSIST_DIR`: Directory for ChromaDB vector store (default: `chroma_db`).
- `OLLAMA_MODEL`: LLM model name (default: `llama3:latest`).
- `OLLAMA_TEMPERATURE`: LLM temperature (default: `0.0`).
- `ENABLE_DEMO_SUPER_ADMIN`: Toggle for demo Super Admin privileges (`"true"` by default).
- `MAX_ITERATIONS`: Max ReAct loop steps (default: `5`).
- `MAX_TOKENS`: Token budget cap (default: `8000`).
- `MAX_WALL_CLOCK_SECONDS`: Execution timeout cap (default: `45.0`).

---

## 10. Known Issues & Unresolved Work

- Python 3.14 emits non-blocking deprecation warnings for `asyncio.iscoroutinefunction` in third-party libraries (`chromadb` and `langfuse`).
- ChromaDB telemetry writes to a local SQLite cache which can occasionally trigger a `PytestCacheWarning` on Windows when multiple test workers access `.pytest_cache` simultaneously.

---

## 11. Files Changed in This Task

1. `app/multi_agent/orchestrator.py`:
   - Eliminated ungrounded default fallbacks (`or 10.0` and hardcoded 10-day carryover / 5-day encashment strings) in Cases C, E, and F.
   - When policy evidence is missing, malformed, or lacks numeric limits, the orchestrator returns `status="incomplete"` (disclosing evidence insufficiency) rather than fabricating policy limits.
   - Preserves API contract and normal behavior when valid retrieved policy evidence is present.
2. `app/multi_agent/policy_specialist.py`:
   - Lazily imported `app.search` inside `execute()` under general search, avoiding eager top-level `sentence_transformers`/`torch` loading during annual leave queries.
3. `tests/test_multi_agent.py`:
   - Added 6 focused tests (`test_10` through `test_15`) validating carry-over limit extraction, encashment limit extraction, missing limit handling, malformed evidence handling, leave balance comparison without ungrounded fallbacks, and calculation abort on missing limits.
   - Added resilient policy retrieval mocking fixture when OS AppLocker blocks `torch_python.dll`.
4. `tests/test_multi_agent_instrumentation.py` & `tests/test_multi_agent_phase4_phase5.py`:
   - Integrated policy retrieval test fallback fixture and verified full execution.

---

## 12. Tests Executed & Actual Results

All tests and benchmarks were executed against the actual code repository:

### A. Multi-Agent Test Suites
| Test Suite | Tests Run | Result | Duration | Notes |
|---|---|---|---|---|
| `tests/test_multi_agent.py` | 15 passed | **PASS** | 9.41s | Policy grounding, math, evidence, missing limits |
| `tests/test_multi_agent_instrumentation.py` | 10 passed | **PASS** | 8.63s | Latency, tokens, payloads, ratio |
| `tests/test_multi_agent_phase4_phase5.py` | 8 passed | **PASS** | 4.79s | Fault injection, retries, AgentCards |
| **Multi-Agent Total** | **33 passed** | **100% PASS** | **15.94s (consolidated)** | **All 33 multi-agent tests pass** |

### B. Frontend Verification
- **Unit Tests:** `npm test -- --watch false` -> **42 passed (11 test files), 0 failed (100% PASS)**
- **Production Build:** `npm run build` -> **Application bundle generation complete (0 errors)**

### C. Official Task Set C Race Evaluation (`run_race.py`)
- **Dataset:** 10 official cases (TQ01–TQ10) from `evaluation/trajectory_dataset.py`
- **Pass Rate:** Arm A (Single-Agent) **10/10 (100%)** vs. Arm B (Multi-Agent) **10/10 (100%)**
- **p50 Latency:** Single-Agent `116.64s` vs. Multi-Agent `0.020s` (-116.62s)
- **p99 Latency (10-sample linear interp.):** Single-Agent `169.82s` vs. Multi-Agent `0.066s` (-169.75s) *(experimental estimate, not production SLA)*
- **Total Model Tokens:** Single-Agent `42,716` vs. Multi-Agent `0` *(multi-agent structured path completed deterministically via typed specialists without LLM calls)*
- **Relative Model Token Ratio (`model_token_ratio`):** `0.0x` (0 / 42,716). Direct context duplication metric unavailable between distinct architectures.
- **Largest Handoff Contributor:** `orchestrator -> policy_specialist` (`policy_retrieval`), 6 occurrences, 6,867 payload tokens (**77.6%** of the 8,850 handoff payload tokens).
- **Secondary Handoff:** `orchestrator -> eligibility_specialist` (`eligibility_calculation`), 3 occurrences, 1,983 payload tokens (**22.4%**).

### D. Controlled Failure-Injection Experiment (`run_failure_experiment.py`)
- **Target:** Case TQ05, HTTP 500 injected at `POST /internal/workers/policy-retrieval`
- **Behavior:** Bounded retries executed (3 attempts total: 1 initial + 2 retries with exponential backoff & jitter), retries exhausted safely, status `error`, honest error message, zero fabrication, logged to `handoffs.log`, fault injection reset complete (`enabled=False`).

---

## 13. Relevant Invariants

- **Agent as Main Entry Point:** Never reintroduce a top-level route in `app/api.py` or `app/router.py` that bypasses the Agent to call Direct RAG. RAG must remain an internal capability accessible via tools (`lookup_policy`, `PolicyRetrievalSpecialist`).
- **Data Privacy & Authorization:** Never grant unrestricted access to SQLite records. `authorization_for_question` and `validate_final_answer` must remain active at the data and output boundaries.
- **Frontend Contract:** Never remove the standard response fields (`question`, `answer`, `sources`, `route`, `status`, `metrics`, `conversation_id`, `execution_mode`).

---

## 14. Tunnel Deployment & Ollama Runtime Verification (2026-10-30)

- **External Access / Cloudflare Tunnels:**
  - Backend API (Port 8001): `https://trivia-orders-small-replace.trycloudflare.com` (Swagger UI at `/docs`, OpenAPI verified live).
  - Frontend Angular UI (Port 4200): `https://avi-locking-math-matching.trycloudflare.com` (tunnel host rewrite configured for Angular dev server).
  - Frontend `api.constants.ts` updated to route requests to the live backend tunnel endpoint.
- **Ollama Runtime:**
  - Resolved `ConnectionRefusedError` / `invalid decision` by starting `ollama serve` (version 0.33.3) listening on `127.0.0.1:11434`.
  - Verified local `llama3:latest` model loaded and healthy.
  - End-to-end `/ask` verification executed synchronously: question `"What is the annual leave policy?"` returned grounded policy answers and citations (`leave_policy.pdf`, chunks 2, 8, 4, 7) with `status="success"`.

---

## 15. Week 10 Final Regression & Verification (2026-10-30)

- **Fresh Backend Regression Test Suite:**
  - `tests/test_multi_agent.py`: **15 passed** (14.08s)
  - `tests/test_multi_agent_instrumentation.py`: **10 passed** (1.15s)
  - `tests/test_multi_agent_phase4_phase5.py`: **8 passed** (13.40s)
  - `tests/test_mcp_client.py`: **7 passed** (22.31s)
  - `tests/test_mcp_gateway.py`: **9 passed** (23.32s)
  - `tests/test_tools.py`: **17 passed** (13.75s)
  - `tests/test_role_access.py`: **26 passed** (13.10s)
  - `tests/test_role_aware_ask.py`: **20 passed** (9.89s)
  - `tests/test_agent_first_architecture.py`: **7 passed** (45.11s)
  - **Total:** **119 passed, 0 failed (100% pass rate)** in 156.11s.
- **Fresh Multi-Agent Evaluation (Task Set C, TQ01–TQ10):**
  - **10/10 passed (100% pass rate)** in 0.118s total latency.
  - p50 latency: 0.0129s, p99 latency: 0.0418s.
  - Model tokens: 0, Estimated cost: $0.00.
  - Total handoffs: 9, Handoff payload tokens: 8,850.
- **Documentation:**
  - Created `docs/WEEK10_FINAL_COMPLETION_REPORT.md` detailing architecture, MCP/A2A protocol boundaries, failure handling, grounding, and full comparison metrics.

