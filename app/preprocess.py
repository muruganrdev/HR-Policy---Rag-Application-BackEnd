import ollama
from typing import Optional

def preprocess_question(question: str) -> str:
    """Correct spelling/grammar of a user question.

    The function attempts to call the local Ollama LLM (llama3) with a
    deterministic prompt that asks only for a corrected version of the
    input question.  If the LLM call fails for any reason (network error,
    model not loaded, etc.) the original question is returned unchanged.

    This is a lightweight *pre‑processing* step – it does **not** rewrite
    the intent, does not add information, and never answers the question.
    """
    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that corrects user questions for grammar and spelling. Return only the corrected question, without any explanation or additional text."},
                {"role": "user", "content": f"Correct this question: {question}"}
            ],
            # Deterministic output – temperature 0 avoids creative changes
            options={"temperature": 0.0}
        )
        corrected = response.get("message", {}).get("content", "").strip()
        if corrected:
            return corrected
    except Exception:
        # Any error (e.g., model not reachable) falls back to original
        pass
    return question
