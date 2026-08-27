"""
Week 4 Retrieval Inspection Tool for HR Policy RAG.

Inspects full text content, metadata, distances, and keyword presence across
the top-3 retrieved chunks for each benchmark question in evaluation_dataset.py.

Run from the project root:
    python evaluation/inspect_retrieval.py
"""

import os
import sys
import json
import chromadb
from sentence_transformers import SentenceTransformer

# Ensure the project root directory is in sys.path so modules can be imported cleanly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ------------------------------------------------------------
# 1. Load Evaluation Dataset
# ------------------------------------------------------------
try:
    from evaluation.evaluation_dataset import EVALUATION_DATASET
except ImportError as err:
    print(f"ERROR: Could not import EVALUATION_DATASET from evaluation.evaluation_dataset: {err}")
    sys.exit(1)


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "hr_policy"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 3
DISTANCE_LIMIT_WARN = 1.0


def main():
    print("=" * 60)
    print("WEEK 4 RETRIEVAL DEEP INSPECTION TOOL")
    print("=" * 60)

    if not EVALUATION_DATASET:
        print("ERROR: EVALUATION_DATASET is empty.")
        sys.exit(1)

    print(f"Loaded {len(EVALUATION_DATASET)} questions for inspection.\n")

    # ------------------------------------------------------------
    # 2. Load Embedding Model
    # ------------------------------------------------------------
    print(f"Loading embedding model ({EMBEDDING_MODEL_NAME})...")
    try:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("Embedding model loaded successfully.\n")
    except Exception as err:
        print(f"ERROR: Failed to load embedding model '{EMBEDDING_MODEL_NAME}': {err}")
        sys.exit(1)

    # ------------------------------------------------------------
    # 3. Connect to Persistent ChromaDB
    # ------------------------------------------------------------
    print(f"Connecting to persistent ChromaDB at: {CHROMA_PATH}")
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        print(f"Connected to collection '{COLLECTION_NAME}' (Total indexed chunks: {collection.count()})\n")
    except Exception as err:
        print(f"ERROR: Failed to connect to ChromaDB collection '{COLLECTION_NAME}': {err}")
        print("Please ensure 'python app/create_vector_db.py' was run successfully.")
        sys.exit(1)

    # Metrics and tracking lists
    total_questions = len(EVALUATION_DATASET)
    source_hits = 0
    source_misses = 0

    questions_with_high_distance = []
    questions_hit_but_no_keywords = []

    # ------------------------------------------------------------
    # 4. Iterate and Inspect Each Question
    # ------------------------------------------------------------
    for item in EVALUATION_DATASET:
        q_id = item["id"]
        question = item["question"]
        expected_source = item["expected_source"]
        expected_keywords = item.get("expected_keywords", [])

        # Generate query embedding
        query_embedding = embedding_model.encode(question).tolist()

        # Query top-3 chunks from ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"]
        )

        retrieved_docs = results["documents"][0] if results["documents"] else []
        retrieved_metas = results["metadatas"][0] if results["metadatas"] else []
        retrieved_dists = results["distances"][0] if results["distances"] else []

        retrieved_sources = [m.get("source", "unknown") for m in retrieved_metas]

        # Check Source HIT
        is_source_hit = expected_source in retrieved_sources
        if is_source_hit:
            source_hits += 1
            source_hit_str = "YES"
        else:
            source_misses += 1
            source_hit_str = "NO"

        # Check for chunks with distance > 1.0
        high_dist_chunks = []
        for meta, dist in zip(retrieved_metas, retrieved_dists):
            if dist > DISTANCE_LIMIT_WARN:
                high_dist_chunks.append({
                    "source": meta.get("source", "unknown"),
                    "chunk": meta.get("chunk_index", "N/A"),
                    "distance": round(dist, 4)
                })

        if high_dist_chunks:
            questions_with_high_distance.append({
                "id": q_id,
                "question": question,
                "chunks": high_dist_chunks
            })

        # Combine text across all 3 retrieved chunks for keyword presence check (case-insensitive)
        combined_text = " ".join(retrieved_docs).lower()
        keyword_results = {}
        any_keyword_matched = False

        for kw in expected_keywords:
            matched = kw.lower() in combined_text
            keyword_results[kw] = "YES" if matched else "NO"
            if matched:
                any_keyword_matched = True

        # Track cases where source was found, but none of the expected keywords were present
        if is_source_hit and expected_keywords and not any_keyword_matched:
            questions_hit_but_no_keywords.append({
                "id": q_id,
                "question": question,
                "expected_source": expected_source,
                "expected_keywords": expected_keywords
            })

        # ------------------------------------------------------------
        # Print Inspection Output for Current Question
        # ------------------------------------------------------------
        print("=" * 60)
        print(f"Question ID: {q_id}")
        print(f"Question: {question}")
        print(f"Expected Source: {expected_source}")
        print("=" * 60)

        for rank, (doc, meta, dist) in enumerate(zip(retrieved_docs, retrieved_metas, retrieved_dists), start=1):
            source = meta.get("source", "unknown")
            chunk_idx = meta.get("chunk_index", "N/A")
            print(f"\n--- Result {rank} ---")
            print(f"Source: {source}")
            print(f"Chunk: {chunk_idx}")
            print(f"Distance: {dist:.4f}\n")
            print("Content:")
            print(doc.strip())

        print("\n" + "-" * 60)
        print("Expected source:")
        print(expected_source)
        print("\nRetrieved sources:")
        print(json.dumps(retrieved_sources, indent=4))
        print(f"\nSource HIT: {source_hit_str}")

        if expected_keywords:
            print("\nKeyword Match:")
            for kw, res in keyword_results.items():
                print(f"- {kw}: {res}")

        print("-" * 60 + "\n")

    # ------------------------------------------------------------
    # 5. Overall Summary
    # ------------------------------------------------------------
    hit_rate = (source_hits / total_questions) * 100.0 if total_questions > 0 else 0.0

    print("=" * 60)
    print("RETRIEVAL INSPECTION SUMMARY")
    print("=" * 60)
    print(f"Total Questions        : {total_questions}")
    print(f"Source-level Hits      : {source_hits}")
    print(f"Source-level Misses    : {source_misses}")
    print(f"Source-level Hit-rate@3: {hit_rate:.2f}%\n")

    # High Distance Warning Section
    print("=" * 60)
    print(f"Questions with Retrieved Chunks Having Distance > {DISTANCE_LIMIT_WARN}:")
    print("=" * 60)
    if questions_with_high_distance:
        for q in questions_with_high_distance:
            print(f"- Question {q['id']}: \"{q['question']}\"")
            for c in q["chunks"]:
                print(f"    * {c['source']} (Chunk {c['chunk']}) -> Distance: {c['distance']}")
    else:
        print("None (all retrieved chunks have distance <= 1.0).")

    # Source Hit but No Keywords Matched Section
    print("\n" + "=" * 60)
    print("Questions Where Expected Source Was Found But NO Keywords Matched:")
    print("=" * 60)
    if questions_hit_but_no_keywords:
        for q in questions_hit_but_no_keywords:
            print(f"- Question {q['id']}: \"{q['question']}\"")
            print(f"    Expected Source  : {q['expected_source']}")
            print(f"    Expected Keywords: {q['expected_keywords']}")
    else:
        print("None (at least one expected keyword was found in all source-hit queries).")

    print("=" * 60)


if __name__ == "__main__":
    main()
