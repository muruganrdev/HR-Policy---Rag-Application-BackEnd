"""
Read-only Q16 retrieval investigation script for CHUNK_SIZE=600 vector database.

Inspects all chunks in employee_conduct_policy.pdf, checks keyword presence,
calculates query embedding distances, queries top-50 candidates, evaluates thresholds,
and determines exact failure category.

Run from project root:
    python evaluation/inspect_q16_topk.py
"""

import os
import sys
import chromadb
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "hr_policy"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
QUESTION_16 = "What are the progressive steps in the company disciplinary process?"

# Current application settings (read from codebase)
# rag.py & search.py currently have DISTANCE_THRESHOLD = 1.2, N_RESULTS = 5
CURRENT_THRESHOLD = 1.2
CURRENT_TOP_K = 5

KEYWORDS_TO_CHECK = [
    "progressive disciplinary process",
    "Step 1",
    "Verbal Warning",
    "Step 2",
    "Written Warning",
    "Step 3",
    "PIP",
    "Step 4",
    "Termination"
]


def main():
    print("=" * 70)
    print("READ-ONLY Q16 RETRIEVAL INVESTIGATION (CHUNK_SIZE=600 DB)")
    print("=" * 70)

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = client.get_collection(name=COLLECTION_NAME)

    total_db_chunks = col.count()
    print(f"Total chunks in collection '{COLLECTION_NAME}': {total_db_chunks}")

    # 1. Fetch all chunks for employee_conduct_policy.pdf
    conduct_records = col.get(
        where={"source": "employee_conduct_policy.pdf"},
        include=["documents", "metadatas", "embeddings"]
    )

    conduct_docs = conduct_records["documents"]
    conduct_metas = conduct_records["metadatas"]
    conduct_ids = conduct_records["ids"]
    conduct_embeds = conduct_records["embeddings"]

    print(f"Total chunks for 'employee_conduct_policy.pdf': {len(conduct_ids)}\n")

    # 2 & 3. Search stored chunks for disciplinary process terms
    target_chunks = []
    for idx, (doc, meta, embed) in enumerate(zip(conduct_docs, conduct_metas, conduct_embeds)):
        chunk_idx = meta["chunk_index"]

        has_step1 = "step 1" in doc.lower() or "verbal warning" in doc.lower()
        has_step2 = "step 2" in doc.lower() or "written warning" in doc.lower()
        has_step3 = "step 3" in doc.lower() or "pip" in doc.lower()
        has_step4 = "step 4" in doc.lower() or "termination" in doc.lower()
        has_prog  = "progressive disciplinary process" in doc.lower()

        if has_step1 or has_step2 or has_step3 or has_step4 or has_prog:
            target_chunks.append({
                "id": conduct_ids[idx],
                "chunk_index": chunk_idx,
                "text": doc,
                "embedding": embed,
                "has_step1": "step 1" in doc.lower() and "verbal warning" in doc.lower(),
                "has_step2": "step 2" in doc.lower() and "written warning" in doc.lower(),
                "has_step3": "step 3" in doc.lower() and "pip" in doc.lower(),
                "has_step4": "step 4" in doc.lower() and "termination" in doc.lower(),
                "has_prog": has_prog
            })

    # 4. Print FULL RAW CONTENT of target chunks
    print("=" * 70)
    print("FULL RAW CONTENT OF DISCIPLINARY PROCESS CHUNKS")
    print("=" * 70)
    for tc in target_chunks:
        print(f"\n--- Chunk Index: {tc['chunk_index']} (ID: {tc['id']}) ---")
        print(tc["text"])
        print("-" * 50)
        print("Keyword Presence:")
        print(f"  - Step 1 (Verbal Warning) : {'YES' if tc['has_step1'] else 'NO'}")
        print(f"  - Step 2 (Written Warning): {'YES' if tc['has_step2'] else 'NO'}")
        print(f"  - Step 3 (PIP)            : {'YES' if tc['has_step3'] else 'NO'}")
        print(f"  - Step 4 (Termination)    : {'YES' if tc['has_step4'] else 'NO'}")
        is_complete = tc['has_step1'] and tc['has_step2'] and tc['has_step3'] and tc['has_step4']
        print(f"  - Complete Process (All 4 Steps in One Chunk): {'YES' if is_complete else 'NO'}")

    # 5. Generate query embedding for Q16
    q_vec = model.encode(QUESTION_16).tolist()

    # 6 & 7. Query ChromaDB for Top-50 results
    top_50 = col.query(
        query_embeddings=[q_vec],
        n_results=min(50, total_db_chunks),
        include=["documents", "metadatas", "distances"]
    )

    top_docs = top_50["documents"][0]
    top_metas = top_50["metadatas"][0]
    top_dists = top_50["distances"][0]

    # 8. Print Top-50 Table
    print("\n" + "=" * 80)
    print("TOP-50 RETRIEVAL RESULTS FOR QUESTION 16")
    print("=" * 80)
    print(f"{'Rank':<5} | {'Chunk':<6} | {'Distance':<10} | {'Keywords Present':<32} | {'Source':<28}")
    print("-" * 88)

    for rank, (doc, meta, dist) in enumerate(zip(top_docs, top_metas, top_dists), start=1):
        found = []
        if "verbal warning" in doc.lower(): found.append("Verbal Warning")
        if "written warning" in doc.lower(): found.append("Written Warning")
        if "pip" in doc.lower(): found.append("PIP")
        if "termination" in doc.lower(): found.append("Termination")

        kw_str = ", ".join(found) if found else "None"
        c_idx = meta.get("chunk_index", "N/A")
        src = meta.get("source", "unknown")

        print(f"{rank:<5} | {c_idx:<6} | {dist:<10.4f} | {kw_str:<32} | {src:<28}")

    print("-" * 88)

    # 9, 10, 11, 12. Calculate distance, rank, Top-K presence, and threshold tests
    print("\n" + "=" * 70)
    print("DETAILED ANALYSIS FOR TARGET CHUNKS")
    print("=" * 70)

    # Find global ranks & distances for target chunks across full collection query
    full_query = col.query(
        query_embeddings=[q_vec],
        n_results=total_db_chunks,
        include=["metadatas", "distances"]
    )
    all_metas = full_query["metadatas"][0]
    all_dists = full_query["distances"][0]

    for tc in target_chunks:
        tc_idx = tc["chunk_index"]
        grank = None
        gdist = None
        for r, (m, d) in enumerate(zip(all_metas, all_dists), start=1):
            if m.get("source") == "employee_conduct_policy.pdf" and m.get("chunk_index") == tc_idx:
                grank = r
                gdist = d
                break

        print(f"\nTarget Chunk Index: {tc_idx}")
        print(f"  - Cosine Distance: {gdist:.4f}")
        print(f"  - Global Rank    : #{grank}")
        print(f"  - Top-K Presence :")
        print(f"      Top-K=3 : {'FOUND' if grank <= 3 else 'NOT FOUND'}")
        print(f"      Top-K=5 : {'FOUND' if grank <= 5 else 'NOT FOUND'}")
        print(f"      Top-K=10: {'FOUND' if grank <= 10 else 'NOT FOUND'}")
        print(f"      Top-K=20: {'FOUND' if grank <= 20 else 'NOT FOUND'}")
        print(f"      Top-K=30: {'FOUND' if grank <= 30 else 'NOT FOUND'}")
        print(f"      Top-K=50: {'FOUND' if grank <= 50 else 'NOT FOUND'}")
        print(f"  - Threshold Tests:")
        print(f"      Threshold 1.2: {'PASS' if gdist <= 1.2 else 'FAIL'}")
        print(f"      Threshold 1.3: {'PASS' if gdist <= 1.3 else 'FAIL'}")
        print(f"      Threshold 1.4: {'PASS' if gdist <= 1.4 else 'FAIL'}")
        print(f"      Threshold 1.5: {'PASS' if gdist <= 1.5 else 'FAIL'}")

if __name__ == "__main__":
    main()
