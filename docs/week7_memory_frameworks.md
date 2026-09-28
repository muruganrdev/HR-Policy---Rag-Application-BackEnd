# Week 7 memory and framework implementation notes

This document distinguishes the isolated Week 7 learning implementations from the production HR agent and retrieval pipeline.

## 1. Short-term memory

The earlier rolling-deque prototype and its test were removed during repository cleanup because no current application or Week 7 implementation depends on them. The final project does not include a standalone short-term-memory module.

## 2. Long-term memory

The long-term memory layer stores user/session-scoped memories on disk with SQLite so they survive restarts.

- Purpose: persistent memory across application restarts.
- Implementation: SQLite-backed store with user_id and session_id filtering.
- Data model: memory_id, user_id, session_id, memory_text, created_at, updated_at, metadata_json.
- Status: implemented and persisted to the local project data directory.

## 3. Summarisation

Conversation summarisation uses Ollama and llama3 to compress recent context into a concise memory summary.

```
Conversation
→ Ollama llama3
→ compact summary
→ memory store
```

- Purpose: turn verbose chat transcripts into a small factual summary.
- Implementation: the dedicated summarisation wrapper calls Ollama with model="llama3".
- Scope: isolated memory experiment; production agent logic is unchanged.

## 4. Vector memory

Vector memory uses ChromaDB and SentenceTransformer embeddings to store and retrieve semantically related facts.

```
Memory text
→ all-MiniLM-L6-v2 embedding
→ ChromaDB persistent collection
→ similarity search
```

- Implementation: real ChromaDB `PersistentClient` usage with `SentenceTransformer` embeddings.
- Storage: isolated memory collection under the project data area rather than the production HR policy collection.
- Retrieval: similarity-based search using query embedding plus metadata filters.
- Important note: on Windows, the Chroma temporary directory can retain file locks until the underlying client is explicitly closed. The fix is a lifecycle cleanup at the test boundary, not a change to the production employee or policy stores.

## 5. Mem0

Mem0 uses the real `mem0ai` distribution (`mem0` import package), verified at version 2.2.0, through `mem0.Memory.add(...)` and `mem0.Memory.search(...)`.

- `add` sends a user message to the actual Mem0 API and supplies `user_id`, `run_id` (the wrapper's `session_id`), and metadata.
- `search` calls the actual Mem0 API with filters for both `user_id` and `run_id`, keeping users and sessions isolated.
- The default wrapper configuration uses persistent local Qdrant storage and a local history SQLite database, but uses OpenAI for both LLM inference and embeddings. That default therefore requires `OPENAI_API_KEY` and access to the OpenAI API.
- `MEM0_API_KEY` is not an OpenAI credential and is not accepted as a substitute. This implementation does not call the hosted Mem0 service and does not require a Mem0 service account when local providers are configured.
- Real add, semantic-search, user/session-isolation, multi-memory, and reopen/persistence tests use Mem0's local Qdrant provider and the already cached local `all-MiniLM-L6-v2` SentenceTransformer. Test adds use Mem0's `infer=False` API option so they store the supplied memories without invoking an LLM inference step; the configured LLM provider is local Ollama `llama3`. The tests disable Mem0's optional telemetry to avoid its separate user-profile migration store and telemetry calls. Embedding and vector-search operations still use the real Mem0 package.
- Local Qdrant handles are explicitly closed in tests so Windows releases its on-disk storage lock before reopening or cleaning the temporary directory.
- No `requirements.txt` exists in the project workspace; the active project virtual environment contains `mem0ai==2.2.0`.

**Status: VERIFIED LOCALLY.** The current environment has no `OPENAI_API_KEY` or `MEM0_API_KEY`; the default OpenAI-backed configuration cannot be exercised here. Local-provider Mem0 operations and persistence are verified without external Mem0/OpenAI service credentials.

This is intentionally isolated from the production HR agent and policy system.

## 6. LangGraph

LangGraph was selected as the required Week 7 framework implementation.

```
StateGraph
→ agent node
→ conditional routing
→ tool node
→ END
```

- Implementation: real `StateGraph` from `langgraph.graph`.
- Usage: graph nodes are defined with actual edges and conditional routing.
- Demonstration: employee lookup flows through an agent node and tool node, then terminates when enough information is available.
- Scope: isolated learning demo only; it does not replace the production agent.

## 7. LangChain

LangChain was not implemented.

Week 7 required either LangChain or LangGraph, and LangGraph was selected. The project keeps the Week 7 framework work isolated and does not modify the production agent or policy flow.

## 8. Final status summary

| Topic | Status | Evidence |
| --- | --- | --- |
| Short-term memory | NOT INCLUDED | Unused prototype removed during repository cleanup |
| Long-term memory | IMPLEMENTED | SQLite persistence with user/session scoping |
| Ollama summarisation | IMPLEMENTED | llama3 summary wrapper calling Ollama |
| ChromaDB vector memory | IMPLEMENTED | Real `PersistClient` + transformer embeddings + similarity retrieval |
| Mem0 | VERIFIED LOCALLY | Real `mem0ai==2.2.0` add/search APIs, user/run filters, local Qdrant persistence, and re-opened retrieval tested with local providers |
| LangGraph | IMPLEMENTED | Actual `StateGraph` nodes, edges, conditional routing |

> Implementation exists is different from live runtime verified. The code is implemented when the modules and APIs are present; runtime verification requires the required service/configuration and a successful execution in the current environment.
