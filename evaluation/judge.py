"""LLM-as-a-Judge v1 for semantic answer quality evaluation."""

from __future__ import annotations

import json
import os
from typing import Any

import ollama


DEFAULT_MODEL = "llama3"
DEFAULT_TEMPERATURE = 0.0


def _load_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "judge_v1.txt")
    with open(prompt_path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _has_single_missing_object_brace(text: str) -> bool:
    """Allow only one unambiguous missing closing brace on a JSON object."""
    if not text.startswith("{") or text.endswith("}"):
        return False

    curly_depth = 0
    square_depth = 0
    in_string = False
    escaped = False

    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "{":
            curly_depth += 1
        elif character == "}":
            curly_depth -= 1
        elif character == "[":
            square_depth += 1
        elif character == "]":
            square_depth -= 1

        if curly_depth < 0 or square_depth < 0:
            return False

    return not in_string and square_depth == 0 and curly_depth == 1


def _parse_structured_response(raw_content: Any) -> dict | None:
    if raw_content is None:
        return None

    text = str(raw_content).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    normalized_text = text.replace("\\'", "'")

    try:
        payload = json.loads(normalized_text)
    except json.JSONDecodeError:
        if not _has_single_missing_object_brace(normalized_text):
            return None
        try:
            payload = json.loads(normalized_text + "}")
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None
    return payload


def _validate_result(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {"verdict": "FAIL", "reason": "Judge returned an invalid response."}

    verdict = str(payload.get("verdict", "")).upper()
    reason = payload.get("reason", "")

    if verdict in {"PASS", "FAIL"} and isinstance(reason, str) and reason.strip():
        return {"verdict": verdict, "reason": reason.strip()}

    return {"verdict": "FAIL", "reason": "Judge returned an invalid response."}


def judge_answer(question: str, answer: str, context: str, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE) -> dict:
    """Judge semantic correctness using only the supplied question, answer, and policy context."""
    try:
        prompt_template = _load_prompt()
        user_prompt = prompt_template.format(
            question=question,
            answer=answer,
            context=context,
        )

        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an evaluation judge. Evaluate semantic correctness only. "
                        "Use only the supplied question, answer, and context. Do not use outside knowledge. "
                        "Do not reward an answer merely because it sounds plausible. Do not evaluate deterministic "
                        "formatting or assertion criteria. Return ONLY the required structured result."
                    ),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            options={"temperature": temperature},
        )

        if isinstance(response, dict):
            message = response.get("message", {})
            content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        else:
            message = getattr(response, "message", None)
            content = getattr(message, "content", None)
        parsed = _parse_structured_response(content)
        return _validate_result(parsed)

    except Exception:
        return {"verdict": "FAIL", "reason": "Judge execution failed."}


__all__ = ["judge_answer"]
