# Agent Failure Modes and Trajectory Evaluation

## Evaluation basis

The before and after measurements use the same final 10-case dataset in `evaluation/trajectory_dataset.py`. The before run executed the committed `HEAD:app/agent.py` without changing the working tree; the final after run used the completion-state fix plus production security integration and the required `python -m evaluation.trajectory_evaluator` command. Costs are the Agent's recorded token-based estimates. No Week 7 race was run.

The evaluator's answer oracle requires every `expected_answer_contains` phrase. Trajectory correctness requires an exact match to one accepted ordered sequence. Tool-choice accuracy is positional matches divided by the larger of actual and expected path length, using the best-scoring accepted path. Duplicate attempts parsed from the returned trace remain in the actual sequence. Step efficiency is `steps_taken / steps_needed`; alternate paths use the accepted path selected by the same best-match comparison. Argument validity counts each tool attempt and requires both syntactic validity and grounding in the live employee database or prior successful observations.

## Final benchmark

| Measure | Before mitigation | After mitigation |
|---|---:|---:|
| Cases | 10 | 10 |
| Outcome pass rate | 5/10 (50%) | 8/10 (80%) |
| Trajectory pass rate | 7/10 (70%) | 10/10 (100%) |
| Outcome minus trajectory gap | -20 percentage points | -20 percentage points |
| Tool-choice accuracy | 17/37 (45.95%) | 17/17 (100%) |
| Argument validity | 37/37 (100%) | 17/17 (100%) |
| Syntactically valid arguments | 37/37 | 17/17 |
| Grounded valid arguments | 37/37 | 17/17 |
| Mean step efficiency | 3.00 | 1.00 |
| Cost p50 | $0.004642 | $0.001798 |
| Cost max | $0.015741 | $0.005351 |
| Average latency | 144.273 s | 109.654 s |
| P50 latency | 147.907 s | 84.292 s |
| Mean cost per task | $0.006312 | $0.002832 |
| Total tokens | 63,119 | 28,318 |
| Termination reasons | none: 7; max_iterations: 2; wall_clock: 1 | none: 10 |

## Outcome-vs-Trajectory Evidence

### Primary benchmark

Outcome pass rate: 80% (8/10)  
Trajectory pass rate: 100% (10/10)  
Gap: -20 percentage points

No live right-answer/wrong-trajectory case was observed in the primary
benchmark. TQ03 and TQ04 had correct trajectories but failed the answer oracle;
they do not qualify.

### Live diagnostic run

An additional eight-question diagnostic run called the real production
`run_agent()` and remained separate from the scored 10-case benchmark. It
covered six employee-only questions, one employee-policy comparison, and one
employee-specific policy-limit question.

| Diagnostic IDs | Result |
|---|---|
| D01-D06 | Correct employee answer, one `get_employee_data` call, expected path |
| D07 | Correct comparison answer, `get_employee_data -> lookup_annual_leave_policy`, expected path |
| D08 | Answer evaluation failed after `get_employee_data`; not an outcome pass |

The diagnostic produced no case with both `answer_correct=true` and
`trajectory_correct=false`. No live right-answer/wrong-trajectory case was
observed after reviewing the primary benchmark and expanded diagnostic set.

### Evaluator-only regression

The controlled unit fixture in `tests/test_trajectory_evaluator.py` passes: the
evaluator recognizes a correct answer with a wrong trajectory. This verifies
scoring only and is not live Agent evidence.

## Selected mitigation

The one scored mitigation is the existing `TOOL_LOOP / completion-state mismatch` fix in `app/agent.py`. It aligns sufficient-observation checks with missing-information decisions, stops after sufficient employee-only or policy-only observations, directs missing-information questions to the missing tool, and completes full disposition questions after calculation. The completion tests also confirm no extra final-model call after supported structured observations. No model, budget, database, ChromaDB, Week 6 data, Week 7 race, protected RAG constant, or public API contract was changed for this mitigation.

| Top failure mode | Before | After |
|---|---:|---:|
| TOOL_LOOP | 3/10 | 0/10 |

The three baseline loop cases were TQ02 (8 employee-data attempts; `MAX_ITERATIONS`), TQ05 (7 policy-lookup attempts; `WALL_CLOCK`), and TQ06 (8 policy-lookup attempts; `MAX_ITERATIONS`). After the fix, each required tool path ran once and none of the ten cases terminated by budget.

### Mitigation impact

Measured after-minus-before per question:

| Resource | Before | After | Delta |
|---|---:|---:|---:|
| Latency change | 144.273 s | 109.654 s | -34.619 s/question |
| Token change | 6,311.9 | 2,831.8 | -3,480.1 tokens/question |
| Cost change | $0.006312 | $0.002832 | -$0.003480/question |

The negative values indicate reductions compared with the pre-mitigation baseline. No additional resource cost was observed in this benchmark. These values compare the preserved pre-mitigation run with the final post-mitigation, security-integrated run; model latency is nondeterministic, and both runs use the same configured model and dataset.

## Failure-mode regression table

Counts use the evaluator's existing primary modes plus secondary budget-termination modes. A case's primary failure and secondary termination can both be counted.

| Mode | Before | After |
|---|---:|---:|
| TOOL_LOOP | 3 | 0 |
| WRONG_TOOL | 0 | 0 |
| WRONG_ARGUMENT | 0 | 0 |
| WRONG_ORDER | 0 | 0 |
| MISSING_TOOL | 0 | 0 |
| PREMATURE_FINAL | 0 | 0 |
| FINAL_ANSWER_ERROR | 2 | 2 |
| TOOL_ERROR | 0 | 0 |
| MAX_ITERATIONS | 2 | 0 |
| WALL_CLOCK | 1 | 0 |
| MAX_TOKENS | 0 | 0 |
| MAX_COST | 0 | 0 |

Modes that worsened: none.

New modes created: none.

Modes checked with no regression: WRONG_TOOL, WRONG_ARGUMENT, WRONG_ORDER, MISSING_TOOL, PREMATURE_FINAL, FINAL_ANSWER_ERROR, TOOL_ERROR, MAX_TOKENS, MAX_COST. TOOL_LOOP, MAX_ITERATIONS, and WALL_CLOCK improved.

## Security evidence boundary

The completion mitigation is the only scored Agent mitigation. Production security integration is documented separately in [security_controls.md](security_controls.md) and [prompt_injection_analysis.md](prompt_injection_analysis.md). Latest focused test results: completion 8/8, failure analysis 11/11, direct/indirect injection 9/9, security controls 31/31, trajectory evaluator 16/16, existing Agent tests 27/27.

## Artifacts

- Per-case after-run matrix: [evaluation/failure_analysis.csv](../evaluation/failure_analysis.csv)
- Final benchmark: [evaluation/trajectory_dataset.py](../evaluation/trajectory_dataset.py)
- Evaluator: [evaluation/trajectory_evaluator.py](../evaluation/trajectory_evaluator.py)

The named official source files `W8-Task-Set-C.md` and `Week8_Module4_Agents.docx` were not present in the workspace; this report follows the complete requirements supplied with the task.

## Final Status

WEEK 8 IMPLEMENTATION COMPLETE - LIVE TRAJECTORY-GAP EVIDENCE NOT OBSERVED
