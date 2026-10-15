"""Tests for Multi-Agent Token, Latency, Cost, and Handoff Instrumentation (Week 10 Phase 2).

Verifies:
1. Single-agent token and latency measurements remain available.
2. Multi-agent execution records total latency and specialist timings.
3. Actual LLM token usage is captured when usage metadata is available.
4. Missing usage metadata is handled with a clearly labeled fallback.
5. Request and response handoff payload counts are recorded.
6. A policy-to-calculation handoff includes the passed policy evidence in its measured payload.
7. Failures and incomplete responses are logged with the correct status.
8. Sensitive payload content is not unnecessarily exposed in logs.
9. Instrumentation does not change answers, worker routing, authorization, or calculation results.
10. Context re-send multiplier formula handles normal and zero-denominator cases correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent import BudgetState
from app.multi_agent.contracts import (
    TaskType,
    WorkerRequest,
    WorkerResponse,
    WorkerStatus,
)
from app.multi_agent.eligibility_specialist import EligibilityCalculationSpecialist
from app.multi_agent.instrumentation import (
    calculate_context_resend_multiplier,
    calculate_model_token_ratio,
    estimate_payload_tokens,
    sanitize_payload,
)
from app.multi_agent.orchestrator import MultiAgentOrchestrator, run_multi_agent
from app.multi_agent.policy_specialist import PolicyRetrievalSpecialist


def test_1_single_agent_token_and_latency_measurements_remain_available():
    """Verify single-agent BudgetState still records tokens, cost, latency, and termination reason."""
    budget = BudgetState()
    assert budget.elapsed_seconds >= 0.0
    budget.record_tokens(150, "ollama_metadata")
    assert budget.tokens_used == 150
    assert budget.estimated_cost == (150 / 1000) * 0.001
    assert budget.token_usage_source == "ollama_metadata"

    budget.record_tokens(50, "fallback_estimate")
    assert budget.tokens_used == 200
    assert budget.token_usage_source == "fallback_estimate"


def test_2_multi_agent_records_total_latency_and_specialist_timings(tmp_path):
    """Verify multi-agent orchestrator measures total latency and specialist breakdowns."""
    log_file = tmp_path / "test_handoffs.log"
    orchestrator = MultiAgentOrchestrator(handoff_log_path=log_file)
    res = orchestrator.run("For employee 005, give the full annual leave disposition.")

    m = res.metrics
    assert m.total_latency_seconds > 0.0
    assert m.policy_specialist_latency_seconds > 0.0
    assert m.eligibility_specialist_latency_seconds > 0.0
    assert m.employee_lookup_latency_seconds > 0.0
    assert m.orchestrator_latency_seconds >= 0.0
    assert m.specialist_call_count == 2
    assert m.handoff_count == 2


def test_3_actual_llm_token_usage_captured_when_metadata_available(tmp_path):
    """Verify orchestrator captures model tokens and marks source as ollama_metadata."""
    log_file = tmp_path / "test_handoffs.log"

    def mock_chat_fn(**kwargs):
        return {
            "message": {"content": "10 days carry, 5 days encash, 10 days lapse"},
            "prompt_eval_count": 45,
            "eval_count": 15,
        }

    orchestrator = MultiAgentOrchestrator(
        chat_fn=mock_chat_fn,
        handoff_log_path=log_file,
    )
    res = orchestrator.run("For employee 005, give the full annual leave disposition.")

    m = res.metrics
    assert m.model_call_count == 1
    assert m.model_prompt_tokens == 45
    assert m.model_completion_tokens == 15
    assert m.total_model_tokens == 60
    assert m.model_token_usage_source == "ollama_metadata"
    assert m.estimated_cost == round((60 / 1000) * 0.001, 6)


def test_4_missing_usage_metadata_handled_with_fallback_estimate(tmp_path):
    """Verify fallback token estimation is used and marked when provider metadata is absent."""
    log_file = tmp_path / "test_handoffs.log"

    def mock_chat_fn_no_metadata(**kwargs):
        return {"message": {"content": "Final summarized text response"}}

    orchestrator = MultiAgentOrchestrator(
        chat_fn=mock_chat_fn_no_metadata,
        handoff_log_path=log_file,
    )
    res = orchestrator.run("For employee 005, give the full annual leave disposition.")

    m = res.metrics
    assert m.model_call_count == 1
    assert m.total_model_tokens > 0
    assert m.model_token_usage_source == "fallback_estimate"


def test_5_request_and_response_handoff_payload_counts_recorded(tmp_path):
    """Verify each hand-off records request, response, and combined payload token counts."""
    log_file = tmp_path / "test_handoffs.log"
    orchestrator = MultiAgentOrchestrator(handoff_log_path=log_file)
    res = orchestrator.run("What is the annual leave carry-over limit under the policy?")

    m = res.metrics
    assert len(m.handoff_records) == 1
    h = m.handoff_records[0]
    assert h.request_tokens > 0
    assert h.response_tokens > 0
    assert h.combined_payload_tokens == h.request_tokens + h.response_tokens
    assert h.token_count_method == "estimated_payload_chars_div_4"

    # Verify written to handoff log file
    assert log_file.exists()
    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 1
    assert lines[0]["destination"] == "policy_specialist"
    assert lines[0]["combined_payload_tokens"] == h.combined_payload_tokens


def test_6_policy_to_calculation_handoff_includes_passed_evidence_in_payload(tmp_path):
    """Verify that evidence passed to eligibility specialist is measured in payload token count."""
    log_file = tmp_path / "test_handoffs.log"
    orchestrator = MultiAgentOrchestrator(handoff_log_path=log_file)
    res = orchestrator.run("For employee 005, give the full annual leave disposition.")

    m = res.metrics
    assert len(m.handoff_records) == 2
    calc_handoff = next(h for h in m.handoff_records if h.destination == "eligibility_specialist")
    # Request payload includes policy_evidence chunks, so request_tokens must be significant
    assert calc_handoff.request_tokens > 20
    assert calc_handoff.combined_payload_tokens > calc_handoff.response_tokens


def test_7_failures_and_incomplete_responses_logged_with_correct_status(tmp_path):
    """Verify worker failures log their status accurately as ERROR."""
    log_file = tmp_path / "test_handoffs.log"

    class FailingPolicySpecialist(PolicyRetrievalSpecialist):
        def execute(self, request: WorkerRequest) -> WorkerResponse:
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.ERROR,
                error="Simulated upstream service error",
            )

    orchestrator = MultiAgentOrchestrator(
        policy_specialist=FailingPolicySpecialist(),
        handoff_log_path=log_file,
    )
    res = orchestrator.run("What is the annual leave carry-over limit under the policy?")
    assert res.status == "error"

    m = res.metrics
    assert len(m.handoff_records) == 1
    assert m.handoff_records[0].status == "error"

    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").strip().splitlines()]
    assert lines[0]["status"] == "error"


def test_8_sensitive_payload_content_sanitized_in_logs():
    """Verify employee-sensitive fields (annual_salary, phone, email) are redacted."""
    raw_payload = {
        "employee_id": "001",
        "employee_name": "Asha Bhosle",
        "annual_salary": 950000.0,
        "phone": "+91 98765 43210",
        "email": "asha.bhosle@company.com",
        "department": "Engineering",
    }
    sanitized = sanitize_payload(raw_payload)
    assert sanitized["annual_salary"] == "[REDACTED]"
    assert sanitized["phone"] == "[REDACTED]"
    assert sanitized["email"] == "[REDACTED]"
    assert sanitized["employee_name"] == "Asha Bhosle"
    assert sanitized["department"] == "Engineering"


def test_9_instrumentation_does_not_change_answers_or_calculations():
    """Verify that adding metrics does not alter question answering or disposition calculations."""
    res = run_multi_agent("For employee 006, report the annual leave carry-over, encashment, and lapse amounts.")
    assert "5 days can be carried over" in res["answer"]
    assert "5 days can be encashed" in res["answer"]
    assert "0 days lapse" in res["answer"]

    # Check metrics envelope is present
    assert "metrics" in res
    assert res["metrics"]["handoff_count"] == 2
    assert res["metrics"]["total_handoff_payload_tokens"] > 0


def test_10_context_resend_multiplier_formula():
    """Verify model token ratio formula and zero-denominator handling."""
    # Normal case: 1200 / 800 = 1.5
    assert calculate_model_token_ratio(1200, 800) == 1.5
    assert calculate_context_resend_multiplier(1200, 800) == 1.5

    # Multi-agent fewer tokens: 600 / 800 = 0.75
    assert calculate_model_token_ratio(600, 800) == 0.75
    assert calculate_context_resend_multiplier(600, 800) == 0.75

    # Zero denominator case
    assert calculate_model_token_ratio(0, 0) == 0.0
    assert calculate_model_token_ratio(500, 0) == 1.0
    assert calculate_context_resend_multiplier(0, 0) == 0.0
    assert calculate_context_resend_multiplier(500, 0) == 1.0
