"""A2A AgentCard metadata definitions for the HR Policy Multi-Agent System (Week 10 Phase 5).

Provides discoverable AgentCard metadata for:
1. MultiAgentOrchestrator
2. PolicyRetrievalSpecialist
3. EligibilityCalculationSpecialist

Note: These cards represent proposed/metadata-only A2A descriptions as the system
currently operates with typed in-process contracts and lightweight REST adapters rather
than a full multi-node A2A streaming transport.
"""

from __future__ import annotations

import json
from typing import Any


ORCHESTRATOR_AGENT_CARD: dict[str, Any] = {
    "name": "HR Policy Multi-Agent Orchestrator",
    "agent_id": "urn:agent:acme:hr-orchestrator",
    "version": "1.0.0",
    "protocol_version": "a2a/0.1-draft (metadata-only)",
    "description": (
        "Supervisory agent responsible for query decomposition, routing, and specialist delegation. "
        "Coordinates policy retrieval and eligibility calculations to synthesize grounded HR answers."
    ),
    "role": "orchestrator",
    "compliance_status": "proposed_metadata_only",
    "transport": "in-process typed contract / REST adapter",
    "skills": [
        {
            "id": "hr_intent_decomposition",
            "name": "HR Intent Decomposition",
            "description": "Analyzes employee and policy questions to identify required sub-tasks.",
            "input_schema": {"type": "string", "description": "User question"},
        },
        {
            "id": "specialist_delegation",
            "name": "Specialist Delegation",
            "description": "Delegates sub-tasks to Policy Retrieval and Eligibility Calculation specialists.",
            "supported_workers": ["policy_retrieval", "eligibility_calculation"],
        },
        {
            "id": "answer_synthesis",
            "name": "Answer Synthesis",
            "description": "Combines verified evidence and calculation results into a final user answer.",
        },
    ],
    "input_modes": ["application/json", "text/plain"],
    "output_modes": ["application/json", "text/markdown"],
    "endpoints": [
        {
            "protocol": "http/json",
            "url": "http://127.0.0.1:8001/ask",
            "method": "POST",
            "parameters": {"agent_mode": "multi"},
            "auth": "RoleAccessPrincipal header/cookie (Super Admin, Manager, Employee)",
        }
    ],
    "supported_lifecycle_states": [
        "submitted",
        "in_progress",
        "completed",
        "failed",
        "input_required",
    ],
    "security": {
        "authorization_required": True,
        "trusted_principal_enforcement": True,
        "data_minimization": True,
    },
}


POLICY_SPECIALIST_AGENT_CARD: dict[str, Any] = {
    "name": "Policy Retrieval Specialist",
    "agent_id": "urn:agent:acme:policy-retrieval-specialist",
    "version": "1.0.0",
    "protocol_version": "a2a/0.1-draft (metadata-only)",
    "description": (
        "Worker specialist strictly dedicated to retrieving verified HR policy evidence from "
        "ChromaDB and authoritative jurisdiction policy registries without hallucinating or modifying text."
    ),
    "role": "specialist_worker",
    "compliance_status": "proposed_metadata_only",
    "transport": "in-process typed contract / HTTP internal endpoint",
    "skills": [
        {
            "id": "policy_retrieval",
            "name": "HR Policy Evidence Retrieval",
            "description": "Searches HR policy documents and extracts relevant text chunks.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "context": {
                        "type": "object",
                        "properties": {
                            "jurisdiction": {"type": "string", "enum": ["INDIA", "GERMANY", "US", "GLOBAL"]},
                            "query": {"type": "string"},
                        },
                    },
                },
                "required": ["question"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["success", "error", "incomplete"]},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "chunk_index": {"type": "integer"},
                                "content": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    ],
    "input_modes": ["application/json"],
    "output_modes": ["application/json"],
    "endpoints": [
        {
            "protocol": "http/json",
            "url": "http://127.0.0.1:8001/internal/workers/policy-retrieval",
            "method": "POST",
            "auth": "Internal gateway / RoleAccessPrincipal",
        }
    ],
    "supported_lifecycle_states": [
        "submitted",
        "in_progress",
        "completed",
        "failed",
        "incomplete",
    ],
}


ELIGIBILITY_SPECIALIST_AGENT_CARD: dict[str, Any] = {
    "name": "Eligibility Calculation Specialist",
    "agent_id": "urn:agent:acme:eligibility-calculation-specialist",
    "version": "1.0.0",
    "protocol_version": "a2a/0.1-draft (metadata-only)",
    "description": (
        "Deterministic specialist executing mathematical leave carry-over, encashment, and lapse calculations. "
        "Guarantees arithmetic invariance (carryover + encashment + lapse == leave_balance)."
    ),
    "role": "specialist_worker",
    "compliance_status": "proposed_metadata_only",
    "transport": "in-process typed contract",
    "skills": [
        {
            "id": "calculate_annual_leave_disposition",
            "name": "Annual Leave Disposition Calculation",
            "description": "Computes carry-over, encashable, and lapsed days deterministically from policy limits.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "leave_balance": {"type": "number"},
                    "carry_over_limit": {"type": "number"},
                    "encashment_limit": {"type": "number"},
                },
                "required": ["leave_balance", "carry_over_limit", "encashment_limit"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "carryover_days": {"type": "number"},
                    "encashable_days": {"type": "number"},
                    "lapsed_days": {"type": "number"},
                    "calculation_details": {"type": "string"},
                },
            },
        }
    ],
    "input_modes": ["application/json"],
    "output_modes": ["application/json"],
    "endpoints": [
        {
            "protocol": "in_process",
            "dispatch": "EligibilityCalculationSpecialist.execute(WorkerRequest)",
        }
    ],
    "supported_lifecycle_states": [
        "submitted",
        "in_progress",
        "completed",
        "failed",
        "input_required",
    ],
}


ALL_AGENT_CARDS: list[dict[str, Any]] = [
    ORCHESTRATOR_AGENT_CARD,
    POLICY_SPECIALIST_AGENT_CARD,
    ELIGIBILITY_SPECIALIST_AGENT_CARD,
]


def export_agent_cards_json() -> str:
    """Return JSON string of all published AgentCards."""
    return json.dumps(ALL_AGENT_CARDS, indent=2)
