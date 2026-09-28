# Agent vs Fixed Workflow Race

This artifact reports measurements only. Costs are estimated experiment costs at $0.001 per 1K tokens, not Ollama billing charges. p50 is the median of the ten per-question elapsed observations.

Dependent/branching cases: Q1, Q4, Q5

| Metric | Agent | Fixed Workflow | Questions |
|---|---:|---:|---:|
| Pass rate | 10/10 (100%) | 10/10 (100%) | 10 |
| p50 latency (seconds) | 135.883491 | 44.591256 | 10 |
| Total tokens | 44670 | 11801 | 10 |
| Estimated cost/question | $0.004467000 | $0.001180100 | 10 |

Agent budget terminations: 0

No winner or final verdict is declared in this step.
