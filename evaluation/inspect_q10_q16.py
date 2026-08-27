"""Temporary investigation script for Q10 and Q16 only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="chroma_db")
col = client.get_collection("hr_policy")

THRESHOLD = 1.0

questions = [
    (10, "How much advance notice is required to request a work from home day?"),
    (16, "What are the progressive steps in the company disciplinary process?"),
]

for qid, question in questions:
    print(f"\n{'='*60}")
    print(f"Question {qid}: {question}")
    print(f"{'='*60}")
    vec = model.encode(question).tolist()
    results = col.query(
        query_embeddings=[vec],
        n_results=3,
        include=["documents", "metadatas", "distances"]
    )
    docs  = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    print(f"DISTANCE_THRESHOLD = {THRESHOLD}   (strict: distance > threshold means DISCARD)")
    print()
    passed_to_llm = 0
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists), 1):
        passes = dist <= THRESHOLD
        label = "PASS (sent to LLM)" if passes else "FAIL (discarded by threshold filter)"
        if passes:
            passed_to_llm += 1
        src = meta["source"]
        chunk = meta["chunk_index"]
        print(f"Rank {i}:")
        print(f"  Source  : {src}")
        print(f"  Chunk   : {chunk}")
        print(f"  Distance: {dist:.4f}  -> {label}")
        print(f"  Content preview:")
        print(f"  {doc[:300].strip()}")
        print()
    print(f"Summary: {passed_to_llm}/3 chunks passed the threshold and were sent to LLM.")
    if passed_to_llm == 0:
        print("  -> context is EMPTY -> LLM returns fallback: 'I don't know...'")
