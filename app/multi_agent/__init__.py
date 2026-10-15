"""Multi-Agent & A2A package for HR Policy RAG application."""

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
    calculate_context_resend_multiplier,
    calculate_model_token_ratio,
    estimate_payload_tokens,
    log_handoff,
    sanitize_payload,
)
from app.multi_agent.orchestrator import MultiAgentOrchestrator, run_multi_agent
from app.multi_agent.policy_specialist import PolicyRetrievalSpecialist

__all__ = [
    "TaskType",
    "WorkerStatus",
    "WorkerRequest",
    "WorkerResponse",
    "HandoffRecord",
    "MultiAgentMetrics",
    "OrchestratorResult",
    "PolicyRetrievalSpecialist",
    "EligibilityCalculationSpecialist",
    "MultiAgentOrchestrator",
    "run_multi_agent",
    "estimate_payload_tokens",
    "sanitize_payload",
    "log_handoff",
    "calculate_context_resend_multiplier",
    "calculate_model_token_ratio",
]
