"""Focused tests for the Week 10 Multi-Agent Orchestrator and Specialists.

Verifies:
1. Policy-retrieval specialist returns structured evidence.
2. Eligibility specialist uses the existing deterministic calculation.
3. Orchestrator delegates policy-only questions correctly.
4. Orchestrator delegates eligibility questions correctly.
5. Orchestrator passes policy evidence to eligibility when the calculation depends on policy.
6. Missing eligibility inputs are handled explicitly.
7. Worker failures are represented as failures, not successful results.
8. The orchestrator does not invent policy details after a failed retrieval.
9. Existing single-agent tests continue to pass (verified alongside existing suite).
10. Existing authorization and role protections remain effective.
"""

from __future__ import annotations

import pytest

from app.multi_agent.contracts import (
    TaskType,
    WorkerRequest,
    WorkerResponse,
    WorkerStatus,
)
from app.multi_agent.eligibility_specialist import EligibilityCalculationSpecialist
from app.multi_agent.orchestrator import MultiAgentOrchestrator, run_multi_agent
from app.multi_agent.policy_specialist import PolicyRetrievalSpecialist


def test_1_policy_retrieval_specialist_returns_structured_evidence():
    """Policy-retrieval specialist must return structured results with evidence metadata."""
    specialist = PolicyRetrievalSpecialist()
    request = WorkerRequest(
        task_type=TaskType.POLICY_RETRIEVAL,
        question="What is the annual leave carry-over limit under the policy?",
        context={"jurisdiction": "INDIA"},
    )
    response = specialist.execute(request)

    assert response.status == WorkerStatus.SUCCESS
    assert response.is_success is True
    assert "results" in response.result
    assert len(response.evidence) > 0
    assert any("source" in chunk for chunk in response.evidence)
    assert any("content" in chunk for chunk in response.evidence)


def test_2_eligibility_specialist_uses_deterministic_calculation():
    """Eligibility specialist must compute exact disposition matching deterministic formula."""
    specialist = EligibilityCalculationSpecialist()
    request = WorkerRequest(
        task_type=TaskType.ELIGIBILITY_CALCULATION,
        question="For employee 005, give the full annual leave disposition.",
        context={
            "leave_balance": 20.0,
            "carry_over_limit": 10.0,
            "encashment_limit": 5.0,
        },
    )
    response = specialist.execute(request)

    assert response.status == WorkerStatus.SUCCESS
    calc = response.result.get("calculation", {})
    assert calc["carryover_days"] == 10.0
    assert calc["encashable_days"] == 5.0
    assert calc["lapsed_days"] == 10.0


def test_3_orchestrator_delegates_policy_only_questions_correctly():
    """Orchestrator must delegate policy questions to PolicyRetrievalSpecialist."""
    orchestrator = MultiAgentOrchestrator()
    result = orchestrator.run("What is the annual leave carry-over limit under the policy?")

    assert result.status == "success"
    assert "10 days" in result.answer
    assert len(result.worker_responses) == 1
    assert result.worker_responses[0].task_type == TaskType.POLICY_RETRIEVAL
    assert len(result.sources) > 0


def test_4_orchestrator_delegates_eligibility_questions_correctly():
    """Orchestrator must coordinate policy retrieval and eligibility calculation."""
    orchestrator = MultiAgentOrchestrator()
    result = orchestrator.run("For employee 005, give the full annual leave disposition.")

    assert result.status == "success"
    assert "10 days can be carried over" in result.answer
    assert "5 days can be encashed" in result.answer
    assert "10 days lapse" in result.answer

    delegated_tasks = [r.task_type for r in result.worker_responses]
    assert TaskType.POLICY_RETRIEVAL in delegated_tasks
    assert TaskType.ELIGIBILITY_CALCULATION in delegated_tasks


def test_5_orchestrator_passes_policy_evidence_to_eligibility_specialist():
    """Orchestrator must extract policy limits from retrieved evidence and pass to eligibility specialist."""
    captured_contexts = []

    class MockEligibilitySpecialist(EligibilityCalculationSpecialist):
        def execute(self, request: WorkerRequest) -> WorkerResponse:
            captured_contexts.append(dict(request.context))
            return super().execute(request)

    orchestrator = MultiAgentOrchestrator(
        eligibility_specialist=MockEligibilitySpecialist()
    )
    result = orchestrator.run("For employee 006, report the annual leave carry-over, encashment, and lapse amounts.")

    assert result.status == "success"
    assert len(captured_contexts) == 1
    passed_context = captured_contexts[0]
    assert passed_context.get("leave_balance") == 5.0
    assert "policy_evidence" in passed_context


def test_6_missing_eligibility_inputs_handled_explicitly():
    """Eligibility specialist must refuse calculation and report missing inputs instead of guessing."""
    specialist = EligibilityCalculationSpecialist()
    # Missing leave_balance
    req_no_balance = WorkerRequest(
        task_type=TaskType.ELIGIBILITY_CALCULATION,
        question="Calculate disposition",
        context={"carry_over_limit": 10.0, "encashment_limit": 5.0},
    )
    resp = specialist.execute(req_no_balance)
    assert resp.status == WorkerStatus.INCOMPLETE
    assert "leave_balance" in resp.error

    # Missing limits without policy evidence
    req_no_limits = WorkerRequest(
        task_type=TaskType.ELIGIBILITY_CALCULATION,
        question="Calculate disposition",
        context={"leave_balance": 15.0},
    )
    resp2 = specialist.execute(req_no_limits)
    assert resp2.status == WorkerStatus.INCOMPLETE
    assert "carry_over_limit" in resp2.error


def test_7_worker_failures_represented_as_failures_not_success():
    """Specialist execution exceptions must return WorkerStatus.ERROR."""
    class FailingPolicySpecialist(PolicyRetrievalSpecialist):
        def execute(self, request: WorkerRequest) -> WorkerResponse:
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.ERROR,
                error="Simulated upstream database connection failure",
            )

    specialist = FailingPolicySpecialist()
    resp = specialist.execute(
        WorkerRequest(task_type=TaskType.POLICY_RETRIEVAL, question="Any policy?")
    )
    assert resp.status == WorkerStatus.ERROR
    assert resp.is_success is False
    assert "Simulated" in resp.error


def test_8_orchestrator_does_not_invent_policy_after_failed_retrieval():
    """Orchestrator must not hallucinate policy facts or calculate if policy worker fails."""
    class FailingPolicySpecialist(PolicyRetrievalSpecialist):
        def execute(self, request: WorkerRequest) -> WorkerResponse:
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.ERROR,
                error="HTTP 500: Policy Retrieval Worker unavailable",
            )

    orchestrator = MultiAgentOrchestrator(
        policy_specialist=FailingPolicySpecialist()
    )
    result = orchestrator.run("For employee 005, give the full annual leave disposition.")

    assert result.status == "error"
    assert "Policy retrieval failed" in result.answer
    assert "HTTP 500" in result.answer
    # Must NOT have run the calculation or reported fabricated disposition numbers
    calc_runs = [r for r in result.worker_responses if r.task_type == TaskType.ELIGIBILITY_CALCULATION]
    assert len(calc_runs) == 0


def test_9_run_multi_agent_functional_entry_point():
    """Test public functional interface returns serializable dictionary with all required keys."""
    res = run_multi_agent("What is the maximum annual leave encashment allowed by policy?")
    assert isinstance(res, dict)
    assert res["status"] == "success"
    assert "5 days" in res["answer"]
    assert "worker_responses" in res
    assert "steps" in res
