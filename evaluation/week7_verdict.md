# Week 7 Final Verdict: Agent vs Fixed Workflow

## Verdict

In the 10-question Week 7 experiment, the tool path **did not vary by input**. Across all 10 questions (Q1–Q10), the Agent selected the exact same fixed sequence of three tools: `get_employee_record` → `lookup_annual_leave_policy` → `calculate_annual_leave_disposition`. No question in the benchmark required skipping a tool, repeating a tool, or choosing an alternative tool. 

No question class requiring dynamic Agent routing was demonstrated. The Fixed Workflow executed the identical 3-tool sequence for every input and achieved a 10/10 (100%) pass rate with a p50 latency of 38.88 seconds, whereas the Agent achieved 0/10 due to 10/10 wall-clock budget terminations (p50 latency 143.22 seconds). 

Because all 10 inputs follow a single static sequence, a fixed workflow is sufficient for this task set, though agents remain valuable for benchmarks with true input-dependent tool path variability.

## Empirical Evidence

| Metric | Agent | Fixed Workflow |
| :--- | :---: | :---: |
| **Pass Rate** | 0/10 (0%) | **10/10 (100%)** |
| **Tool Path Variability** | Static (identical 3 tools for Q1–Q10) | Static (identical 3 tools for Q1–Q10) |
| **p50 Latency** | 143.22 s | **38.88 s** |
| **Total Tokens** | 32,863 | **11,249** |
| **Estimated Cost / Question** | $0.0032863 | **$0.0011249** |
| **Budget Terminations** | 10 (100% `wall_clock`) | **0** |
