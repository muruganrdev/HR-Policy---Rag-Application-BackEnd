# Langfuse Observability Integration

## Why Langfuse Was Added

Langfuse provides end-to-end observability for the HR Policy RAG pipeline.  
It allows every `/ask` request to be inspected as a structured trace in the Langfuse dashboard, including each pipeline stage: preprocessing → query rewrite → query expansion → embedding → vector retrieval → reranking → distance filtering → context assembly → LLM generation.

> **Langfuse integration is an observability enhancement. It does not implement the Week 6 fixes for the Week 5 issues.**

The existing Week 5 evaluation results, retrieval configuration, prompts, and answer outputs are **completely unchanged** by this integration.

---

## What Parts of the RAG Pipeline Are Traced

| Langfuse Span / Event        | What Is Captured                                                                  |
|------------------------------|-----------------------------------------------------------------------------------|
| `hr_rag_pipeline` (root)     | Entire `/ask` trace — input question, final answer                                |
| `preprocessing`              | Raw question → preprocessed question                                              |
| `query_rewrite`              | Preprocessed → rewritten query                                                    |
| `query_expansion`            | Rewritten → expanded query                                                        |
| `embedding`                  | Expanded query, embedding model name                                              |
| `vector_retrieval` (event)   | Query, N_RESULTS, candidate chunks with source / chunk_index / distance, latency |
| `reranking`                  | Number of candidates passed to CrossEncoder reranker                              |
| `distance_filtering` (event) | DISTANCE_THRESHOLD, chunks that passed, chunks filtered out with distances        |
| `llm_generation`             | Model name, number of context chunks, question, latency                           |

The `vector_retrieval` and `distance_filtering` events are especially useful for diagnosing Q15 (retrieval failure) and Q1/Q2/Q6 (answer completeness) without any code changes.

---

## How to Configure Langfuse

1. **Copy `.env.example` to `.env`**
   ```
   copy .env.example .env
   ```

2. **Fill in your Langfuse credentials** in `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-<your-public-key>
   LANGFUSE_SECRET_KEY=sk-lf-<your-secret-key>
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
   - Sign up / log in at [https://cloud.langfuse.com](https://cloud.langfuse.com) to get keys.
   - For self-hosted Langfuse, set `LANGFUSE_HOST` to your instance URL.

3. **Load `.env` before starting the server** (python-dotenv is already installed):
   ```powershell
   # Windows PowerShell
   $env:LANGFUSE_PUBLIC_KEY="pk-lf-..."
   $env:LANGFUSE_SECRET_KEY="sk-lf-..."
   $env:LANGFUSE_HOST="https://cloud.langfuse.com"
   uvicorn app.main:app --reload --port 8001
   ```
   Or add them to `.env` and they will be picked up automatically if you use `python-dotenv`.

> ⚠️ **Never commit `.env` to version control.** It is already listed in `.gitignore`.

---

## How to Run the Application

```powershell
# Without Langfuse (default — works normally)
uvicorn app.main:app --reload --port 8001

# With Langfuse enabled
$env:LANGFUSE_PUBLIC_KEY="pk-lf-..."
$env:LANGFUSE_SECRET_KEY="sk-lf-..."
$env:LANGFUSE_HOST="https://cloud.langfuse.com"
uvicorn app.main:app --reload --port 8001
```

---

## How to Inspect a Trace

1. Open [https://cloud.langfuse.com](https://cloud.langfuse.com) (or your self-hosted instance).
2. Navigate to **Traces**.
3. Each `/ask` call appears as a trace named `hr_rag_pipeline`.
4. Click a trace to see the nested spans and events for all pipeline stages.

---

## What Information Can Be Used for Debugging

### Q15 — Retrieval Failure (P1 High Priority)

In the trace for Q15, look at the **`distance_filtering`** event:

- `distance_threshold: 1.2`
- `candidates_before: 5`
- `filtered_out`: should show `employee_conduct_policy.pdf` (Chunk 4) with `distance ≈ 1.54`
- `chunks_passed: 0`

This proves that the relevant gift-disclosure chunk existed in ChromaDB but was filtered out because its distance exceeded the configured threshold.

### Q1 / Q2 / Q6 — Answer Completeness (P2 Medium Priority)

In traces for Q1, Q2, and Q6:

- `vector_retrieval` event will show the expected source was retrieved with a low distance score.
- `distance_filtering` event will show the chunk passed the threshold (`chunks_passed >= 1`).
- `llm_generation` span shows `n_context_chunks >= 1`.

This proves retrieval succeeded and the evidence was available to the generator, confirming the issue is in LLM synthesis rather than retrieval.

---

## Graceful Degradation

If Langfuse credentials are missing or the Langfuse server is unreachable:

- A warning is logged at startup.
- All RAG operations continue normally.
- The `/ask` endpoint returns the same answer as without Langfuse.
- No errors are surfaced to the API caller.

This is guaranteed by [`app/observability.py`](../app/observability.py) which wraps all Langfuse calls with try/except and provides a no-op fallback.

---

## Confirmation: Week 5 Behavior Not Changed

The following **were not modified** during Langfuse integration:

| Item | Status |
|------|--------|
| `DISTANCE_THRESHOLD` (1.2) | ✅ Unchanged |
| `N_RESULTS` (5) | ✅ Unchanged |
| Embedding model (`all-MiniLM-L6-v2`) | ✅ Unchanged |
| ChromaDB collection (`hr_policy`) | ✅ Unchanged |
| Reranker (CrossEncoder) | ✅ Unchanged |
| LLM model (`llama3`) | ✅ Unchanged |
| Generation prompt | ✅ Unchanged |
| `preprocess_question`, `rewrite_question`, `expand_query` | ✅ Unchanged |
| `docs/week5_analysis.md` | ✅ Unchanged |
| `docs/week5_trace.json` | ✅ Unchanged |
| Evaluation questions and expected answers | ✅ Unchanged |

The only files modified or created are:

| File | Change |
|------|--------|
| `app/observability.py` | **Created** — Langfuse initialisation + safe `observe()` wrapper |
| `app/rag.py` | **Modified** — Added `@observe` decorator + helper calls (no logic change) |
| `.env.example` | **Created** — Documents required environment variables |
| `docs/langfuse_observability.md` | **Created** — This documentation |
