"""Tests for Phase 4 (HTTP Fault Injection) and Phase 5 (AgentCards & A2A Metadata)."""

from __future__ import annotations

import json
import pytest

from app.multi_agent.agent_cards import (
    ALL_AGENT_CARDS,
    ELIGIBILITY_SPECIALIST_AGENT_CARD,
    ORCHESTRATOR_AGENT_CARD,
    POLICY_SPECIALIST_AGENT_CARD,
    export_agent_cards_json,
)
from app.multi_agent.contracts import TaskType, WorkerRequest, WorkerStatus
from app.multi_agent.http_transport import (
    FAULT_INJECTION_CONFIG,
    HttpPolicySpecialist,
    configure_fault_injection,
    reset_fault_injection,
)
from app.multi_agent.orchestrator import MultiAgentOrchestrator


def test_fault_injection_is_disabled_by_default():
    """Verify fault injection starts disabled."""
    reset_fault_injection()
    assert FAULT_INJECTION_CONFIG["enabled"] is False
    assert FAULT_INJECTION_CONFIG["target_case_id"] is None


def test_controlled_http_500_fault_injection():
    """Verify HttpPolicySpecialist returns error contract when fault injection is enabled for target case."""
    try:
        configure_fault_injection(enabled=True, target_case_id="TEST_CASE_500", status_code=500)
        specialist = HttpPolicySpecialist()
        req = WorkerRequest(
            task_type=TaskType.POLICY_RETRIEVAL,
            question="Test question",
            context={"case_id": "TEST_CASE_500"},
        )
        resp = specialist.execute(req)

        assert resp.status == WorkerStatus.ERROR
        assert resp.is_success is False
        assert "HTTP 500" in resp.error
        assert resp.metadata.get("status_code") == 500
    finally:
        reset_fault_injection()
        assert FAULT_INJECTION_CONFIG["enabled"] is False


def test_orchestrator_handles_worker_http_500_safely():
    """Verify orchestrator fails gracefully and does not invent facts when policy worker fails."""
    try:
        configure_fault_injection(enabled=True, target_case_id="TQ05", status_code=500)
        specialist = HttpPolicySpecialist()
        orchestrator = MultiAgentOrchestrator(policy_specialist=specialist)
        res = orchestrator.run(
            "What is the annual leave carry-over limit under the policy?",
            role_context={"case_id": "TQ05"},
        )

        assert res.status == "error"
        assert "Policy retrieval failed" in res.answer
        assert "10 days" not in res.answer  # Must not hallucinate or fabricate facts!
    finally:
        reset_fault_injection()


def test_agent_cards_metadata_structure():
    """Verify published AgentCard metadata conforms to expected fields."""
    assert len(ALL_AGENT_CARDS) == 3
    for card in ALL_AGENT_CARDS:
        assert "name" in card
        assert "agent_id" in card
        assert "version" in card
        assert "skills" in card
        assert "input_modes" in card
        assert "output_modes" in card
        assert "supported_lifecycle_states" in card
        assert card["compliance_status"] == "proposed_metadata_only"

    # Verify JSON export
    raw_json = export_agent_cards_json()
    parsed = json.loads(raw_json)
    assert len(parsed) == 3


def test_transient_failure_recovered_with_exponential_backoff():
    """Verify that a transient 500 error recovers on subsequent retry with backoff."""
    try:
        configure_fault_injection(
            enabled=True,
            target_case_id="TRANSIENT_CASE",
            status_code=500,
            failure_count=1,  # Fails attempt 1, succeeds attempt 2
        )
        specialist = HttpPolicySpecialist(max_retries=2, backoff_base_seconds=0.005)
        req = WorkerRequest(
            task_type=TaskType.POLICY_RETRIEVAL,
            question="What is the bereavement leave policy?",
            context={"case_id": "TRANSIENT_CASE"},
            request_id="req-transient-1",
            correlation_id="corr-transient-1",
        )
        resp = specialist.execute(req)

        assert resp.status == WorkerStatus.SUCCESS
        assert resp.is_success is True
        assert resp.metadata.get("retried") is True
        assert resp.metadata.get("attempts") == 2
        assert resp.request_id == "req-transient-1"
    finally:
        reset_fault_injection()
        assert FAULT_INJECTION_CONFIG["enabled"] is False


def test_retry_exhaustion_on_persistent_500():
    """Verify that persistent 500 errors exhaust retries and return an honest error contract."""
    try:
        configure_fault_injection(
            enabled=True,
            target_case_id="PERSISTENT_CASE",
            status_code=500,
            failure_count=None,  # Persistently fails
        )
        specialist = HttpPolicySpecialist(max_retries=2, backoff_base_seconds=0.005)
        req = WorkerRequest(
            task_type=TaskType.POLICY_RETRIEVAL,
            question="What is the bereavement leave policy?",
            context={"case_id": "PERSISTENT_CASE"},
            request_id="req-persist-1",
            correlation_id="corr-persist-1",
        )
        resp = specialist.execute(req)

        assert resp.status == WorkerStatus.ERROR
        assert resp.is_success is False
        assert resp.metadata.get("retried") is True
        assert resp.metadata.get("retries_exhausted") is True
        assert resp.metadata.get("attempts") == 3  # Initial attempt + 2 retries
        assert resp.request_id == "req-persist-1"
        assert "HTTP 500" in resp.error
    finally:
        reset_fault_injection()
        assert FAULT_INJECTION_CONFIG["enabled"] is False


def test_non_retryable_client_error_fails_fast():
    """Verify that permanent 4xx errors fail immediately without wasteful retries."""
    try:
        configure_fault_injection(
            enabled=True,
            target_case_id="CLIENT_ERR_CASE",
            status_code=400,
            error_message="Bad Request: Missing policy query parameter",
        )
        specialist = HttpPolicySpecialist(max_retries=2, backoff_base_seconds=0.005)
        req = WorkerRequest(
            task_type=TaskType.POLICY_RETRIEVAL,
            question="Invalid question",
            context={"case_id": "CLIENT_ERR_CASE"},
            request_id="req-400-1",
        )
        resp = specialist.execute(req)

        assert resp.status == WorkerStatus.ERROR
        assert resp.is_success is False
        assert resp.metadata.get("retried") is False
        assert resp.metadata.get("attempts") == 1  # Fast-fail without retrying
        assert resp.metadata.get("retries_exhausted") is False
        assert resp.metadata.get("status_code") == 400
    finally:
        reset_fault_injection()
        assert FAULT_INJECTION_CONFIG["enabled"] is False


def test_fault_injection_cleanup_guarantee():
    """Verify that reset_fault_injection cleanly restores defaults even after abnormal termination."""
    try:
        configure_fault_injection(
            enabled=True,
            target_case_id="CLEANUP_CASE",
            status_code=500,
            failure_count=3,
        )
        assert FAULT_INJECTION_CONFIG["enabled"] is True
        assert FAULT_INJECTION_CONFIG["target_case_id"] == "CLEANUP_CASE"
        assert FAULT_INJECTION_CONFIG["failure_count"] == 3
        # Simulate an exception in user code
        raise RuntimeError("Simulated failure")
    except RuntimeError:
        pass
    finally:
        reset_fault_injection()

    assert FAULT_INJECTION_CONFIG["enabled"] is False
    assert FAULT_INJECTION_CONFIG["target_case_id"] is None
    assert FAULT_INJECTION_CONFIG["failure_count"] is None
    assert FAULT_INJECTION_CONFIG["attempt_counter"] == 0

