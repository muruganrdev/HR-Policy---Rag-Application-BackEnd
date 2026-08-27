import ollama
from app.rewrite import _token_overlap

# Model name – keep consistent with app.rag
EXPANSION_MODEL = "llama3"

def expand_query(query: str) -> str:
    """Expand a rewritten query with additional retrieval‑relevant terms.

    The function uses the local Ollama LLM to generate a concise list of
    keywords/concepts that improve semantic search while preserving the original
    intent. If the expansion fails or drops too many original tokens (overlap
    < 0.60), the original query is returned unchanged.
    """
    try:
        response = ollama.chat(
            model=EXPANSION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that expands a user's question with concise, "
                        "relevant keywords to improve document retrieval. Preserve the original "
                        "intent, do NOT answer the question, and do NOT invent facts. Return ONLY "
                        "the expanded query as a space‑separated list of terms."
                    ),
                },
                {"role": "user", "content": f"Expand this question for retrieval: {query}"},
            ],
            options={"temperature": 0.0},  # deterministic output
        )
        expanded = response.get("message", {}).get("content", "").strip()
        if expanded:
            # Ensure original terms are largely retained; otherwise fallback
            if _token_overlap(query, expanded) >= 0.60:
                return expanded
    except Exception:
        # Any error – fallback to original query
        pass
    return query
