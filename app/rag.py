import re
import os
import time
import chromadb
import ollama
from sentence_transformers import SentenceTransformer
from app.reranker import rerank_documents
from app.preprocess import preprocess_question
from app.rewrite import rewrite_question
from app.query_expansion import expand_query
from app.observability import observe





# --------------------------------
# 1. Configuration & Casual Conversation
# --------------------------------

# Resolve paths relative to this script location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "hr_policy"

# Configurable distance threshold.
# Adjust this after testing with your actual HR documents.
DISTANCE_THRESHOLD = 1.2

N_RESULTS = 5

OLLAMA_MODEL = "llama3"


CASUAL_PATTERNS = {
    "greetings": {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening"
    },
    "general": {
        "how are you", "how are you doing", "what's up", "whats up"
    },
    "thanks": {
        "thanks", "thank you", "thanks a lot"
    },
    "farewell": {
        "bye", "goodbye", "see you", "see you later"
    }
}

CASUAL_RESPONSES = {
    "greetings": "Hello! 👋 How can I help you with our HR Policies?",
    "general": "I'm doing well! 😊 How can I help you with our HR Policies?",
    "thanks": "You're welcome! 😊 Feel free to ask any other HR policy questions.",
    "farewell": "Goodbye! 👋 Feel free to ask me anything about our HR Policies."
}


def get_casual_category(question: str) -> str | None:
    cleaned = re.sub(r"[^\w\s']", "", question.strip().lower()).strip()
    for category, patterns in CASUAL_PATTERNS.items():
        if cleaned in patterns:
            return category
    return None


def is_casual_message(question: str) -> bool:
    return get_casual_category(question) is not None


def get_casual_response(question: str) -> str:
    category = get_casual_category(question)
    if category and category in CASUAL_RESPONSES:
        return CASUAL_RESPONSES[category]
    return "Hello! 👋 How can I help you with our HR Policies?"


# --------------------------------
# 2. Load embedding model
# --------------------------------

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# --------------------------------
# 3. Connect to HR ChromaDB
# --------------------------------

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_collection(
    name=COLLECTION_NAME
)


# --------------------------------
# 4. Observability helpers (no-op safe)
# --------------------------------

import contextlib
import logging

_obs_logger = logging.getLogger(__name__)

@contextlib.contextmanager
def _observe_span(name: str, input=None):
    """
    Context manager that wraps a pipeline stage in a Langfuse span.
    Silently no-ops if Langfuse is disabled or throws any error.
    The wrapped code always runs regardless of Langfuse availability.
    """
    from app.observability import is_enabled
    if is_enabled():
        try:
            from langfuse import Langfuse
            _client = Langfuse()
            span = _client.start_observation(name=name, type="span", input=input)
            try:
                yield
            except Exception:
                raise
            finally:
                try:
                    _client.update_current_span(end=True)
                except Exception:
                    pass
        except Exception as _e:
            _obs_logger.debug("Langfuse span '%s' failed (non-fatal): %s", name, _e)
            yield
    else:
        yield


def _observe_retrieval_event(*, query, n_results, candidates, distance_threshold, latency_ms):
    """Logs a structured retrieval metadata event to Langfuse (non-fatal)."""
    from app.observability import is_enabled
    if not is_enabled():
        return
    try:
        from langfuse import Langfuse
        _client = Langfuse()
        _client.create_event(
            name="vector_retrieval",
            input={"query": query, "n_results": n_results,
                   "distance_threshold": distance_threshold},
            output={
                "candidates": candidates,
                "n_candidates_retrieved": len(candidates),
                "latency_ms": latency_ms,
            },
        )
    except Exception as _e:
        _obs_logger.debug("Langfuse retrieval event failed (non-fatal): %s", _e)


def _observe_filtering_event(*, distance_threshold, candidates_before, passed, filtered_out):
    """Logs a structured distance-filtering event to Langfuse (non-fatal)."""
    from app.observability import is_enabled
    if not is_enabled():
        return
    try:
        from langfuse import Langfuse
        _client = Langfuse()
        _client.create_event(
            name="distance_filtering",
            input={"distance_threshold": distance_threshold,
                   "candidates_before": candidates_before},
            output={
                "passed": passed,
                "filtered_out": filtered_out,
                "chunks_passed": len(passed),
                "chunks_filtered_out": len(filtered_out),
            },
        )
    except Exception as _e:
        _obs_logger.debug("Langfuse filtering event failed (non-fatal): %s", _e)


# --------------------------------
# 5. RAG Function
# --------------------------------

@observe(name="hr_rag_pipeline")
def ask_question(question: str):
    """
    Full HR Policy RAG pipeline:
      1. Check for casual conversation
      2. Embed the question
      3. Retrieve relevant HR policy chunks from ChromaDB
      4. Filter by distance threshold
      5. Build grounded context
      6. Send grounded prompt to Llama 3 via Ollama
      7. Return answer + source citations

    Args:
        question: The user's natural language question.

    Returns:
        A dict with keys: question, answer, sources.
    """

    # --------------------------------
    # Casual conversation check
    # --------------------------------

    if is_casual_message(question):
        return {
            "question": question,
            "answer": get_casual_response(question),
            "sources": []
        }


    # --------------------------------
    # Convert question into embedding vector
    # --------------------------------

    # ── Preprocessing ────────────────────────────────────────────────────────
    with _observe_span("preprocessing", input={"raw_question": question}):
        processed_question = preprocess_question(question)

    # ── Query rewrite ────────────────────────────────────────────────────────
    with _observe_span("query_rewrite", input={"preprocessed": processed_question}):
        rewritten_question = rewrite_question(processed_question)

    # ── Query expansion ──────────────────────────────────────────────────────
    with _observe_span("query_expansion", input={"rewritten": rewritten_question}):
        expanded_query = expand_query(rewritten_question)

    print(f"Original question: {question}")
    print(f"Preprocessed question: {processed_question}")
    print(f"Rewritten question: {rewritten_question}")
    print(f"Expanded query: {expanded_query}")

    # ── Embedding ────────────────────────────────────────────────────────────
    with _observe_span("embedding", input={"query": expanded_query,
                                           "model": "all-MiniLM-L6-v2"}):
        query_embedding = embedding_model.encode(expanded_query).tolist()


    # --------------------------------
    # Retrieve top-N candidate chunks
    # --------------------------------

    # ── Vector retrieval ─────────────────────────────────────────────────────
    _t_retr = time.time()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=N_RESULTS,
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )
    _retr_latency = round((time.time() - _t_retr) * 1000, 2)

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    _candidates = [
        {
            "rank": i + 1,
            "source": m.get("source"),
            "chunk_index": m.get("chunk_index"),
            "distance": round(d, 4),
        }
        for i, (m, d) in enumerate(zip(metadatas, distances))
    ]
    _observe_retrieval_event(
        query=expanded_query,
        n_results=N_RESULTS,
        candidates=_candidates,
        distance_threshold=DISTANCE_THRESHOLD,
        latency_ms=_retr_latency,
    )

    # ── Reranking ────────────────────────────────────────────────────────────
    with _observe_span("reranking", input={"n_candidates": len(documents)}):
        # Rerank retrieved documents using CrossEncoder
        documents, metadatas, distances = rerank_documents(
            expanded_query, documents, metadatas, distances
        )


    # --------------------------------
    # Filter chunks by distance threshold
    # --------------------------------

    context_parts = []
    relevant_sources = []
    _filtered_in = []
    _filtered_out = []

    for _rank, (document, metadata, distance) in enumerate(
        zip(documents, metadatas, distances), start=1
    ):
        _src = metadata["source"]
        _chk = metadata["chunk_index"]

        # Discard irrelevant chunks beyond threshold
        if distance > DISTANCE_THRESHOLD:
            _filtered_out.append({"rank": _rank, "source": _src,
                                   "chunk_index": _chk, "distance": round(distance, 4)})
            continue

        _filtered_in.append({"rank": _rank, "source": _src,
                              "chunk_index": _chk, "distance": round(distance, 4)})

        source = _src
        chunk_index = _chk

        # Build context block with citation
        context_parts.append(
            f"""
Source: {source}
Chunk: {chunk_index}

Content:
{document}
"""
        )

        # Store citation for the response
        relevant_sources.append({
            "source": source,
            "chunk": chunk_index
        })

    # ── Distance filtering observation event ─────────────────────────────────
    _observe_filtering_event(
        distance_threshold=DISTANCE_THRESHOLD,
        candidates_before=len(documents),
        passed=_filtered_in,
        filtered_out=_filtered_out,
    )


    # --------------------------------
    # Build final context string
    # --------------------------------

    context = "\n\n".join(context_parts)


    # --------------------------------
    # No relevant HR documents found
    # --------------------------------

    if not context:
        return {
            "question": question,
            "answer": "I don't know based on the provided HR policy documents.",
            "sources": []
        }


    # --------------------------------
    # Grounded prompt — HR Policy domain
    # --------------------------------

    prompt = f"""
You are a helpful HR Policy assistant.

Answer the user's question using ONLY the information
provided in the context below.

The context comes exclusively from official HR policy documents.

If the answer cannot be found in the context, say:
"I don't know based on the provided HR policy documents."

Do NOT make up or invent HR policies.
Do NOT use general knowledge to answer — only use what is in the context.

Context:
{context}

User Question:
{question}

Answer:
"""


    # --------------------------------
    # Send grounded prompt to Llama 3
    # --------------------------------

    # ── LLM generation ──────────────────────────────────────────────────────
    _t_llm = time.time()
    with _observe_span("llm_generation", input={
        "model": OLLAMA_MODEL,
        "n_context_chunks": len(context_parts),
        "question": question,
    }):
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
    _llm_latency = round((time.time() - _t_llm) * 1000, 2)


    # --------------------------------
    # Extract answer text
    # --------------------------------

    answer = response["message"]["content"]


    # --------------------------------
    # Return API-friendly response
    # --------------------------------

    return {
        "question": question,
        "answer": answer,
        "sources": relevant_sources
    }

