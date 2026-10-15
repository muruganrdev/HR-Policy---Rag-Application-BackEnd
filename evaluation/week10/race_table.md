# Week 10 — Single-Agent vs Multi-Agent Race Evaluation Report

- **Date / Time:** `2026-10-09T18:19:34.710887+00:00`
- **Dataset:** Official Task Set C (`TQ01` to `TQ10` from `evaluation/trajectory_dataset.py`)
- **Evaluation Methodology:** Deterministic substring oracle against `expected_answer_contains`
- **Percentile Convention:** Standard linear interpolation (`k = (p / 100) * (n - 1)`) on sorted 10-sample distribution
- **Cost Rate Configured:** `$0.001/1K model tokens` (Estimated Rate, not billed cloud infra)

## 1. Aggregate Comparison Table

| Metric | Single-Agent (Arm A) | Multi-Agent (Arm B) | Difference / Ratio |
| :--- | :---: | :---: | :---: |
| **Passed Cases** | 10 / 10 | 10 / 10 | +0 cases |
| **Pass Rate** | **100.0%** | **100.0%** | +0.0% |
| **p50 Latency** | 116.641 s | 0.020 s | -116.622 s |
| **p99 Latency (linear interp.)** | 169.819 s | 0.066 s | -169.754 s |
| **Total Model Tokens (LLM)** | 42,716 | 0 | -42,716 tokens |
| **Total Handoff Payload Tokens** | 0 *(in-process)* | 8,850 *(serialized)* | N/A *(distinct from LLM)* |
| **Avg. Estimated Cost / Question** | $0.004272 | $0.000000 | $-0.004272 |
| **Total Estimated Run Cost** | $0.042716 | $0.000000 | $-0.042716 |

## 2. Relative Model Token Usage Ratio (model_token_ratio) & Handoff Payload Analysis

- **Metric Name:** `Relative Model Token Usage Ratio` (`model_token_ratio`)
- **Formula:** `Multi-Agent Model Tokens / Single-Agent Model Tokens`
- **Numerator:** `Multi-Agent Total Model Tokens = 0`
- **Denominator:** `Single-Agent Total Model Tokens = 42,716`
- **Calculated Ratio:** **`0.0x`** (Multi-agent leveraged deterministic specialist contracts, requiring 0 LLM model tokens vs 42,716 for single-agent)
- **Metric Nature & Limitation Disclosure:** This metric represents the ratio of total LLM model tokens consumed between execution modes. It is **not** a direct measurement of repeated or duplicated context. Direct context duplication measurement is unavailable because Multi-Agent relies on deterministic specialist delegation with typed contracts rather than multi-turn LLM context re-sending.

### Handoff Payload Distribution & Largest Share Analysis

Across the 10 Task Set C cases (TQ01–TQ10), delegation occurred in 6 cases resulting in **9 total handoff delegations** and **8,850 total estimated handoff payload tokens**:

| Source Worker | Destination Worker | Task Type | Occurrences | Total Payload Tokens | Share of Total Payload |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `orchestrator` | `policy_specialist` | `policy_retrieval` | **6** | **6,867** tokens | **77.6%** (Largest) |
| `orchestrator` | `eligibility_specialist` | `eligibility_calculation` | **3** | **1,983** tokens | **22.4%** |
| **Total** | | | **9** | **8,850** tokens | **100.0%** |

#### Largest Handoff Contributor: `orchestrator` → `policy_specialist` (`policy_retrieval`)
- **Source:** `orchestrator`
- **Destination:** `policy_specialist`
- **Task Type:** `policy_retrieval`
- **Occurrences:** 6 (TQ05, TQ06, TQ07, TQ08, TQ09, TQ10)
- **Total Estimated Payload Tokens:** **6,867 tokens**
- **Share of Measured Handoff Total:** **77.6%** (6,867 ÷ 8,850 tokens)
- **Peak Single Instance:** Request 43 tokens, Response 1106 tokens, Combined **1149 tokens**
- **Why It Dominates:** Policy evidence chunks retrieved from ChromaDB (4 document chunks per lookup) are returned in full structured JSON format to ground the orchestrator's decision.
- **Metric Distinction Note:** Handoff payload tokens measure serialized inter-worker payload volume (`chars ÷ 4`) across application boundaries and are strictly tracked separately from LLM prompt/completion model tokens.

## 3. Per-Case Results Breakdown (TQ01–TQ10)

| Case ID | Single Pass | Multi Pass | Single Latency | Multi Latency | Single Tokens | Multi Tokens | Single Cost | Multi Cost | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `TQ01` | ✅ PASS | ✅ PASS | 170.15s | 0.00s | 5,032 | 0 | $0.005032 | $0.000000 | Both passed substring oracle |
| `TQ02` | ✅ PASS | ✅ PASS | 116.24s | 0.00s | 4,905 | 0 | $0.004905 | $0.000000 | Both passed substring oracle |
| `TQ03` | ✅ PASS | ✅ PASS | 108.93s | 0.00s | 4,873 | 0 | $0.004873 | $0.000000 | Both passed substring oracle |
| `TQ04` | ✅ PASS | ✅ PASS | 104.44s | 0.00s | 4,877 | 0 | $0.004877 | $0.000000 | Both passed substring oracle |
| `TQ05` | ✅ PASS | ✅ PASS | 117.04s | 0.07s | 2,504 | 0 | $0.002504 | $0.000000 | Both passed substring oracle |
| `TQ06` | ✅ PASS | ✅ PASS | 112.29s | 0.02s | 4,961 | 0 | $0.004961 | $0.000000 | Both passed substring oracle |
| `TQ07` | ✅ PASS | ✅ PASS | 122.35s | 0.02s | 5,054 | 0 | $0.005054 | $0.000000 | Both passed substring oracle |
| `TQ08` | ✅ PASS | ✅ PASS | 133.07s | 0.02s | 2,690 | 0 | $0.002690 | $0.000000 | Both passed substring oracle |
| `TQ09` | ✅ PASS | ✅ PASS | 166.49s | 0.02s | 2,851 | 0 | $0.002851 | $0.000000 | Both passed substring oracle |
| `TQ10` | ✅ PASS | ✅ PASS | 96.23s | 0.02s | 4,969 | 0 | $0.004969 | $0.000000 | Both passed substring oracle |

## 4. Evaluation Notes and Observations

1. **Execution Model:** Both arms evaluated against identical input queries, identical employee and database environments, and identical substring assertion criteria from `evaluation/trajectory_dataset.py`.
2. **Single-Agent Profile:** The single-agent baseline utilizes ReAct loop tool-selection. Token counts reflect dynamic tool observation frames and final answer synthesis.
3. **Multi-Agent Profile:** The multi-agent orchestrator delegates to specialized workers (Policy Retrieval and Eligibility Calculation). Specialists return typed results, reducing conversational loop overhead on calculation queries while isolating retrieval evidence.
4. **Payload vs Model Token Separation:** Serialized handoff request/response tokens transferred between the orchestrator and specialists are measured and tracked separately from LLM model tokens, ensuring no inflated token counts.
