from sentence_transformers import CrossEncoder
from typing import List, Tuple
import logging

# Load model once at import time; fallback to None on failure
try:
    CROSS_ENCODER_MODEL = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
except Exception as e:
    logging.warning(f"Failed to load CrossEncoder model: {e}")
    CROSS_ENCODER_MODEL = None

def rerank_documents(
    query: str,
    documents: List[str],
    metadatas: List[dict],
    distances: List[float],
) -> Tuple[List[str], List[dict], List[float]]:
    """Rerank retrieved documents using a CrossEncoder relevance model.

    Args:
        query: The query string used for the initial retrieval (post‑expansion).
        documents: List of retrieved document chunks (strings).
        metadatas: Corresponding metadata dictionaries for each chunk.
        distances: Original ChromaDB distance scores (kept for later filtering).

    Returns:
        Reordered (documents, metadatas, distances) tuples sorted by descending
        CrossEncoder relevance score. If the model cannot be used, the original
        ordering is returned unchanged.
    """
    if CROSS_ENCODER_MODEL is None or not documents:
        # No model or no docs: log and return unchanged
        logging.info("Reranker skipped: model not loaded or no documents.")
        return documents, metadatas, distances
        return documents, metadatas, distances

    try:
        # Log query and number of candidates
        logging.info(f"Reranking query: {query}")
        logging.info(f"Candidate count: {len(documents)}")
        # Log BEFORE info: source/chunk identifier and original distance
        for idx, meta in enumerate(metadatas):
            source = meta.get('source', 'unknown')
            chunk_id = meta.get('chunk_id', idx)
            logging.info(f"BEFORE rerank - idx:{idx} source:{source} chunk_id:{chunk_id} distance:{distances[idx]:.4f}")
        # Build (query, doc) pairs for scoring
        pairs = [[query, doc] for doc in documents]
        scores = CROSS_ENCODER_MODEL.predict(pairs)
        # Log CrossEncoder scores
        for idx, score in enumerate(scores):
            logging.info(f"CrossEncoder score idx:{idx} score:{score:.4f}")
        # Pair each score with its original index
        indexed = list(enumerate(scores))
        # Sort by score descending
        indexed.sort(key=lambda x: x[1], reverse=True)
        # Reorder all lists according to sorted indices
        ordered_docs = [documents[i] for i, _ in indexed]
        ordered_meta = [metadatas[i] for i, _ in indexed]
        ordered_dist = [distances[i] for i, _ in indexed]
        # Log AFTER info: source/chunk and reranker score
        for rank, (idx, score) in enumerate(indexed):
            meta = metadatas[idx]
            source = meta.get('source', 'unknown')
            chunk_id = meta.get('chunk_id', idx)
            logging.info(f"AFTER rerank - rank:{rank} source:{source} chunk_id:{chunk_id} rerank_score:{score:.4f}")
        return ordered_docs, ordered_meta, ordered_dist
    except Exception as e:
        logging.warning(f"Reranking failed: {e}")
        return documents, metadatas, distances
