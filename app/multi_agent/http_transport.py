"""HTTP transport adapter for Specialist Workers and fault injection (Week 10 Phase 4).

Provides an isolated, test-only HTTP transport adapter for specialist delegation
and controlled fault injection to exercise the required policy-worker HTTP 500 scenario.
Disabled by default to prevent altering normal benchmark or production behavior.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.multi_agent.contracts import (
    TaskType,
    WorkerRequest,
    WorkerResponse,
    WorkerStatus,
)
from app.multi_agent.policy_specialist import PolicyRetrievalSpecialist

logger = logging.getLogger(__name__)

# Controlled fault injection configuration (strictly disabled by default)
FAULT_INJECTION_CONFIG: dict[str, Any] = {
    "enabled": False,
    "target_case_id": None,
    "target_task_type": "policy_retrieval",
    "status_code": 500,
    "error_message": "Internal Server Error: Policy Retrieval database connection failed.",
    "failure_count": None,
    "attempt_counter": 0,
}


def configure_fault_injection(
    enabled: bool = False,
    target_case_id: str | None = None,
    status_code: int = 500,
    error_message: str | None = None,
    failure_count: int | None = None,
) -> None:
    """Configure or reset the controlled fault injection mechanism."""
    FAULT_INJECTION_CONFIG["enabled"] = enabled
    FAULT_INJECTION_CONFIG["target_case_id"] = target_case_id
    FAULT_INJECTION_CONFIG["status_code"] = status_code
    FAULT_INJECTION_CONFIG["failure_count"] = failure_count
    FAULT_INJECTION_CONFIG["attempt_counter"] = 0
    if error_message:
        FAULT_INJECTION_CONFIG["error_message"] = error_message


def reset_fault_injection() -> None:
    """Safely disable all fault injection settings."""
    FAULT_INJECTION_CONFIG["enabled"] = False
    FAULT_INJECTION_CONFIG["target_case_id"] = None
    FAULT_INJECTION_CONFIG["failure_count"] = None
    FAULT_INJECTION_CONFIG["attempt_counter"] = 0


class HttpPolicySpecialist:
    """Policy Retrieval Specialist adapter that delegates over HTTP transport with bounded retries.

    Makes actual HTTP requests to the worker endpoint and accurately reflects HTTP
    status codes (including HTTP 500) into WorkerResponse error contracts.
    Implements bounded retries with exponential backoff and jitter for transient 5xx errors.
    """

    def __init__(
        self,
        endpoint_url: str = "http://127.0.0.1:8001/internal/workers/policy-retrieval",
        name: str = "HttpPolicySpecialist",
        fallback_specialist: PolicyRetrievalSpecialist | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_base_seconds: float = 0.05,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.endpoint_url = endpoint_url
        self.name = name
        self.fallback = fallback_specialist or PolicyRetrievalSpecialist()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff duration with optional random jitter."""
        import random
        delay = self.backoff_base_seconds * (self.backoff_factor ** attempt)
        if self.jitter:
            delay += random.uniform(0.0, self.backoff_base_seconds)
        return max(0.001, delay)

    def execute(self, request: WorkerRequest) -> WorkerResponse:
        """Execute request over HTTP transport, with bounded retries for transient failures."""
        import time

        case_id = request.context.get("case_id") or getattr(request, "case_id", None)
        is_target_case = (
            FAULT_INJECTION_CONFIG["enabled"]
            and FAULT_INJECTION_CONFIG["target_case_id"] is not None
            and (case_id == FAULT_INJECTION_CONFIG["target_case_id"])
        )

        for attempt in range(self.max_retries + 1):
            total_attempts = attempt + 1

            # Controlled fault injection path (isolated to target test case)
            if is_target_case:
                current_attempt_idx = FAULT_INJECTION_CONFIG.get("attempt_counter", 0)
                FAULT_INJECTION_CONFIG["attempt_counter"] = current_attempt_idx + 1
                failure_limit = FAULT_INJECTION_CONFIG.get("failure_count")

                # If transient failure limit reached, recover to success
                if failure_limit is not None and current_attempt_idx >= failure_limit:
                    logger.info(
                        "Fault injection transient limit reached (%d attempts); recovering via fallback",
                        failure_limit,
                    )
                    res = self.fallback.execute(request)
                    res.metadata["retried"] = attempt > 0
                    res.metadata["attempts"] = total_attempts
                    return res

                status_code = FAULT_INJECTION_CONFIG.get("status_code", 500)
                err_msg = FAULT_INJECTION_CONFIG.get("error_message", "Internal Server Error in Policy Specialist")
                is_transient = status_code >= 500

                if is_transient and attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        "Policy worker HTTP error %d for request %s (attempt %d/%d, transient); retrying in %.3fs",
                        status_code,
                        request.request_id,
                        total_attempts,
                        self.max_retries + 1,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue

                logger.warning(
                    "Policy worker HTTP error %d for request %s (attempt %d/%d, %s): %s",
                    status_code,
                    request.request_id,
                    total_attempts,
                    self.max_retries + 1,
                    "exhausted" if attempt >= self.max_retries else "non-retryable",
                    err_msg,
                )
                return WorkerResponse(
                    request_id=request.request_id,
                    task_type=request.task_type,
                    status=WorkerStatus.ERROR,
                    result={},
                    evidence=[],
                    error=f"HTTP {status_code} Internal Server Error from policy retrieval worker endpoint: {err_msg}",
                    metadata={
                        "transport": "http_worker_endpoint",
                        "status_code": status_code,
                        "endpoint": self.endpoint_url,
                        "error_detail": err_msg,
                        "attempts": total_attempts,
                        "retried": attempt > 0,
                        "retries_exhausted": attempt >= self.max_retries,
                    },
                )

            # Normal HTTP transport path
            payload = {
                "task_type": request.task_type.value,
                "question": request.question,
                "context": request.context,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id,
                "target_case_id": case_id,
            }
            payload_bytes = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                self.endpoint_url,
                data=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Case-ID": str(case_id or ""),
                    "X-Fault-Inject": "false",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    status_code = resp.status
                    body = json.loads(resp.read().decode("utf-8"))
                    return WorkerResponse(
                        request_id=body.get("request_id", request.request_id),
                        task_type=request.task_type,
                        status=WorkerStatus(body.get("status", "success")),
                        result=body.get("result", {}),
                        evidence=body.get("evidence", []),
                        error=body.get("error"),
                        metadata={
                            "transport": "http",
                            "status_code": status_code,
                            "endpoint": self.endpoint_url,
                            "attempts": total_attempts,
                            "retried": attempt > 0,
                            **body.get("metadata", {}),
                        },
                    )
            except urllib.error.HTTPError as http_err:
                status_code = http_err.code
                err_body = http_err.read().decode("utf-8", errors="replace")
                is_transient = status_code >= 500

                # Retry only transient 5xx errors; permanent client errors (4xx) fail fast
                if is_transient and attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        "Policy worker HTTP error %d for request %s (attempt %d/%d); retrying in %.3fs",
                        status_code,
                        request.request_id,
                        total_attempts,
                        self.max_retries + 1,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue

                logger.warning(
                    "Policy worker HTTP error %d for request %s (attempt %d/%d, %s): %s",
                    status_code,
                    request.request_id,
                    total_attempts,
                    self.max_retries + 1,
                    "exhausted" if attempt >= self.max_retries else "non-retryable",
                    err_body,
                )
                return WorkerResponse(
                    request_id=request.request_id,
                    task_type=request.task_type,
                    status=WorkerStatus.ERROR,
                    result={},
                    evidence=[],
                    error=f"HTTP {status_code} Internal Server Error from policy retrieval worker endpoint: {err_body}",
                    metadata={
                        "transport": "http",
                        "status_code": status_code,
                        "endpoint": self.endpoint_url,
                        "error_detail": err_body,
                        "attempts": total_attempts,
                        "retried": attempt > 0,
                        "retries_exhausted": attempt >= self.max_retries,
                    },
                )
            except (urllib.error.URLError, TimeoutError, OSError) as url_err:
                if attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        "HTTP connection failed (%s, attempt %d/%d); retrying in %.3fs",
                        url_err,
                        total_attempts,
                        self.max_retries + 1,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue

                logger.warning(
                    "HTTP connection failed (%s) after %d attempts, falling back to in-process worker",
                    url_err,
                    total_attempts,
                )
                res = self.fallback.execute(request)
                res.metadata["attempts"] = total_attempts
                res.metadata["retried"] = attempt > 0
                return res

        # Safety fallback (should never be reached)
        return WorkerResponse(
            request_id=request.request_id,
            task_type=request.task_type,
            status=WorkerStatus.ERROR,
            error="Retries exhausted without response",
            metadata={"attempts": self.max_retries + 1, "retried": True},
        )
