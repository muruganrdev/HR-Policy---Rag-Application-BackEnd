import ollama

# Model name – keep consistent with app.rag
OLLAMA_MODEL = "llama3"

def _token_overlap(original: str, rewritten: str) -> float:
    """Return the fraction of original tokens that appear in the rewritten string.

    Tokenisation is whitespace‑based and case‑insensitive. The result is a
    value between 0 and 1, where 1 means all original tokens are retained.
    """
    orig_tokens = [t.lower() for t in original.split() if t]
    rew_tokens = set(t.lower() for t in rewritten.split() if t)
    if not orig_tokens:
        return 0.0
    common = sum(1 for t in orig_tokens if t in rew_tokens)
    return common / len(orig_tokens)

def rewrite_question(question: str) -> str:
    """Rewrite a pre‑processed question for better retrieval while preserving intent.

    Calls the local Ollama LLM (llama3) with a deterministic prompt. If the rewrite
    drops too many essential tokens (overlap < 0.60) or an error occurs, the original
    pre‑processed question is returned unchanged.
    """
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that rewrites a user's question to improve semantic document retrieval. "
                        "Preserve the original intent and retain all domain‑specific terms such as "
                        "'progressive disciplinary process', 'Verbal Warning', 'Written Warning', 'PIP', and 'Termination'. "
                        "Return ONLY the rewritten question."
                    ),
                },
                {"role": "user", "content": f"Rewrite this question for retrieval: {question}"},
            ],
            options={"temperature": 0.0},  # deterministic output
        )
        rewritten = response.get("message", {}).get("content", "").strip()
        if rewritten:
            overlap = _token_overlap(question, rewritten)
            if overlap >= 0.60:
                return rewritten
    except Exception:
        pass
    return question
