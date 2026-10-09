"""Bounded, process-local conversation context for follow-up questions."""

from __future__ import annotations

import re
from collections import OrderedDict
from threading import RLock
from typing import Any


MAX_SHORT_TERM_TURNS = 6
MAX_SHORT_TERM_CONVERSATIONS = 1000

_REFERENCE_PATTERN = re.compile(
    r"\b(?:he|she|him|her|they|them|his|hers|their|theirs)\b", re.IGNORECASE
)
_POSSESSIVE_HR_REFERENCE = re.compile(
    r"\b(?:her|his|their|hers|theirs)\b(?=\s+(?:(?:annual|sick)\s+)?"
    r"(?:leave(?:\s+balance)?|salary|department|designation|role|job title|"
    r"email|phone|work mode|employment status|employment type|manager|"
    r"location|tenure|balance)\b)",
    re.IGNORECASE,
)


class ShortTermConversationMemory:
    """Thread-safe conversation-keyed history with LRU eviction."""

    def __init__(
        self,
        *,
        max_turns: int = MAX_SHORT_TERM_TURNS,
        max_conversations: int = MAX_SHORT_TERM_CONVERSATIONS,
    ) -> None:
        if max_turns < 1 or max_conversations < 1:
            raise ValueError("Memory limits must be positive")
        self.max_turns = max_turns
        self.max_conversations = max_conversations
        self._histories: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        self._lock = RLock()

    def get_history(
        self,
        conversation_id: str,
        *,
        role: str | None = None,
        employee_id: str | None = None,
    ) -> list[dict[str, str]]:
        """Return a copy so callers cannot mutate stored conversation state.

        If a conversation ID is reused with a different role or identity, the previous
        conversation history is evicted immediately to prevent data leakage across roles.
        """
        with self._lock:
            entry = self._histories.get(conversation_id)
            if entry is None:
                return []
            if isinstance(entry, dict):
                stored_role = entry.get("role")
                stored_emp_id = entry.get("employee_id")
                # If a role or identity was stored or is requested, verify they match
                if (stored_role is not None or role is not None) and (stored_role != role or stored_emp_id != employee_id):
                    self._histories.pop(conversation_id, None)
                    return []
                messages = entry.get("messages", [])
            else:
                messages = entry
            self._histories.move_to_end(conversation_id)
            return [dict(message) for message in messages]

    def add_exchange(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        *,
        role: str | None = None,
        employee_id: str | None = None,
    ) -> None:
        """Append one user/assistant turn and keep only the newest turns, bound to the caller's role context."""
        new_turns = [
            {"role": "user", "content": str(question)},
            {"role": "assistant", "content": str(answer)},
        ]
        with self._lock:
            entry = self._histories.pop(conversation_id, None)
            if isinstance(entry, dict):
                if entry.get("role") != role or entry.get("employee_id") != employee_id:
                    existing_messages = []
                else:
                    existing_messages = entry.get("messages", [])
            elif isinstance(entry, list):
                existing_messages = entry
            else:
                existing_messages = []

            existing_messages.extend(new_turns)
            self._histories[conversation_id] = {
                "messages": existing_messages[-self.max_turns * 2 :],
                "role": role,
                "employee_id": employee_id,
            }
            while len(self._histories) > self.max_conversations:
                self._histories.popitem(last=False)


def resolve_employee_reference(
    question: str, conversation_history: list[dict[str, Any]]
) -> str:
    """Resolve a pronoun only when the latest named prior user turn is unambiguous."""
    if not _REFERENCE_PATTERN.search(question):
        return question

    from app.router import _EMPLOYEE_NAMES

    known_names = sorted(_EMPLOYEE_NAMES, key=len, reverse=True)
    employee_name = None
    for message in reversed(conversation_history):
        if message.get("role") != "user" or not isinstance(message.get("content"), str):
            continue
        content = message["content"]
        matches: dict[str, str] = {}
        for known_name in known_names:
            match = re.search(
                rf"(?<!\w){re.escape(known_name)}(?!\w)", content, re.IGNORECASE
            )
            if match:
                matches[known_name] = match.group(0)
        if not matches:
            continue
        if len(matches) != 1:
            return question
        employee_name = next(iter(matches.values()))
        break

    if employee_name is None:
        return question

    possessives = {"her", "his", "their", "hers", "theirs"}
    resolved = _POSSESSIVE_HR_REFERENCE.sub(
        lambda match: f"{employee_name}'s"
        if match.group(0).casefold() in possessives
        else match.group(0),
        question,
    )
    return _REFERENCE_PATTERN.sub(employee_name, resolved)


_MY_HR_REFERENCE = re.compile(
    r"\bmy\s+((?:(?:annual|sick)\s+)?(?:leave(?:\s+balance)?|salary|pay|department|designation|role|job title|"
    r"email|phone|work mode|employment status|employment type|manager|location|tenure|balance))\b",
    re.IGNORECASE,
)


def resolve_self_reference(question: str, employee_name: str | None) -> str:
    """Resolve first-person references like 'my salary' to the selected employee identity."""
    if not employee_name or not str(employee_name).strip():
        return question
    name = str(employee_name).strip()
    return _MY_HR_REFERENCE.sub(rf"{name}'s \1", question)