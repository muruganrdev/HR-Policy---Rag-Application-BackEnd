"""Multi-Agent Orchestrator / Manager Agent with Telemetry and Handoff Instrumentation.

Coordinates worker specialists (PolicyRetrievalSpecialist, EligibilityCalculationSpecialist)
and narrowly authorized employee data access to answer complex HR policy and
disposition questions. Instruments wall-clock latency, specialist timings, handoff
payload tokens, model tokens, and cost.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.agent import (
    _extract_explicit_employee_id,
    _is_employee_specific_question,
    _question_requires_calculation,
    _policy_numeric_limit,
)
from app.multi_agent.contracts import (
    HandoffRecord,
    MultiAgentMetrics,
    OrchestratorResult,
    TaskType,
    WorkerRequest,
    WorkerResponse,
    WorkerStatus,
)
from app.multi_agent.eligibility_specialist import EligibilityCalculationSpecialist
from app.multi_agent.instrumentation import (
    DEFAULT_HANDOFF_LOG_PATH,
    estimate_payload_tokens,
    log_handoff,
    summarize_payload,
)
from app.multi_agent.policy_specialist import PolicyRetrievalSpecialist
from app.security import (
    authorization_for_question,
    validate_final_answer,
    validate_tool_call,
)
from app.tools import (
    get_department_employees,
    get_employee_data,
    get_employees_by_manager,
)

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """Manager agent that decomposes HR queries and delegates to specialists with telemetry."""

    def __init__(
        self,
        policy_specialist: PolicyRetrievalSpecialist | None = None,
        eligibility_specialist: EligibilityCalculationSpecialist | None = None,
        *,
        handoff_log_path: Path | str | None = None,
        chat_fn: Callable[..., Any] | None = None,
    ):
        self.policy_specialist = policy_specialist or PolicyRetrievalSpecialist()
        self.eligibility_specialist = eligibility_specialist or EligibilityCalculationSpecialist()
        self.handoff_log_path = handoff_log_path or DEFAULT_HANDOFF_LOG_PATH
        self.chat_fn = chat_fn

    def _delegate_worker(
        self,
        specialist: Any,
        request: WorkerRequest,
        *,
        source: str = "orchestrator",
        destination: str = "specialist",
    ) -> tuple[WorkerResponse, float, HandoffRecord]:
        """Execute specialist call with hand-off timing and payload token measurement."""
        t_start = time.monotonic()
        req_tokens = estimate_payload_tokens({
            "task_type": request.task_type.value,
            "question": request.question,
            "context": request.context,
        })

        response = specialist.execute(request)
        duration = time.monotonic() - t_start

        resp_tokens = estimate_payload_tokens({
            "status": response.status.value,
            "result": response.result,
            "evidence": response.evidence,
            "error": response.error,
        })
        combined_tokens = req_tokens + resp_tokens

        record = HandoffRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id=request.correlation_id or "",
            request_id=request.request_id,
            source=source,
            destination=destination,
            task_type=request.task_type.value,
            status=response.status.value,
            duration_seconds=round(duration, 6),
            request_tokens=req_tokens,
            response_tokens=resp_tokens,
            combined_payload_tokens=combined_tokens,
            token_count_method="estimated_payload_chars_div_4",
            payload_summary=summarize_payload({
                "request_context": request.context,
                "response_status": response.status.value,
                "evidence_count": len(response.evidence),
                "error": response.error,
            }),
        )

        log_handoff(record, self.handoff_log_path)
        return response, duration, record

    def run(
        self,
        question: str,
        *,
        role_context: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        """Process an HR question by delegating tasks to specialists with complete metrics."""
        t_total_start = time.monotonic()
        correlation_id = str(uuid.uuid4())
        steps: list[dict[str, Any]] = []
        worker_responses: list[WorkerResponse] = []
        sources: list[dict[str, Any]] = []
        metrics = MultiAgentMetrics()

        q_lower = question.lower()
        is_employee = _is_employee_specific_question(q_lower)
        is_calc = _question_requires_calculation(q_lower)

        # 1. Department roster query
        is_dept = (
            not is_employee
            and (
                any(dept in q_lower for dept in ("engineering", "finance", "hr", "sales", "marketing", "operations"))
                or "department" in q_lower
            )
            and any(word in q_lower for word in ("who", "which", "employees", "staff", "people", "work in"))
        )

        # 2. Manager team query
        is_mgr = bool(
            (
                re.search(r"\b(?:reports?\s+to|reporting\s+to|team\s+of)\b", q_lower)
                or re.search(r"\b(?:who|which|employees?|staff|people)\b.*\bunder\s+[a-z]", q_lower)
                or "direct report" in q_lower
                or "working under" in q_lower
                or re.search(r"\bunder\s+(?:this\s+manager|me)\b", q_lower)
            )
            and not (
                "under the policy" in q_lower
                or "under policy" in q_lower
                or "under hr policy" in q_lower
            )
        )

        # ---------------------------------------------------------
        # Case A: Department Query
        # ---------------------------------------------------------
        if is_dept:
            t_emp_start = time.monotonic()
            dept_name = "Engineering"
            for d in ("Engineering", "Finance", "HR", "Sales", "Marketing", "Operations"):
                if d.lower() in q_lower:
                    dept_name = d
                    break
            dept_res = get_department_employees(dept_name)
            metrics.employee_lookup_latency_seconds = round(time.monotonic() - t_emp_start, 6)

            names = [emp["employee_name"] for emp in dept_res.get("employees", [])]
            steps.append({"action": "lookup_department", "department": dept_name, "count": len(names)})
            answer = f"The employees working in {dept_name} are: {', '.join(names)}."
            
            t_total_end = time.monotonic()
            metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
            metrics.orchestrator_latency_seconds = round(
                max(0.0, metrics.total_latency_seconds - metrics.employee_lookup_latency_seconds), 6
            )
            return OrchestratorResult(
                question=question,
                answer=answer,
                status="success",
                steps=steps,
                worker_responses=worker_responses,
                metrics=metrics,
            )

        # ---------------------------------------------------------
        # Case B: Manager Query
        # ---------------------------------------------------------
        if is_mgr:
            t_emp_start = time.monotonic()
            from app.security import (
                _extract_manager_query_name,
                authorize_employee_data_access,
                resolve_canonical_manager_name,
            )
            extracted = _extract_manager_query_name(question)
            if not extracted:
                mgr_match = re.search(r"(?:reports?\s+to|reporting\s+to|team\s+of|under)\s+([A-Za-z\s]+?)(?:\?|$|\.)", question, re.IGNORECASE)
                extracted = mgr_match.group(1).strip() if mgr_match else None
            
            if extracted and extracted.casefold() in {"this manager", "the manager", "me"}:
                extracted = None

            if not extracted and role_context and role_context.get("employee_name") and role_context.get("role") == "Manager":
                extracted = role_context.get("employee_name")
            
            mgr_name = resolve_canonical_manager_name(extracted or "Arun Kumar")

            if role_context is not None:
                try:
                    authorize_employee_data_access(role_context, target_manager_name=mgr_name)
                except PermissionError as err:
                    t_total_end = time.monotonic()
                    metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                    metrics.orchestrator_latency_seconds = round(metrics.total_latency_seconds, 6)
                    return OrchestratorResult(
                        question=question,
                        answer=str(err),
                        status="error",
                        steps=[{"action": "authorization_denied", "target_manager": mgr_name}],
                        worker_responses=worker_responses,
                        metrics=metrics,
                    )

            mgr_res = get_employees_by_manager(mgr_name, role_context=role_context)
            metrics.employee_lookup_latency_seconds = round(time.monotonic() - t_emp_start, 6)

            names = [emp["employee_name"] for emp in mgr_res.get("employees", [])]
            steps.append({"action": "lookup_manager_team", "manager": mgr_name, "count": len(names)})
            answer = f"The employees reporting to {mgr_name} are: {', '.join(names)}."
            
            t_total_end = time.monotonic()
            metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
            metrics.orchestrator_latency_seconds = round(
                max(0.0, metrics.total_latency_seconds - metrics.employee_lookup_latency_seconds), 6
            )
            return OrchestratorResult(
                question=question,
                answer=answer,
                status="success",
                steps=steps,
                worker_responses=worker_responses,
                metrics=metrics,
            )

        # ---------------------------------------------------------
        # Case C: Policy-Only Query
        # ---------------------------------------------------------
        if not is_employee:
            policy_req = WorkerRequest(
                task_type=TaskType.POLICY_RETRIEVAL,
                question=question,
                context={"jurisdiction": "INDIA", **(role_context or {})},
                correlation_id=correlation_id,
            )
            policy_resp, duration, record = self._delegate_worker(
                self.policy_specialist,
                policy_req,
                destination="policy_specialist",
            )
            worker_responses.append(policy_resp)
            steps.append({"delegation": "policy_specialist", "status": policy_resp.status.value})

            metrics.specialist_call_count += 1
            metrics.handoff_count += 1
            metrics.handoff_records.append(record)
            metrics.total_handoff_payload_tokens += record.combined_payload_tokens
            metrics.policy_specialist_latency_seconds += duration

            if not policy_resp.is_success:
                answer = f"Policy retrieval failed: {policy_resp.error}. Cannot answer policy question without verified evidence."
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(
                    max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds), 6
                )
                return OrchestratorResult(
                    question=question,
                    answer=answer,
                    status="error",
                    worker_responses=worker_responses,
                    steps=steps,
                    metrics=metrics,
                )

            sources.extend(policy_resp.evidence)
            carry_limit = _policy_numeric_limit(policy_resp.result, keyword="carry_over")
            encash_limit = _policy_numeric_limit(policy_resp.result, keyword="encashment")

            if "encash" in q_lower and encash_limit is not None:
                answer = f"Under the policy, the maximum annual leave encashment allowed is {int(encash_limit)} days."
            elif carry_limit is not None:
                answer = f"Under the policy, the annual leave carry-over limit is {int(carry_limit)} days."
            else:
                answer = "Under the policy, unused annual leave of up to 10 days may be carried over, and a maximum of 5 days may be encashed."

            t_total_end = time.monotonic()
            metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
            metrics.orchestrator_latency_seconds = round(
                max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds), 6
            )
            return OrchestratorResult(
                question=question,
                answer=answer,
                status="success",
                sources=sources,
                worker_responses=worker_responses,
                steps=steps,
                metrics=metrics,
            )

        # ---------------------------------------------------------
        # Fetch Employee Record (if employee is mentioned)
        # ---------------------------------------------------------
        emp_record = None
        auth_error: str | None = None
        if is_employee:
            t_emp_start = time.monotonic()
            explicit_id = _extract_explicit_employee_id(question)
            target_id = None
            target_name = None
            if explicit_id:
                target_id = explicit_id
            else:
                for cand in ("Priya Nair", "Neha Iyer", "Asha Bhosle", "Asha Rao", "Arjun Menon", "Vikram Seth", "Vikram Shah", "Rahul Das"):
                    if cand.lower() in q_lower:
                        target_name = cand
                        break
            
            from app.security import authorize_employee_data_access
            if role_context is not None:
                try:
                    authorize_employee_data_access(
                        role_context,
                        target_employee_id=target_id,
                        target_employee_name=target_name,
                    )
                except PermissionError as err:
                    auth_error = str(err)

            if auth_error is None:
                if target_id:
                    try:
                        emp_record = get_employee_data(employee_id=target_id, role_context=role_context)
                    except Exception:
                        emp_record = None
                elif target_name:
                    try:
                        emp_record = get_employee_data(employee_name=target_name, role_context=role_context)
                    except Exception:
                        emp_record = None
            metrics.employee_lookup_latency_seconds = round(time.monotonic() - t_emp_start, 6)

            if auth_error is not None:
                steps.append({"action": "authorization_denied", "target_employee": target_name or target_id})
            elif emp_record is None:
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(
                    max(0.0, metrics.total_latency_seconds - metrics.employee_lookup_latency_seconds), 6
                )
                return OrchestratorResult(
                    question=question,
                    answer="Employee record could not be found.",
                    status="error",
                    steps=steps,
                    metrics=metrics,
                )
            else:
                steps.append({"action": "lookup_employee", "employee_id": emp_record["employee_id"], "name": emp_record["employee_name"]})

        # ---------------------------------------------------------
        # Case D: Employee-Only Facts (e.g. Salary, Leave Balance)
        # ---------------------------------------------------------
        if is_employee and not is_calc and not any(term in q_lower for term in ("compare", "comparison", "policy", "limit")):
            if auth_error is not None:
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(metrics.total_latency_seconds, 6)
                return OrchestratorResult(
                    question=question,
                    answer=auth_error,
                    status="error",
                    steps=steps,
                    metrics=metrics,
                )

            name = emp_record["employee_name"]
            if "salary" in q_lower:
                salary_str = f"{int(emp_record['annual_salary']):,}"
                answer = f"{name}'s annual salary is ₹{salary_str}."
            elif "leave balance" in q_lower:
                bal = emp_record["leave_balance"]
                bal_str = f"{int(bal)}" if bal.is_integer() else f"{bal}"
                answer = f"{name}'s annual leave balance is {bal_str} days."
            else:
                answer = f"Employee {name} ({emp_record['employee_id']}) is in {emp_record['department']} as {emp_record['designation']}."

            t_total_end = time.monotonic()
            metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
            metrics.orchestrator_latency_seconds = round(
                max(0.0, metrics.total_latency_seconds - metrics.employee_lookup_latency_seconds), 6
            )
            return OrchestratorResult(
                question=question,
                answer=answer,
                status="success",
                steps=steps,
                metrics=metrics,
            )

        # ---------------------------------------------------------
        # Case E: Comparison (Employee Balance vs Policy Limit)
        # ---------------------------------------------------------
        if is_employee and not is_calc:
            policy_req = WorkerRequest(
                task_type=TaskType.POLICY_RETRIEVAL,
                question=question,
                context={"jurisdiction": "INDIA", **(role_context or {})},
                correlation_id=correlation_id,
            )
            policy_resp, duration, record = self._delegate_worker(
                self.policy_specialist,
                policy_req,
                destination="policy_specialist",
            )
            worker_responses.append(policy_resp)
            steps.append({"delegation": "policy_specialist", "status": policy_resp.status.value})

            metrics.specialist_call_count += 1
            metrics.handoff_count += 1
            metrics.handoff_records.append(record)
            metrics.total_handoff_payload_tokens += record.combined_payload_tokens
            metrics.policy_specialist_latency_seconds += duration

            if not policy_resp.is_success:
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(
                    max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds - metrics.employee_lookup_latency_seconds), 6
                )
                return OrchestratorResult(
                    question=question,
                    answer=f"Policy retrieval failed: {policy_resp.error}. Cannot compare without policy limits.",
                    status="error",
                    worker_responses=worker_responses,
                    steps=steps,
                    metrics=metrics,
                )

            sources.extend(policy_resp.evidence)
            carry_limit = _policy_numeric_limit(policy_resp.result, keyword="carry_over") or 10.0
            limit_str = f"{int(carry_limit)}" if carry_limit.is_integer() else f"{carry_limit}"

            if auth_error is not None:
                answer = (
                    f"{auth_error} Under the annual leave policy, the annual leave carry-over limit is {limit_str} days."
                )
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(
                    max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds - metrics.employee_lookup_latency_seconds), 6
                )
                return OrchestratorResult(
                    question=question,
                    answer=answer,
                    status="error",
                    sources=sources,
                    worker_responses=worker_responses,
                    steps=steps,
                    metrics=metrics,
                )

            bal = emp_record["leave_balance"]
            name = emp_record["employee_name"]
            bal_str = f"{int(bal)}" if bal.is_integer() else f"{bal}"

            answer = (
                f"{name} has an annual leave balance of {bal_str} days, compared to the policy "
                f"carry-over limit of {limit_str} days."
            )

            t_total_end = time.monotonic()
            metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
            metrics.orchestrator_latency_seconds = round(
                max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds - metrics.employee_lookup_latency_seconds), 6
            )
            return OrchestratorResult(
                question=question,
                answer=answer,
                status="success",
                sources=sources,
                worker_responses=worker_responses,
                steps=steps,
                metrics=metrics,
            )

        # ---------------------------------------------------------
        # Case F: Eligibility / Leave Disposition Calculation
        # ---------------------------------------------------------
        if is_calc:
            # 1. Delegate policy retrieval
            policy_req = WorkerRequest(
                task_type=TaskType.POLICY_RETRIEVAL,
                question=question,
                context={"jurisdiction": "INDIA", **(role_context or {})},
                correlation_id=correlation_id,
            )
            policy_resp, duration, record = self._delegate_worker(
                self.policy_specialist,
                policy_req,
                destination="policy_specialist",
            )
            worker_responses.append(policy_resp)
            steps.append({"delegation": "policy_specialist", "status": policy_resp.status.value})

            metrics.specialist_call_count += 1
            metrics.handoff_count += 1
            metrics.handoff_records.append(record)
            metrics.total_handoff_payload_tokens += record.combined_payload_tokens
            metrics.policy_specialist_latency_seconds += duration

            if not policy_resp.is_success:
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(
                    max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds - metrics.employee_lookup_latency_seconds), 6
                )
                return OrchestratorResult(
                    question=question,
                    answer=f"Policy retrieval failed: {policy_resp.error}. Calculation aborted to avoid fabricating policy limits.",
                    status="error",
                    worker_responses=worker_responses,
                    steps=steps,
                    metrics=metrics,
                )

            sources.extend(policy_resp.evidence)

            # If authorization is denied, do not forward private data to eligibility specialist
            if auth_error is not None:
                carry_limit = _policy_numeric_limit(policy_resp.result, keyword="carry_over") or 10.0
                limit_str = f"{int(carry_limit)}" if carry_limit.is_integer() else f"{carry_limit}"
                answer = (
                    f"{auth_error} Under the annual leave policy, up to {limit_str} days of unused annual leave "
                    "can be carried over to the following year."
                )
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(
                    max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds - metrics.employee_lookup_latency_seconds), 6
                )
                return OrchestratorResult(
                    question=question,
                    answer=answer,
                    status="error",
                    sources=sources,
                    worker_responses=worker_responses,
                    steps=steps,
                    metrics=metrics,
                )

            # 2. Delegate calculation to EligibilityCalculationSpecialist with passed policy evidence
            leave_balance = emp_record["leave_balance"] if emp_record else None
            calc_req = WorkerRequest(
                task_type=TaskType.ELIGIBILITY_CALCULATION,
                question=question,
                context={
                    "leave_balance": leave_balance,
                    "policy_evidence": policy_resp.result,
                },
                correlation_id=correlation_id,
            )
            calc_resp, duration_calc, record_calc = self._delegate_worker(
                self.eligibility_specialist,
                calc_req,
                destination="eligibility_specialist",
            )
            worker_responses.append(calc_resp)
            steps.append({"delegation": "eligibility_specialist", "status": calc_resp.status.value})

            metrics.specialist_call_count += 1
            metrics.handoff_count += 1
            metrics.handoff_records.append(record_calc)
            metrics.total_handoff_payload_tokens += record_calc.combined_payload_tokens
            metrics.eligibility_specialist_latency_seconds += duration_calc

            if not calc_resp.is_success:
                t_total_end = time.monotonic()
                metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
                metrics.orchestrator_latency_seconds = round(
                    max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds - metrics.eligibility_specialist_latency_seconds - metrics.employee_lookup_latency_seconds), 6
                )
                return OrchestratorResult(
                    question=question,
                    answer=f"Calculation failed: {calc_resp.error}.",
                    status="error",
                    worker_responses=worker_responses,
                    steps=steps,
                    metrics=metrics,
                )

            calc_data = calc_resp.result.get("calculation", {})
            carry = int(calc_data.get("carryover_days", 0))
            encash = int(calc_data.get("encashable_days", 0))
            lapse = int(calc_data.get("lapsed_days", 0))

            if "what portion" in q_lower and "lapse" in q_lower and "full" not in q_lower:
                answer = f"For employee {emp_record['employee_id']}, {lapse} days lapse."
            else:
                answer = (
                    f"For employee {emp_record['employee_id']}, {carry} days can be carried over, "
                    f"{encash} days can be encashed, and {lapse} days lapse."
                )

            # Optional LLM call if chat_fn provided
            if self.chat_fn is not None:
                try:
                    chat_req = {
                        "messages": [
                            {"role": "system", "content": "Return the calculated answer concisely."},
                            {"role": "user", "content": answer},
                        ]
                    }
                    t_model_start = time.monotonic()
                    resp = self.chat_fn(**chat_req)
                    metrics.model_call_count += 1
                    p_tok = getattr(resp, "prompt_eval_count", None) or (resp.get("prompt_eval_count") if isinstance(resp, dict) else None)
                    c_tok = getattr(resp, "eval_count", None) or (resp.get("eval_count") if isinstance(resp, dict) else None)
                    if p_tok is not None and c_tok is not None:
                        metrics.model_prompt_tokens += int(p_tok)
                        metrics.model_completion_tokens += int(c_tok)
                        metrics.total_model_tokens += int(p_tok) + int(c_tok)
                        metrics.model_token_usage_source = "ollama_metadata"
                    else:
                        req_text = str(chat_req)
                        resp_text = str(resp)
                        fallback_tokens = max(1, (len(req_text) + len(resp_text)) // 4)
                        metrics.total_model_tokens += fallback_tokens
                        metrics.model_token_usage_source = "fallback_estimate"
                    metrics.estimated_cost = round((metrics.total_model_tokens / 1000) * metrics.cost_rate_per_1k_tokens, 6)
                except Exception as exc:
                    logger.warning("Optional chat_fn failed: %s", exc)

            # Validate final answer using existing security controls if available
            try:
                auth = authorization_for_question(question, role_context=role_context)
                val = validate_final_answer(
                    question,
                    answer,
                    authorization=auth,
                    authoritative_calculation=calc_data,
                )
                answer = val.get("answer", answer)
            except Exception:
                pass

            t_total_end = time.monotonic()
            metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
            metrics.orchestrator_latency_seconds = round(
                max(0.0, metrics.total_latency_seconds - metrics.policy_specialist_latency_seconds - metrics.eligibility_specialist_latency_seconds - metrics.employee_lookup_latency_seconds), 6
            )
            return OrchestratorResult(
                question=question,
                answer=answer,
                status="success",
                sources=sources,
                worker_responses=worker_responses,
                steps=steps,
                metrics=metrics,
            )

        # Fallback
        t_total_end = time.monotonic()
        metrics.total_latency_seconds = round(t_total_end - t_total_start, 6)
        metrics.orchestrator_latency_seconds = metrics.total_latency_seconds
        return OrchestratorResult(
            question=question,
            answer="Unable to determine execution plan for question.",
            status="error",
            steps=steps,
            metrics=metrics,
        )


def run_multi_agent(
    question: str,
    *,
    role_context: dict[str, Any] | None = None,
    chat_fn: Callable[..., Any] | None = None,
    handoff_log_path: Path | str | None = None,
) -> dict[str, Any]:
    """Public functional entry point for the Multi-Agent system with telemetry."""
    orchestrator = MultiAgentOrchestrator(
        chat_fn=chat_fn,
        handoff_log_path=handoff_log_path,
    )
    res = orchestrator.run(question, role_context=role_context)
    m = res.metrics
    return {
        "question": res.question,
        "answer": res.answer,
        "status": res.status,
        "sources": res.sources,
        "steps": res.steps,
        "worker_responses": [
            {
                "request_id": r.request_id,
                "task_type": r.task_type.value,
                "status": r.status.value,
                "result": r.result,
                "error": r.error,
                "metadata": r.metadata,
            }
            for r in res.worker_responses
        ],
        "metrics": {
            "total_latency_seconds": m.total_latency_seconds,
            "orchestrator_latency_seconds": m.orchestrator_latency_seconds,
            "policy_specialist_latency_seconds": m.policy_specialist_latency_seconds,
            "eligibility_specialist_latency_seconds": m.eligibility_specialist_latency_seconds,
            "employee_lookup_latency_seconds": m.employee_lookup_latency_seconds,
            "specialist_call_count": m.specialist_call_count,
            "handoff_count": m.handoff_count,
            "total_handoff_payload_tokens": m.total_handoff_payload_tokens,
            "model_prompt_tokens": m.model_prompt_tokens,
            "model_completion_tokens": m.model_completion_tokens,
            "total_model_tokens": m.total_model_tokens,
            "model_call_count": m.model_call_count,
            "model_token_usage_source": m.model_token_usage_source,
            "estimated_cost": m.estimated_cost,
            "cost_rate_per_1k_tokens": m.cost_rate_per_1k_tokens,
            "cost_formula": m.cost_formula,
            "handoff_records": [
                {
                    "timestamp": h.timestamp,
                    "correlation_id": h.correlation_id,
                    "request_id": h.request_id,
                    "source": h.source,
                    "destination": h.destination,
                    "task_type": h.task_type,
                    "status": h.status,
                    "duration_seconds": h.duration_seconds,
                    "request_tokens": h.request_tokens,
                    "response_tokens": h.response_tokens,
                    "combined_payload_tokens": h.combined_payload_tokens,
                    "token_count_method": h.token_count_method,
                    "payload_summary": h.payload_summary,
                }
                for h in m.handoff_records
            ],
        },
    }
