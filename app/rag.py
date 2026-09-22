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


def _can_recover_empty_context(question: str, document: str) -> bool:
    """Allow a conservative lexical check for an otherwise empty context."""
    stop_words = {
        "a", "an", "and", "are", "can", "do", "does", "for", "from", "how",
        "i", "is", "of", "on", "the", "to", "what", "within", "with",
    }
    question_terms = {
        term for term in re.findall(r"[a-z0-9]+", question.lower())
        if term not in stop_words and len(term) > 2
    }
    document_terms = set(re.findall(r"[a-z0-9]+", document.lower()))
    return len(question_terms & document_terms) >= 2


def _append_chunk_continuation(document: str, metadata: dict) -> str:
    """Complete a retrieved chunk when fixed-size splitting ends mid-word."""
    if not document or not re.search(r"[A-Za-z0-9]$", document):
        return document

    source = metadata.get("source")
    chunk_index = metadata.get("chunk_index")
    if source is None or chunk_index is None:
        return document

    try:
        adjacent = collection.get(
            where={"source": source},
            include=["documents", "metadatas"],
        )
        for adjacent_document, adjacent_metadata in zip(
            adjacent["documents"], adjacent["metadatas"]
        ):
            if adjacent_metadata.get("chunk_index") != chunk_index + 1:
                continue
            continuation = adjacent_document.lstrip()
            if continuation and continuation[0].islower():
                return f"{document}{continuation}"
    except Exception:
        pass

    return document


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

        # Complete only fixed-size chunks that end mid-word.
        document = _append_chunk_continuation(document, metadata)

        # Build a clearly bounded policy block without changing the retrieved text.
        context_parts.append(
            f"""
    === POLICY SOURCE ===
    File: {source}
Chunk: {chunk_index}

    Policy Text:
{document}
    === END POLICY SOURCE ===
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
        # Keep the normal threshold behavior. Recover only the top reranked
        # candidate when it has strong lexical evidence for the question.
        if documents and _can_recover_empty_context(question, documents[0]):
            _document = documents[0]
            _metadata = metadatas[0]
            context = (
                f"\n=== POLICY SOURCE ===\n"
                f"File: {_metadata['source']}\n"
                f"Chunk: {_metadata['chunk_index']}\n\n"
                f"Policy Text:\n{_document}\n"
                f"=== END POLICY SOURCE ===\n"
            )
            relevant_sources.append({
                "source": _metadata["source"],
                "chunk": _metadata["chunk_index"],
            })
        else:
            return {
                "question": question,
                "answer": "I don't know based on the provided HR policy documents.",
                "sources": []
            }

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

Answer the original user question using ONLY the supplied policy context.
Before writing, identify every policy statement that directly governs the
question. Keep the answer concise, but completeness takes priority over
excessive summarization; use a short bullet list when multiple related rules
apply.

The context comes exclusively from official HR policy documents.

If the answer cannot be found in the context, say:
"I don't know based on the provided HR policy documents."

Do NOT make up or invent HR policies.
Do NOT use general knowledge to answer — only use what is in the context.
Preserve the complete policy rule when related conditions belong to the same
policy provision. Do not reduce a multi-part rule to only its headline number.
For entitlement questions, preserve directly associated eligibility, scope,
pro-rata or accrual rules, application and request procedures, approval
requirements, deadlines, limits, expiry or lapse conditions, and consequences
when the context states that they govern the entitlement or its use. If a
policy states a limit and what happens when it is reached or exceeded,
preserve both the limit and that resulting consequence. If a policy states
that an action must be completed by a deadline, preserve that deadline when it
governs the requested action. If a policy states an obligation and identifies
who must receive, report, or be disclosed to, preserve both the action and its
recipient or destination. Keep all related conditions from the same policy
rule together. For duration questions, stay focused on the requested duration
and directly associated conditions; do not include unrelated numeric rules.
For consequence or escalation questions, include the complete applicable
threshold, consequence, and escalation chain.
Do not include unrelated retrieved policy sections. Do not combine separate
policy limits into a new total unless the policy explicitly defines that
calculation. Do not perform unsupported calculations. Every factual statement
in the answer must be supported by the supplied policy context. Never combine
contradictory policy statements or manufacture a conclusion. If the requested
information is not present, use the existing grounded refusal sentence.
If the provided policy context does not contain the requested information,
clearly state that it is not covered by the provided HR policy documents and
do not invent an answer.

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
            ],
            options={"temperature": 0.0},
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

