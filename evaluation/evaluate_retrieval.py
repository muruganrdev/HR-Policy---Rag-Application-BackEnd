"""
Week 4 Baseline Retrieval Evaluation Script.

Evaluates retrieval quality (Hit-rate@3) of the HR Policy RAG system against
the benchmark dataset using ChromaDB and all-MiniLM-L6-v2 embeddings.

Run from the project root:
    python evaluation/evaluate_retrieval.py
"""

import os
import sys
import chromadb
from sentence_transformers import SentenceTransformer

# Ensure the project root directory is in sys.path so modules can be imported cleanly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ------------------------------------------------------------
# 1. Loading the evaluation dataset
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


def main():
    print("=" * 60)
    print("WEEK 4 BASELINE RETRIEVAL EVALUATION (Hit-rate@3)")
    print("=" * 60)

    # Validate evaluation dataset
    if not EVALUATION_DATASET:
        print("ERROR: EVALUATION_DATASET is empty. Please add evaluation questions and re-run.")
        sys.exit(1)

    print(f"Loaded {len(EVALUATION_DATASET)} test questions from evaluation_dataset.py\n")

    # ------------------------------------------------------------
    # 2. Loading the embedding model
    # ------------------------------------------------------------
    print(f"Loading embedding model ({EMBEDDING_MODEL_NAME})...")
    try:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("Embedding model loaded successfully.\n")
    except Exception as err:
        print(f"ERROR: Failed to load embedding model '{EMBEDDING_MODEL_NAME}': {err}")
        sys.exit(1)

    # ------------------------------------------------------------
    # 3. Connecting to ChromaDB
    # ------------------------------------------------------------
    print(f"Connecting to persistent ChromaDB at: {CHROMA_PATH}")
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
    except Exception as err:
        print(f"ERROR: Failed to connect to ChromaDB at '{CHROMA_PATH}': {err}")
        sys.exit(1)

    try:
        collection = client.get_collection(name=COLLECTION_NAME)
        total_chunks = collection.count()
        print(f"Connected to collection '{COLLECTION_NAME}' (Total indexed chunks: {total_chunks})\n")
    except Exception as err:
        print(f"ERROR: Collection '{COLLECTION_NAME}' not found in ChromaDB.")
        print("Please run 'python app/create_vector_db.py' first to build the vector store.")
        print(f"Details: {err}")
        sys.exit(1)

    # Tracking metrics
    total_queries = len(EVALUATION_DATASET)
    hits = 0
    misses = 0
    table_rows = []

    print("=" * 60)
    print("RUNNING RETRIEVAL EVALUATION")
    print("=" * 60)

    # ------------------------------------------------------------
    # Iterating over each test query
    # ------------------------------------------------------------
    for item in EVALUATION_DATASET:
        q_id = item["id"]
        question = item["question"]
        expected_source = item["expected_source"]

        # ------------------------------------------------------------
        # 4. Creating the query embedding
        # ------------------------------------------------------------
        query_embedding = embedding_model.encode(question).tolist()

        # ------------------------------------------------------------
        # 5. Top-3 retrieval from ChromaDB
        # ------------------------------------------------------------
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"]
        )

        retrieved_metadatas = results["metadatas"][0] if results["metadatas"] else []
        retrieved_distances = results["distances"][0] if results["distances"] else []

        retrieved_sources = [m.get("source", "unknown") for m in retrieved_metadatas]

        # ------------------------------------------------------------
        # 6. Hit-rate@3 calculation check
        # A query is a HIT if expected_source appears in any of top-3 results
        # ------------------------------------------------------------
        is_hit = expected_source in retrieved_sources
        if is_hit:
            hits += 1
            result_label = "HIT"
        else:
            misses += 1
            result_label = "MISS"

        # Record for compact summary table
        table_rows.append({
            "id": q_id,
            "expected": expected_source,
            "retrieved": ", ".join(retrieved_sources),
            "result": result_label
        })

        # Print detailed inspection per question
        print("-" * 60)
        print(f"Question {q_id}")
        print(f"Question: {question}")
        print(f"Expected Source: {expected_source}\n")
        print("Top 3 Retrieved Results:")

        for rank, (meta, dist) in enumerate(zip(retrieved_metadatas, retrieved_distances), start=1):
            source = meta.get("source", "unknown")
            chunk_idx = meta.get("chunk_index", "N/A")
            print(f"{rank}. Source: {source}")
            print(f"   Chunk: {chunk_idx}")
            print(f"   Distance: {dist:.4f}\n")

        print(f"Result: {result_label}")
        print("-" * 60)

    # ------------------------------------------------------------
    # Compact Results Table
    # ------------------------------------------------------------
    print("\n" + "=" * 90)
    print(f"{'ID':<4} | {'Expected Source':<28} | {'Retrieved Sources':<42} | {'Result':<6}")
    print("-" * 90)
    for row in table_rows:
        print(f"{row['id']:<4} | {row['expected']:<28} | {row['retrieved']:<42} | {row['result']:<6}")
    print("=" * 90)

    # ------------------------------------------------------------
    # Overall Summary & Hit-rate@3 Calculation
    # ------------------------------------------------------------
    hit_rate = (hits / total_queries) * 100.0 if total_queries > 0 else 0.0

    print("\n" + "=" * 60)
    print("WEEK 4 RETRIEVAL EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Questions : {total_queries}")
    print(f"Hits            : {hits}")
    print(f"Misses          : {misses}")
    print(f"Hit-rate@3      : {hit_rate:.2f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
