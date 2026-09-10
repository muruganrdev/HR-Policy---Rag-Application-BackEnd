import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from evaluation.evaluation_dataset import EVALUATION_DATASET
import app.rag as rag
import app.reranker as reranker

# Storage for intercepted retrieval data
CURRENT_RETRIEVAL_DATA = {}

original_rerank_documents = reranker.rerank_documents

def intercepted_rerank_documents(query, documents, metadatas, distances):
    ordered_docs, ordered_meta, ordered_dist = original_rerank_documents(query, documents, metadatas, distances)
    
    # Calculate cross-encoder scores if available
    scores = []
    if reranker.CROSS_ENCODER_MODEL is not None and ordered_docs:
        try:
            pairs = [[query, doc] for doc in ordered_docs]
            scores = [float(s) for s in reranker.CROSS_ENCODER_MODEL.predict(pairs)]
        except Exception as e:
            scores = [None] * len(ordered_docs)
    else:
        scores = [None] * len(ordered_docs)

    CURRENT_RETRIEVAL_DATA["query"] = query
    CURRENT_RETRIEVAL_DATA["retrieved"] = []
    for rank, (doc, meta, dist, score) in enumerate(zip(ordered_docs, ordered_meta, ordered_dist, scores)):
        source = meta.get("source")
        chunk_idx = meta.get("chunk_index")
        chunk_id = f"{source}_chunk_{chunk_idx}" if source is not None and chunk_idx is not None else f"chunk_{rank+1}"
        CURRENT_RETRIEVAL_DATA["retrieved"].append({
            "chunk_id": chunk_id,
            "source": source,
            "page": None,  # ChromaDB metadata schema doesn't store page numbers
            "rank": rank + 1,
            "score": round(float(dist), 4),
            "rerank_score": round(score, 4) if score is not None else None,
            "retrieval_method": "dense_embedding_and_cross_encoder_rerank",
            "text": doc
        })
    return ordered_docs, ordered_meta, ordered_dist

# Patch both reranker and rag modules
reranker.rerank_documents = intercepted_rerank_documents
rag.rerank_documents = intercepted_rerank_documents

CATEGORIES = {
    1: "Leave Policy",
    2: "Leave Policy",
    3: "Leave Policy",
    4: "Leave Policy",
    5: "Attendance Policy",
    6: "Attendance Policy",
    7: "Attendance Policy",
    8: "Work From Home Policy",
    9: "Work From Home Policy",
    10: "Work From Home Policy",
    11: "Working Hours Policy",
    12: "Working Hours Policy",
    13: "Working Hours Policy",
    14: "Employee Conduct Policy",
    15: "Employee Conduct Policy",
    16: "Employee Conduct Policy",
    17: "Notice Period Policy",
    18: "Notice Period Policy",
    19: "Notice Period Policy",
    20: "Leave Policy - Sick Leave"
}

def main():
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    print("=" * 60)
    print("STARTING WEEK 5 STEP 5 TRACE EXECUTION RUNNER")
    print(f"Run ID: {run_id}")
    print(f"Total questions: {len(EVALUATION_DATASET)}")
    print("=" * 60)

    trace_records = []
    total = len(EVALUATION_DATASET)
    successful = 0
    failures = 0

    for idx, item in enumerate(EVALUATION_DATASET):
        q_id = item["id"]
        question = item["question"]
        expected_source = item["expected_source"]
        category = CATEGORIES.get(q_id, "General HR Policy")

        print(f"\n[{idx + 1}/{total}] Tracing Q{q_id}: {question}")
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        collected_at = datetime.now(timezone.utc).isoformat()
        CURRENT_RETRIEVAL_DATA.clear()

        start_time = time.time()
        status = "completed"
        http_status = 200
        rag_answer = ""
        citations_raw = []
        error_msg = None

        try:
            rag_output = rag.ask_question(question)
            rag_answer = rag_output.get("answer", "")
            citations_raw = rag_output.get("sources", [])
            successful += 1
        except Exception as e:
            status = "failed"
            http_status = 500
            error_msg = str(e)
            rag_answer = f"EXECUTION ERROR: {e}"
            failures += 1
            print(f"  FAILED with error: {e}")

        latency_ms = round((time.time() - start_time) * 1000, 2)
        print(f"  Latency: {latency_ms} ms | Status: {status}")

        formatted_citations = []
        for c in citations_raw:
            if isinstance(c, dict):
                src = c.get("source")
                chk = c.get("chunk")
                chunk_id = f"{src}_chunk_{chk}" if src is not None and chk is not None else None
                formatted_citations.append({
                    "source": src,
                    "page": None,
                    "chunk_id": chunk_id
                })

        retrieved_list = list(CURRENT_RETRIEVAL_DATA.get("retrieved", []))

        record = {
            "trace_id": trace_id,
            "run_id": run_id,
            "sequence": idx + 1,
            "collected_at": collected_at,
            "category": category,
            "question": question,
            "expected_source": expected_source,
            "expected_answerable": True,
            "endpoint": "/ask",
            "request_id": request_id,
            "request": {
                "question": question,
                "temperature": None
            },
            "temperature": None,
            "status": status,
            "http_status": http_status,
            "answer": rag_answer,
            "confidence": None,
            "citations": formatted_citations,
            "retrieved": retrieved_list,
            "latency_ms": latency_ms
        }
        if error_msg:
            record["error"] = error_msg

        trace_records.append(record)

        # Save progress after each question
        out_path = os.path.join(BASE_DIR, "docs", "week5_trace.json")
        with open(out_path, "w", encoding="utf-8") as f_out:
            json.dump(trace_records, f_out, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("WEEK 5 STEP 5 TRACE COMPLETED")
    print(f"Total questions traced: {len(trace_records)}")
    print(f"Successful executions: {successful}")
    print(f"Failed executions: {failures}")
    print(f"Trace file saved to: {out_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
