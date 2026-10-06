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

    def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        """Return a copy so callers cannot mutate stored conversation state."""
        with self._lock:
            history = self._histories.get(conversation_id)
            if history is None:
                return []
            self._histories.move_to_end(conversation_id)
            return [dict(message) for message in history]

    def add_exchange(
        self, conversation_id: str, question: str, answer: str
    ) -> None:
        """Append one user/assistant turn and keep only the newest turns."""
        messages = [
            {"role": "user", "content": str(question)},
            {"role": "assistant", "content": str(answer)},
        ]
        with self._lock:
            history = self._histories.pop(conversation_id, [])
            history.extend(messages)
            self._histories[conversation_id] = history[-self.max_turns * 2 :]
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