"""Instrumentation and telemetry for the Multi-Agent architecture.

Provides latency measurement, model token tracking, per-handoff payload token
estimation, and structured logging to evaluation/week10/handoffs.log.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.multi_agent.contracts import HandoffRecord

logger = logging.getLogger(__name__)

# Project root directory
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_HANDOFF_LOG_PATH = ROOT_DIR / "evaluation" / "week10" / "handoffs.log"
SENSITIVE_KEYS = frozenset({
    "annual_salary",
    "phone",
    "email",
    "salary",
    "bank_account",
    "password",
    "token",
})


def estimate_payload_tokens(payload: Any) -> int:
    """Consistently estimate payload tokens using ~4 chars per token.
    
    Uses standard JSON serialization to measure serialized size.
    """
    if payload is None:
        return 0
    if isinstance(payload, (int, float, bool)):
        return 1
    if isinstance(payload, str):
        text = payload
    else:
        try:
            text = json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            text = str(payload)
    return max(1, math.ceil(len(text) / 4))


def sanitize_payload(payload: Any) -> Any:
    """Redact sensitive personal employee fields before logging."""
    if isinstance(payload, dict):
        sanitized = {}
        for k, v in payload.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = sanitize_payload(v)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload


def summarize_payload(payload: Any, max_len: int = 250) -> dict[str, Any]:
    """Create a concise, non-sensitive summary dictionary of a payload for logging."""
    sanitized = sanitize_payload(payload)
    if isinstance(sanitized, dict):
        summary = {}
        for k, v in sanitized.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                s_str = str(v)
                summary[k] = s_str[:max_len] + "..." if len(s_str) > max_len else v
            elif isinstance(v, list):
                summary[k] = f"list(len={len(v)})"
            elif isinstance(v, dict):
                summary[k] = f"dict(keys={list(v.keys())})"
        return summary
    return {"summary": str(sanitized)[:max_len]}


def log_handoff(
    record: HandoffRecord,
    log_path: Path | str | None = None,
) -> None:
    """Append a structured HandoffRecord as a JSON line to the handoff log file."""
    target_path = Path(log_path) if log_path else DEFAULT_HANDOFF_LOG_PATH
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": record.timestamp,
            "correlation_id": record.correlation_id,
            "request_id": record.request_id,
            "source": record.source,
            "destination": record.destination,
            "task_type": record.task_type,
            "status": record.status,
            "duration_seconds": record.duration_seconds,
            "request_tokens": record.request_tokens,
            "response_tokens": record.response_tokens,
            "combined_payload_tokens": record.combined_payload_tokens,
            "token_count_method": record.token_count_method,
            "payload_summary": record.payload_summary,
        }
        with open(target_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to write handoff log to %s: %s", target_path, exc)


def calculate_model_token_ratio(
    multi_agent_model_tokens: int,
    single_agent_model_tokens: int,
) -> float:
    """Calculate the relative model token usage ratio.
    
    Formula: multi_agent_total_model_tokens / single_agent_total_model_tokens.
    Numerator: Total Ollama model tokens consumed by the Multi-Agent orchestrator/specialists.
    Denominator: Total Ollama model tokens consumed by the Single-Agent ReAct loop.
    
    Note: This is a ratio of model-token totals between execution modes, not a direct
    measurement of repeated or duplicated context.
    """
    if single_agent_model_tokens <= 0:
        return 0.0 if multi_agent_model_tokens == 0 else 1.0
    return round(multi_agent_model_tokens / single_agent_model_tokens, 4)


# Backwards compatibility alias for existing callers
calculate_context_resend_multiplier = calculate_model_token_ratio
