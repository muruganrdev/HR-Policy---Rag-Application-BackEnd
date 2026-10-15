# Week 10 Phase 5 — A2A Bonus: AgentCard & Task Lifecycle Architecture Notes

This document provides the architectural analysis and task lifecycle mapping for the HR Policy Multi-Agent system under the **Agent-to-Agent (A2A)** specification.

---

## 1. Published AgentCard Metadata

The project includes discoverable AgentCard definitions implemented in [`app/multi_agent/agent_cards.py`](file:///c:/Local%20Disk%20D/Murugan%20Project/Projects/AI%20-%20Backend/HR%20Policy%20-%20Ask%20my%20documents/hr_policy_rag/app/multi_agent/agent_cards.py):

1. **`HR Policy Multi-Agent Orchestrator`** (`urn:agent:acme:hr-orchestrator`)
   - **Role:** Orchestrator / Dispatcher
   - **Skills:** `hr_intent_decomposition`, `specialist_delegation`, `answer_synthesis`
   - **Endpoints:** `POST /ask` (`agent_mode=multi`)
   - **Status:** *Proposed metadata card* (delegates in-process to specialist workers)
2. **`Policy Retrieval Specialist`** (`urn:agent:acme:policy-retrieval-specialist`)
   - **Role:** Specialist Worker
   - **Skills:** `policy_retrieval` (semantic search & authoritative policy lookup)
   - **Endpoints:** In-process / `POST /internal/workers/policy-retrieval`
   - **Status:** *Proposed metadata card*
3. **`Eligibility Calculation Specialist`** (`urn:agent:acme:eligibility-calculation-specialist`)
   - **Role:** Specialist Worker
   - **Skills:** `calculate_annual_leave_disposition` (deterministic leave arithmetic)
   - **Endpoints:** In-process contract
   - **Status:** *Proposed metadata card*

> **Compliance Disclosure:** These cards are clearly marked as **proposed metadata cards**. The current repository uses typed Python dataclass contracts and lightweight REST adapters rather than an asynchronous multi-node A2A streaming transport.

---

## 2. A2A Task Lifecycle State Mapping

The table below maps internal worker and orchestrator statuses to the official A2A task lifecycle:

| Internal Contract Status | A2A Lifecycle State | Description & Transition Trigger |
| :--- | :--- | :--- |
| `WorkerRequest` created | `submitted` | The orchestrator creates a typed `WorkerRequest` with correlation ID and enqueues execution. |
| In delegation execution | `in_progress` | Specialist worker receives payload, starts search or computation, and begins duration clock. |
| `WorkerStatus.SUCCESS` | `completed` | The specialist produced valid evidence or deterministic calculation; returned to orchestrator. |
| `WorkerStatus.ERROR` | `failed` | An unrecoverable internal exception or transport error occurred (e.g., HTTP 500 from policy worker). |
| `WorkerStatus.INCOMPLETE` (missing inputs) | `input_required` | The task cannot proceed because mandatory parameters are missing from the caller (e.g. employee leave balance or jurisdiction missing). |

### Critical Distinction: `failed` vs `input-required`

It is essential to distinguish infrastructure and execution failures from information-gap states:

- **`failed` (Service Failure):**  
  In the Phase 4 experiment, when the policy worker returned `HTTP 500 Internal Server Error`, the task transitioned to **`failed`**. The user query ("What is the annual leave carry-over limit under the policy?") contained all required information. The failure was caused by worker backend unavailability. The system must report this honestly as a system failure.
- **`input-required` (Missing Information):**  
  If a user asks *"Calculate my leave disposition"* but neither the employee identity nor leave balance is provided, the task transitions to **`input-required`**. The service is healthy, but execution cannot continue until the caller supplies the missing data.
- **Rule Enforced:** A service failure must **never** be reclassified as `input-required` to artificially suppress error rates or disguise system downtime.

---

## 3. Protocol Architecture: MCP vs. A2A vs. Plain REST

- **Two-Line Protocol Distinction:**
  1. **MCP** standardizes client-to-tool data access and resource querying, whereas **plain REST** provides point-to-point client-to-server request/response transport.
  2. In contrast, **A2A** coordinates peer or hierarchical agent-to-agent task delegation, capability negotiation, and multi-step lifecycle states.

The following matrix clarifies the distinct roles and boundaries of the protocols present in this architecture:

| Protocol / Layer | Primary Purpose | How It Is Used in This Project | Limitations / Boundaries |
| :--- | :--- | :--- | :--- |
| **Model Context Protocol (MCP)** | **Tool & Data Access:** Standardized client-server protocol enabling LLMs to safely query databases, files, and external APIs. | Used by `Single Agent` via `MCPClient` and `mcp_servers/gateway_server.py` to run `get_employee_data`, `lookup_annual_leave_policy`, etc. | Designed for agent-to-tool interactions, not high-level collaborative agent-to-agent delegation. |
| **Agent-to-Agent (A2A)** | **Agent Collaboration:** Protocol for peer-to-peer or hierarchical task distribution, capability negotiation, and task lifecycle tracking. | Represented via AgentCards (`agent_cards.py`) and worker contract lifecycle (`WorkerRequest` / `WorkerResponse`). | Full distributed wire protocol requires standardized streaming envelopes and external service discovery. |
| **Plain REST** | **Application Interface:** Synchronous request/response HTTP over standard endpoints. | Used by FastAPI (`POST /ask`) and the test worker endpoint (`POST /internal/workers/policy-retrieval`). | Lacks agent capability negotiation, task suspension/resumption, and multi-turn collaboration primitives of true A2A. |

---

## 4. Remaining Gaps to Full A2A Compliance

To achieve full production-grade A2A compliance in future iterations, the following capabilities would be required:

1. **Independent Process / Microservice Boundaries:**  
   Currently, the specialists run in-process within the FastAPI application process. True A2A involves network-isolated agents operating on separate hosts or containers.
2. **Asynchronous Task Queue & Streaming Transport:**  
   Replacing synchronous RPC with SSE (Server-Sent Events) or WebSocket streaming for long-running specialist tasks.
3. **Dynamic Agent Discovery & Negotiation:**  
   Implementing an AgentCard registry allowing the orchestrator to dynamically discover new specialized agents at runtime based on advertised skill schemas.
4. **Decentralized Authentication (DID / mTLS):**  
   Securing inter-agent handoffs using mutual TLS or verifiable credentials rather than shared backend application context.
