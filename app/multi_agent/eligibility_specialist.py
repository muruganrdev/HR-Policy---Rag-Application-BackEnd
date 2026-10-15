"""Eligibility-Calculation Specialist Agent.

Responsible for calculating annual leave disposition and evaluating eligibility
under explicit policy limits using deterministic arithmetic. Identifies missing
inputs explicitly rather than guessing or fabricating values.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent import _policy_numeric_limit
from app.multi_agent.contracts import TaskType, WorkerRequest, WorkerResponse, WorkerStatus
from app.tools import calculate_annual_leave_disposition

logger = logging.getLogger(__name__)


class EligibilityCalculationSpecialist:
    """Specialist agent for evaluating leave disposition under policy limits."""

    def __init__(self, name: str = "EligibilityCalculationSpecialist"):
        self.name = name

    def execute(self, request: WorkerRequest) -> WorkerResponse:
        """Execute a deterministic calculation request."""
        if request.task_type != TaskType.ELIGIBILITY_CALCULATION:
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.INVALID_INPUT,
                error=f"Unsupported task type for eligibility specialist: {request.task_type}",
            )

        context = request.context or {}
        leave_balance = context.get("leave_balance")
        carry_over_limit = context.get("carry_over_limit")
        encashment_limit = context.get("encashment_limit")
        policy_evidence = context.get("policy_evidence") or context.get("policy_result")

        # Derive limits from policy evidence if not passed directly
        if carry_over_limit is None and policy_evidence:
            carry_over_limit = _policy_numeric_limit(policy_evidence, keyword="carry_over")
        if encashment_limit is None and policy_evidence:
            encashment_limit = _policy_numeric_limit(policy_evidence, keyword="encashment")

        # Validate presence of required inputs
        missing_inputs = []
        if leave_balance is None:
            missing_inputs.append("leave_balance")
        if carry_over_limit is None:
            missing_inputs.append("carry_over_limit")
        if encashment_limit is None:
            missing_inputs.append("encashment_limit")

        if missing_inputs:
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.INCOMPLETE,
                error=f"Cannot perform calculation; missing required inputs: {', '.join(missing_inputs)}",
                result={
                    "inputs_provided": {
                        "leave_balance": leave_balance,
                        "carry_over_limit": carry_over_limit,
                        "encashment_limit": encashment_limit,
                    },
                    "missing_inputs": missing_inputs,
                },
                metadata={"agent": self.name},
            )

        try:
            leave_balance_float = float(leave_balance)
            carry_over_limit_float = float(carry_over_limit)
            encashment_limit_float = float(encashment_limit)

            disposition = calculate_annual_leave_disposition(
                leave_balance=leave_balance_float,
                carry_over_limit=carry_over_limit_float,
                encashment_limit=encashment_limit_float,
            )

            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.SUCCESS,
                result={
                    "inputs": {
                        "leave_balance": leave_balance_float,
                        "carry_over_limit": carry_over_limit_float,
                        "encashment_limit": encashment_limit_float,
                    },
                    "calculation": disposition,
                },
                metadata={"agent": self.name},
            )

        except (ValueError, TypeError) as exc:
            return WorkerResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                status=WorkerStatus.ERROR,
                error=f"Calculation error: {type(exc).__name__}: {str(exc)}",
                metadata={"agent": self.name},
            )
