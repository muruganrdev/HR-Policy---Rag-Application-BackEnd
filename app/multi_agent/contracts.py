"""Typed worker contracts and message structures for the Multi-Agent architecture.

Defines the message envelopes and interfaces for orchestrator-to-specialist
interactions, establishing clear boundaries, audit trails, and telemetry.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    """Enumeration of specialist task types."""
    POLICY_RETRIEVAL = "policy_retrieval"
    ELIGIBILITY_CALCULATION = "eligibility_calculation"


class WorkerStatus(str, Enum):
    """Execution status returned by specialist workers."""
    SUCCESS = "success"
    ERROR = "error"
    INCOMPLETE = "incomplete"
    INVALID_INPUT = "invalid_input"


@dataclass
class WorkerRequest:
    """Standardized request envelope sent from orchestrator to specialist."""
    task_type: TaskType
    question: str
    context: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None


@dataclass
class WorkerResponse:
    """Standardized response envelope returned from specialist to orchestrator."""
    request_id: str
    task_type: TaskType
    status: WorkerStatus
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == WorkerStatus.SUCCESS


@dataclass
class HandoffRecord:
    """Record of a single delegation hand-off between orchestrator and worker."""
    timestamp: str
    correlation_id: str
    request_id: str
    source: str
    destination: str
    task_type: str
    status: str
    duration_seconds: float
    request_tokens: int
    response_tokens: int
    combined_payload_tokens: int
    token_count_method: str = "estimated_payload_chars_div_4"
    payload_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiAgentMetrics:
    """Comprehensive performance and telemetry metrics for a multi-agent execution."""
    total_latency_seconds: float = 0.0
    orchestrator_latency_seconds: float = 0.0
    policy_specialist_latency_seconds: float = 0.0
    eligibility_specialist_latency_seconds: float = 0.0
    employee_lookup_latency_seconds: float = 0.0
    specialist_call_count: int = 0
    handoff_count: int = 0
    handoff_records: list[HandoffRecord] = field(default_factory=list)
    total_handoff_payload_tokens: int = 0
    model_prompt_tokens: int = 0
    model_completion_tokens: int = 0
    total_model_tokens: int = 0
    model_call_count: int = 0
    model_token_usage_source: str = "none"
    estimated_cost: float = 0.0
    cost_rate_per_1k_tokens: float = 0.001
    cost_formula: str = "(total_model_tokens / 1000) * 0.001"


@dataclass
class OrchestratorResult:
    """Structured response from the Multi-Agent Orchestrator."""
    question: str
    answer: str
    status: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    worker_responses: list[WorkerResponse] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: MultiAgentMetrics = field(default_factory=MultiAgentMetrics)
