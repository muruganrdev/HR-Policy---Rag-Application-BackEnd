"""
Langfuse observability module for the HR Policy RAG application.

This module provides a safe instrumentation layer around the existing RAG pipeline.
It initialises the Langfuse client from environment variables and exports the
@observe decorator so that pipeline functions can be traced without altering
their behaviour.

Configuration (via environment variables — never hard-coded):
    LANGFUSE_PUBLIC_KEY   – Langfuse project public key
    LANGFUSE_SECRET_KEY   – Langfuse project secret key
    LANGFUSE_HOST         – Langfuse server URL (default: https://cloud.langfuse.com)

Graceful degradation:
    If any of the required environment variables are missing, or if the Langfuse
    client fails to initialise for any reason, the module falls back to a no-op
    decorator so the RAG application continues to work normally.

Important:
    This module does NOT modify any RAG logic, prompts, thresholds, embeddings,
    chunking, reranking, or retrieval behaviour.  It is a read-only observability
    layer added on top of the existing pipeline.
"""

import logging
import os

# Load .env automatically if present (credentials are never hard-coded here)
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(override=False)  # override=False keeps shell env vars if already set
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 1.  Try to import the Langfuse @observe decorator.
#     Fall back to a transparent no-op if the SDK is absent or broken.
# ──────────────────────────────────────────────────────────────────────────────

_LANGFUSE_ENABLED = False

try:
    from langfuse import observe as _langfuse_observe  # type: ignore
    _LANGFUSE_ENABLED = True
    logger.debug("Langfuse SDK imported successfully.")
except Exception as _import_err:
    _langfuse_observe = None  # type: ignore
    logger.warning("Langfuse SDK not available: %s  — tracing disabled.", _import_err)


def _noop_observe(**kwargs) -> Callable:
    """No-op decorator used when Langfuse is unavailable."""
    def decorator(fn: Callable) -> Callable:
        return fn
    return decorator


def observe(**kwargs) -> Callable:
    """
    Wraps the Langfuse @observe decorator with a safe fallback.

    Any keyword arguments accepted by the Langfuse @observe are forwarded.
    If Langfuse is disabled or misconfigured the decorated function is returned
    unchanged so RAG behaviour is unaffected.
    """
    if _LANGFUSE_ENABLED and _langfuse_observe is not None:
        try:
            return _langfuse_observe(**kwargs)
        except Exception as err:
            logger.warning("Langfuse @observe setup failed: %s  — using no-op.", err)
    return _noop_observe(**kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# 2.  Validate required environment variables at import time (warn only).
# ──────────────────────────────────────────────────────────────────────────────

def _check_env() -> None:
    required = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.warning(
            "Langfuse environment variables not set: %s  — "
            "traces will not be exported to Langfuse.",
            ", ".join(missing),
        )


_check_env()


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Public helpers
# ──────────────────────────────────────────────────────────────────────────────

def is_enabled() -> bool:
    """Returns True if Langfuse tracing is active."""
    return (
        _LANGFUSE_ENABLED
        and bool(os.getenv("LANGFUSE_PUBLIC_KEY"))
        and bool(os.getenv("LANGFUSE_SECRET_KEY"))
    )
