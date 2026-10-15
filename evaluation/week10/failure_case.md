# Week 10 Phase 4 — Policy-Worker HTTP 500 Failure Injection Report

- **Date / Time:** `2026-10-13T12:04:09.720584+00:00`
- **Experiment Type:** Controlled HTTP 500 Service Fault Injection with Bounded Retries
- **Target Case:** `TQ05`
- **Target Question:** *"What is the annual leave carry-over limit under the policy?"*
- **Correlation ID:** `994f30a9-89c3-4bac-be62-961a7078b230`
- **Request ID:** `f36ab3db-ee09-4192-8bd4-11200a7ad7cc`

---

## 1. Selected Case and Rationale

**Case ID:** `TQ05`  
**Category:** `policy_only` (from `evaluation/trajectory_dataset.py`)  
**Question:** "What is the annual leave carry-over limit under the policy?"  
**Rationale for Selection:**  
Case `TQ05` asks directly for the annual leave carry-over limit under policy without referencing specific employee database records. It relies strictly on `PolicyRetrievalSpecialist` for authoritative evidence. Injecting an HTTP 500 failure into this case directly tests whether the orchestrator safely detects worker unavailability, executes bounded retries with backoff, and halts honestly without manufacturing ungrounded policy numbers or hallucinating a false success.

---

## 2. Fault-Injection Setup

1. **Transport Mechanism:** Isolated HTTP worker endpoint at `POST http://127.0.0.1:8001/internal/workers/policy-retrieval` operated by `HttpPolicySpecialist`.
2. **Activation Control:** Configured via `configure_fault_injection(enabled=True, target_case_id='TQ05', status_code=500)`.
3. **Safety Isolation:** Strictly disabled by default (`enabled: False`). Activated only for this explicit test pass and immediately reset upon test completion in a `finally` block.
4. **Target Precision:** Targets exclusively case `TQ05` via the `X-Case-ID` context header. Public and production requests cannot trigger the fault.
5. **Retry Configuration:** Bounded retries (`max_retries: 2`, max 3 attempts total) with exponential backoff (`base: 0.05s`, `factor: 2.0`) and jitter. Permanent client errors (4xx) fast-fail without retrying.

---

## 3. Expected Safe Behavior

- Worker returns `HTTP 500 Internal Server Error`.
- Adapter initiates bounded retries with exponential backoff and jitter for transient 5xx errors.
- Correlation ID and request ID are strictly preserved across attempts.
- When retries are exhausted, an honest error contract (`WorkerStatus.ERROR`) is returned.
- Orchestrator logs the failed handoff with `status: "error"` and non-sensitive error summaries.
- Orchestrator aborts the query safely and returns an honest degraded error message.
- **Critical Invariance:** The orchestrator must **never** fabricate policy numbers (e.g. inventing "10 days") when policy lookup fails.
- The request must **not** be misclassified as `input-required` (since the question was complete, the fault was a service failure).

---

## 4. Actual Observed Behavior

- **HTTP Status Returned:** `HTTP 500`
- **Number of Attempts:** `3` (Initial attempt + 2 retries with exponential backoff & jitter)
- **Retry Behavior:** Bounded retry policy active (`max_retries=2`, exponential backoff with jitter). Retries exhausted safely.
- **Orchestrator Execution Status:** `error`
- **Final Answer Returned:**  
  > *"Policy retrieval failed: HTTP 500 Internal Server Error from policy retrieval worker endpoint: Internal Server Error: Policy Retrieval database connection failed.. Cannot answer policy question without verified evidence."*
- **Elapsed Execution Time:** `0.238 s`
- **Error Detail Safe for Report:** `HTTP 500 Internal Server Error from policy retrieval worker endpoint: Internal Server Error: Policy Retrieval database connection failed.`

---

## 5. Grounding, Safety, and Observability Evaluation

| Safety Criterion | Requirement | Observed Result | Assessment |
| :--- | :--- | :--- | :---: |
| **No Fabrication** | Must not invent policy terms | Did not invent policy terms; answered with failure disclosure | ✅ PASS |
| **Bounded Retries** | Exponential backoff + jitter | Attempt count = 3 (max 3), retried = True | ✅ PASS |
| **Honest Status** | Must return failed status | `status: "error"` | ✅ PASS |
| **No False Input-Required** | Service error != user input missing | Identified as worker failure, not missing input | ✅ PASS |
| **Structured Trace** | Logged to handoffs.log | Recorded with status `"error"` and sanitized error summary | ✅ PASS |
| **State Reset** | Fault disabled after test | `FAULT_INJECTION_CONFIG["enabled"] == False` confirmed | ✅ PASS |

---

## 6. Observability and Recovery Architecture

1. **Transient Fault Recovery:** `HttpPolicySpecialist` executes bounded retries (default `max_retries=2`) with exponential backoff and jitter for 5xx errors and connection drops, preventing transient blips from causing unneeded query failures.
2. **Permanent Error Fast-Fail:** HTTP 4xx client errors fail immediately on attempt 1 without wasteful retrying.
3. **Correlation Tracking:** Correlation ID (`994f30a9-89c3-4bac-be62-961a7078b230`) and Request ID (`f36ab3db-ee09-4192-8bd4-11200a7ad7cc`) are retained end-to-end across all attempts and logged in `handoffs.log`.
4. **Future Scalability Recommendation:** In distributed production clusters with multiple worker replicas, a distributed circuit breaker and secondary read-only cached policy snapshot could be introduced.
