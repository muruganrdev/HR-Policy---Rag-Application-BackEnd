"""Policy-Retrieval Specialist Agent.

Responsible strictly for finding and returning relevant HR policy evidence
from the existing ChromaDB / HR policy documents. Avoids employee database
operations and never manufactures citations or excerpts.
"""

from __future__ import annotations

import logging
from typing import Any

from app.multi_agent.contracts import TaskType, WorkerRequest, WorkerResponse, WorkerStatus
from app.tools import Jurisdiction, lookup_annual_leave_policy
from app.search import search

logger = logging.getLogger(__name__)


class PolicyRetrievalSpecialist:
    """Specialist agent for retrieving verified HR policy evidence."""

    def __init__(self, name: str = "PolicyRetrievalSpecialist"):
        self.name = name

    def execute(self, request: WorkerRequest) -> WorkerResponse:
        """Execute a policy retrieval request and return structured evidence."""
        if request.task_type != TaskType.POLICY_RETRIEVAL:
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.INVALID_INPUT,
                error=f"Unsupported task type for policy retrieval specialist: {request.task_type}",
            )

        jurisdiction_val = request.context.get("jurisdiction", "INDIA")
        query_text = request.context.get("query") or request.question

        try:
            # 1. If asking specifically about annual leave / limits for INDIA, use official policy tool
            if jurisdiction_val == "INDIA" and any(
                term in query_text.lower()
                for term in ("annual leave", "carry-over", "carry over", "encash", "lapse", "vacation")
            ):
                policy_data = lookup_annual_leave_policy(Jurisdiction.INDIA)
            else:
                # 2. General search query via existing ChromaDB vector search
                search_results = search(query_text)
                policy_data = {
                    "jurisdiction": jurisdiction_val,
                    "policy_area": "general_policy",
                    "results": search_results,
                }

            raw_results = policy_data.get("results", [])
            evidence = []
            for item in raw_results:
                if isinstance(item, dict) and "content" in item:
                    evidence.append({
                        "source": item.get("source", "unknown"),
                        "chunk_index": item.get("chunk_index"),
                        "content": str(item.get("content", "")),
                    })

            if not evidence:
                return WorkerResponse(
                    request_id=request.request_id,
                    task_type=request.task_type,
                    status=WorkerStatus.INCOMPLETE,
                    result={"policy_data": policy_data},
                    evidence=[],
                    error="No relevant policy evidence found for query.",
                    metadata={"agent": self.name},
                )

            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.SUCCESS,
                result={
                    "jurisdiction": policy_data.get("jurisdiction", jurisdiction_val),
                    "policy_area": policy_data.get("policy_area", "annual_leave_balance"),
                    "results": evidence,
                },
                evidence=evidence,
                metadata={"agent": self.name, "evidence_count": len(evidence)},
            )

        except Exception as exc:
            logger.exception("Policy retrieval failed for request %s: %s", request.request_id, exc)
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.ERROR,
                error=f"Policy retrieval execution error: {type(exc).__name__}: {str(exc)}",
                metadata={"agent": self.name},
            )
