"""Deterministic router for directing user questions to Normal RAG or Agent.

Routes to 'agent' when the question references:
- A known employee ID (e.g. 005)
- A known employee name (e.g. Priya Nair)
- Department/manager/team queries requiring database access

Defaults conservatively to 'rag' for all general policy questions.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "employee.db"

# ---------------------------------------------------------------------------
# Employee name cache (loaded once at import time from SQLite)
# ---------------------------------------------------------------------------

_EMPLOYEE_NAMES: set[str] = set()
_EMPLOYEE_IDS: set[str] = set()
_MANAGER_NAMES: set[str] = set()


def _load_employee_identifiers() -> None:
    """Populate the name, ID, and manager caches from the employee database."""
    global _EMPLOYEE_NAMES, _EMPLOYEE_IDS, _MANAGER_NAMES
    if not DATABASE_PATH.exists():
        return
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            rows = conn.execute(
                "SELECT employee_id, employee_name, manager_name FROM employees"
            ).fetchall()
            _EMPLOYEE_IDS = {r[0] for r in rows if r[0]}
            _EMPLOYEE_NAMES = {r[1].lower() for r in rows if r[1]}
            _MANAGER_NAMES = {r[2].lower() for r in rows if r[2]}
    except Exception:
        pass


_load_employee_identifiers()


def reload_employee_identifiers() -> None:
    """Re-read employee names/IDs from the database (useful after DB changes)."""
    _load_employee_identifiers()


# ---------------------------------------------------------------------------
# Patterns for employee-specific questions
# ---------------------------------------------------------------------------

# Match simple numeric employee IDs like 001, 005
EMPLOYEE_ID_PATTERN = re.compile(
    r"\bemployee\s+(\d{3})\b|\b(\d{3})\b(?='s)",
    re.IGNORECASE,
)

# Broader numeric ID in "employee NNN" context
EMPLOYEE_ID_CONTEXT = re.compile(
    r"\bemployee\s+(?:id\s+)?(\d{3})\b",
    re.IGNORECASE,
)

_FULL_PERSON_NAME = r"([A-Za-z][A-Za-z'-]*\s+[A-Za-z][A-Za-z'-]*)"
_EMPLOYEE_LOOKUP_NAME_PATTERNS = (
    re.compile(
        rf"\b{_FULL_PERSON_NAME}'s\s+(?:annual\s+)?(?:salary|pay|department|email|phone|"
        r"annual leave balance|leave balance|work mode|designation|manager)\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bwhat\s+department\s+does\s+{_FULL_PERSON_NAME}\s+work\s+in\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:find|look\s+up|lookup)\s+employee\s+(?:named\s+)?{_FULL_PERSON_NAME}\b",
        re.IGNORECASE,
    ),
)

# Department/manager/team query indicators
TEAM_QUERY_PATTERNS = re.compile(
    r"\b(?:"
    r"who\s+(?:all\s+)?(?:are|is)?\s*(?:working|work|works)\s+(?:in|under)|"
    r"who\s+(?:all\s+)?(?:are|is)\s+in|"
    r"who\s+(?:all\s+)?reports?\s+to|"
    r"(?:which\s+)?employees?\s+(?:(?:are|is|work|works)\s+(?:in|under)|working\s+(?:in|under))\s+|"
    r"(?:employees?\s+in)\s+(?:the\s+)?(?:\w+\s+)?department|"
    r"(?:list|show|get)\s+(?:all\s+)?employees?\s+(?:in|from|of|under)|"
    r"(?:list|show|get|who\s+(?:are|is))\s+(?:all\s+)?(?:\w+(?:'s)?\s+)?direct\s+reports|"
    r"direct\s+reports|"
    r"department\s+(?:members?|employees?|staff|team)|"
    r"under\s+(?:this\s+manager|me)|"
    r"reports?\s+to\b|"
    r"reporting\s+to\b|"
    r"team\s+of\b"
    r")",
    re.IGNORECASE,
)


def _contains_employee_name(question: str) -> bool:
    """Check whether the question contains a known employee name."""
    q_lower = question.lower()
    return any(name in q_lower for name in _EMPLOYEE_NAMES) or (
        _extract_employee_lookup_name(question) is not None
    )


def _contains_manager_name(question: str) -> bool:
    """Check whether the question contains a known manager name."""
    q_lower = question.lower()
    return any(name in q_lower for name in _MANAGER_NAMES)


def _extract_employee_lookup_name(question: str) -> str | None:
    """Extract a full name only from employee-fact lookup question forms."""
    for pattern in _EMPLOYEE_LOOKUP_NAME_PATTERNS:
        match = pattern.search(question)
        if match:
            return match.group(1).strip()
    return None


def _contains_employee_id(question: str) -> bool:
    """Check for an explicitly requested three-digit employee identifier."""
    return bool(
        EMPLOYEE_ID_CONTEXT.search(question)
        or EMPLOYEE_ID_PATTERN.search(question)
    )


def _is_team_query(question: str) -> bool:
    """Check whether the question is a department/manager team query."""
    return bool(TEAM_QUERY_PATTERNS.search(question))


def classify_question_intent(question: str) -> str:
    """Classify user question intent for tool selection and downstream processing."""
    if not question or not isinstance(question, str):
        return "policy_retrieval"
    q = question.strip()
    q_lower = q.lower()

    if any(
        term in q_lower
        for term in (
            "add an employee",
            "add a new employee",
            "create an employee",
            "create a new employee",
            "adding an employee",
            "creating an employee",
            "add employee",
            "create employee",
            "onboard an employee",
            "onboarding an employee",
        )
    ) or (
        any(
            term in q_lower
            for term in (
                "what information",
                "what details",
                "what fields",
                "what data",
                "information required",
                "information needed",
            )
        )
        and any(term in q_lower for term in ("add", "create", "new employee", "register"))
    ):
        return "employee_creation"

    if _is_team_query(q) or _contains_manager_name(q):
        if any(dept in q_lower for dept in ("engineering", "finance", "hr", "sales", "marketing", "operations")) or "department" in q_lower:
            return "department_roster"
        return "manager_team"

    if _contains_employee_id(q) or _contains_employee_name(q):
        if any(term in q_lower for term in ("disposition", "handled", "how should", "lapse", "lapsed")) or (
            any(term in q_lower for term in ("carry", "carried")) and any(term in q_lower for term in ("encash", "remaining", "balance"))
        ):
            return "leave_disposition"
        return "employee_fact"

    return "policy_retrieval"


def route_question(question: str) -> str:
    """Determine whether a question should be routed to 'agent' or 'rag'.

    In the Agent-First architecture, the Agent is the primary entry point for all
    user questions, dispatching dynamically to policy RAG or employee tools.
    """
    if not question or not isinstance(question, str) or not question.strip():
        return "agent"

    return "agent"
