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


def _load_employee_identifiers() -> None:
    """Populate the name and ID caches from the employee database."""
    global _EMPLOYEE_NAMES, _EMPLOYEE_IDS
    if not DATABASE_PATH.exists():
        return
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            rows = conn.execute(
                "SELECT employee_id, employee_name FROM employees"
            ).fetchall()
            _EMPLOYEE_IDS = {r[0] for r in rows}
            _EMPLOYEE_NAMES = {r[1].lower() for r in rows}
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
    r"\b(?:who\s+(?:works?\s+in|is\s+in|are\s+in|reports?\s+to)|"
    r"(?:which\s+)?employees?\s+(?:are\s+|is\s+)?(?:in|working\s+in)\s+|"
    r"(?:employees?\s+in)\s+(?:the\s+)?(?:\w+\s+)?department|"
    r"(?:list|show|get)\s+(?:all\s+)?employees?\s+(?:in|from|of)|"
    r"department\s+(?:members?|employees?|staff|team)|"
    r"reports?\s+to\s+\w+)",
    re.IGNORECASE,
)


def _contains_employee_name(question: str) -> bool:
    """Check whether the question contains a known employee name."""
    q_lower = question.lower()
    return any(name in q_lower for name in _EMPLOYEE_NAMES) or (
        _extract_employee_lookup_name(question) is not None
    )


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


def route_question(question: str) -> str:
    """Determine whether a question should be routed to 'agent' or 'rag'.

    Routes to 'agent' when the question references:
    - A known employee by name (e.g. "Priya Nair's leave balance")
    - A known employee by ID (e.g. "employee 005")
    - A department/manager team query (e.g. "who works in Engineering?")

    Defaults conservatively to 'rag' for all general policy questions.
    """
    if not question or not isinstance(question, str):
        return "rag"

    q = question.strip()
    if not q:
        return "rag"

    # Check employee-specific identifiers
    if _contains_employee_id(q):
        return "agent"

    if _contains_employee_name(q):
        return "agent"

    # Check team/department queries
    if _is_team_query(q):
        return "agent"

    return "rag"
