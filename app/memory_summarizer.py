from __future__ import annotations

import re
from typing import Any

import ollama

OLLAMA_MODEL = "llama3"
OLLAMA_TEMPERATURE = 0.0


def _fallback_summary(conversation: str) -> str:
    text = re.sub(r"\s+", " ", str(conversation or "")).strip()
    if not text:
        return "No conversation content to summarize."
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = " ".join(s.strip() for s in sentences if s.strip())
    return summary[:600].rstrip() + ("..." if len(summary) > 600 else "")


def summarize_conversation(conversation: str) -> str:
    """Summarize a conversation using the installed Ollama llama3 model.

    The function preserves key facts and avoids fabrication; if the Ollama service
    is unavailable it returns a safe deterministic fallback based on the text itself.
    """
    text = str(conversation or "").strip()
    if not text:
        return "No conversation content to summarize."

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Summarize the conversation below in a concise, factual form. "
                        "Keep the important facts and do not invent information. "
                        "Return only the summary.\n\n"
                        f"{text}"
                    ),
                }
            ],
            options={"temperature": OLLAMA_TEMPERATURE},
        )
        content = response.get("message", {}).get("content", "") if isinstance(response, dict) else str(response)
        summary = str(content).strip()
        if summary:
            return summary
    except Exception:
        pass

    return _fallback_summary(text)
