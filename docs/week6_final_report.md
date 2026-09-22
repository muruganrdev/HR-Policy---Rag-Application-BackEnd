# Week 6 Final Evaluation Evidence Report

## 1. Week 6 objective

The objective of Week 6 was to complete the repository’s evaluation evidence chain without changing the retrieval pipeline, the ChromaDB records, or the evaluation dataset. The work focused on the dataset, taxonomy coding, deterministic assertions, manual reference labeling with evidence-preparation assistance where applicable, Judge V1, genuine disagreement analysis, Judge V2, and the cross-run comparison evidence that explains what changed and what did not.

## 2. Evaluation dataset

The repository’s Week 6 evidence dataset contains 27 cases, covering questions Q1–Q25, Q27, and Q28. Q26 is intentionally excluded. The dataset therefore represents the confirmed 27-case evidence set and not an expanded or synthetic question set.

## 3. Taxonomy modes and counts

The 27-case evaluation dataset uses 7 taxonomy modes:

- exact_fact: 10 cases
- eligibility_conditions: 3 cases
- procedure_application: 5 cases
- multi_tier_penalties: 4 cases
- calculation_rule: 3 cases
- multi_condition_matrix: 1 case
- unanswerable_fallback: 1 case

These classifications are represented in the repository evidence files and are used to organize the one-command evaluation table. The evidence files for the dataset and labels are [evaluation/evaluation_dataset.py](evaluation/evaluation_dataset.py) and [evaluation/labels_27.json](evaluation/labels_27.json).

## 4. Regression cases

The confirmed regression cases included in the standard Week 6 evidence set are:

- Q1
- Q2
- Q6
- Q15

These cases must stay unchanged because they prove that the evaluation path remains anchored to the existing 27-case dataset rather than a separate or rewritten benchmark.

## 5. Deterministic assertion vs Judge split

The deterministic assertion checks are implemented in [evaluation/assertions.py](evaluation/assertions.py) and evaluate 4 criteria outside the LLM Judge:

1. Policy section reference resolves to a real policy section.
2. Handbook version is cited and matches the repository handbook version.
3. Notice-period figure is numeric.
4. Unsupported/out-of-policy refusal path is detected through deterministic wording.

The semantic LLM Judge in [evaluation/judge.py](evaluation/judge.py), together with the semantic prompts in [evaluation/judge_v1.txt](evaluation/judge_v1.txt) and [evaluation/judge_v2.txt](evaluation/judge_v2.txt), is limited to the single semantic criterion:

“Does the answer correctly answer the user’s question using the provided policy context without introducing unsupported claims?”

This split preserves the distinction between deterministic evidence checks and the semantic answer-judging criterion. The judge is not asked to re-implement the four deterministic checks.

## 6. Blind-labeling process and limitation

The reference-label evidence is stored in [evaluation/labels_27.json](evaluation/labels_27.json). The evidence-preparation trail is documented in [evaluation/step4b_labeling_audit.md](evaluation/step4b_labeling_audit.md).

All 27 cases were manually reviewed by the human evaluator, Murugan, before the Judge run. The final reference labels represent the human evaluator’s decisions, not AI-generated labels. AI assistance was used only where applicable during evidence preparation and initial analysis; it did not replace the final human labeling decision. The five manually identified FAIL cases were Q1, Q2, Q3, Q6, and Q15; the remaining 22 cases were marked PASS. The final human reference labels were recorded in [evaluation/labels_27.json](evaluation/labels_27.json). The repository’s existing label-checkpoint commit/timestamp evidence and audit record preserve that the labels checkpoint occurred before the fresh Judge evaluation.

## 7. Judge V1

The judge V1 semantic artifact is implemented in [evaluation/judge.py](evaluation/judge.py), with prompt evidence in [evaluation/judge_v1.txt](evaluation/judge_v1.txt). The final validated agreement artifact is [evaluation/judge_v1_agreement.json](evaluation/judge_v1_agreement.json), and the judge output evidence is in [evaluation/judge_v1_results.json](evaluation/judge_v1_results.json).

Stored Judge V1 result:

- Cases: 27
- Agreements: 24
- Disagreements: 3
- Agreement: 88.89%

The previous 11.11% result was caused by an Ollama typed-response parsing failure and is not part of the valid Judge V1 semantic agreement evidence.

## 8. V1 disagreements

The genuine V1 disagreements are Q3, Q6, and Q24, as recorded in [evaluation/judge_v1_disagreements.md](evaluation/judge_v1_disagreements.md) and [evaluation/judge_v1_summary.md](evaluation/judge_v1_summary.md).

Those disagreements are the semantic disagreements that matter for the baseline judge. They are the same adversarial examples that seeded the V2 prompt design.

## 9. Judge V2

Judge V2 was created with a separate prompt artifact, [evaluation/judge_v2.txt](evaluation/judge_v2.txt), and the judge runner structure mirrors the V1 judge while using two selected disagreement examples as few-shot examples. The selection rationale is documented in [evaluation/judge_v2_selection.md](evaluation/judge_v2_selection.md), and the agreement evidence is recorded in [evaluation/judge_v2_agreement.json](evaluation/judge_v2_agreement.json).

Stored Judge V2 result:

- Cases: 27
- Agreements: 24
- Disagreements: 3
- Agreement: 88.89%

The specific case-level changes from V1 → V2 were:

- Q24: V1 FAIL → V2 PASS
- Q28: V1 PASS → V2 FAIL

Aggregate agreement stayed unchanged:

- V1 = 88.89%
- V2 = 88.89%
- Difference = 0 percentage points

This evidence confirms that V2 did not improve aggregate Judge agreement. The objective result is that V2 changed a small number of case-level verdicts but preserved the overall agreement rate.

## 10. V1 → V2 comparison

The relevant comparison is between the semantic judge artifacts and the reference labels, not between two differently defined metrics.

| Metric | V1 | V2 | Difference |
|---|---:|---:|---:|
| Agreement | 88.89% | 88.89% | 0.00 percentage points |
| Agreements count | 24 | 24 | 0 |
| Disagreements count | 3 | 3 | 0 |

Case-level verdict movement:

- Q24: V1 FAIL → V2 PASS
- Q28: V1 PASS → V2 FAIL

Mode-level comparison is not preserved as an independent artifact in the repository; the case-level changes and aggregate agreement evidence remain the strongest traceable evidence.

## 11. Prediction artifact note

The repository preserves [evaluation/prediction.txt](evaluation/prediction.txt). It contains the prediction statement used for the V2 iteration, but it is not itself a Judge execution/result artifact and therefore does not independently prove the outcome of the prediction.

This means:

- [evaluation/prediction.txt](evaluation/prediction.txt) is preserved repository evidence.
- It records the prediction statement for the V2 iteration rather than a Judge execution/result artifact.
- The prediction statement is not independently verified beyond the repository evidence and must not be treated as a validated execution outcome.

## 12. One-command evaluation

The one-command evaluation entry point is implemented in [evaluation/run_week6_eval.py](evaluation/run_week6_eval.py). It prints the requested taxonomy-mode table and also labels the results as a reference-label pass-rate table, not as a judge-agreement table.

The repository contains a completed one-command evaluation result showing 24/27 reference-label passes (88.89%). The latest end-to-end 27-case run was manually stopped before completion because of runtime, so no new final measurement is claimed from that interrupted run.

Stored reference-label evidence:

```text
Mode                         Cases   Pass   Fail   Pass Rate
-------------------------------------------------------------
exact_fact                    10      8      2       80.0%
eligibility_conditions         3      3      0      100.0%
procedure_application          5      5      0      100.0%
multi_tier_penalties           4      3      1       75.0%
calculation_rule               3      3      0      100.0%
multi_condition_matrix         1      1      0      100.0%
unanswerable_fallback          1      1      0      100.0%
-------------------------------------------------------------
TOTAL                         27     24      3       88.89%
```

Important distinction:

- This table measures the reference-label pass rate generated by the one-command evaluation script.
- It must not be described as the semantic Judge agreement rate.
- The stored repository evidence supports a 24/27 reference-label result = 88.89%.
- The latest end-to-end 27-case run was manually stopped before completion, so the repository does not carry a fresh final 27-case measurement from that interrupted run.

## 13. Test results

No fresh repository test result is being claimed for the current report. The test suite was not rerun here, and the final end-to-end 27-case verification was not completed in the latest run because the evaluation was manually stopped before completion.

## 14. Key findings

The main findings are simple and evidence based:

- The evaluation dataset contains 27 confirmed cases and 7 taxonomy modes.
- The deterministic assertion checks are separate from the semantic judge criterion.
- The final reference labels are manual decisions by Murugan after all 27 cases were reviewed; AI assistance applied only to evidence preparation where applicable.
- Judge V1 yields 24/27 agreement.
- Judge V2 yields the same 24/27 aggregate agreement, but the verdict changes Q24 and Q28 only.
- The few-shot example selection uses Q3 and Q24 as examples, while Q6 is intentionally not selected.
- The one-command reference-label pass-rate table is a separate metric from Judge agreement.
- The prediction statement is preserved in [evaluation/prediction.txt](evaluation/prediction.txt), but it is not a Judge execution/result artifact.

## 15. Potential limitations

Potential limitations are important for a mentor-facing explanation:

- The prediction file is preserved in [evaluation/prediction.txt](evaluation/prediction.txt) as a written pre-iteration prediction/selection note; it does not independently provide a separate machine-generated measurement before the V2 Judge run.
- The final labels in [evaluation/labels_27.json](evaluation/labels_27.json) are human-reviewed/manual decisions by Murugan; AI assistance was limited to evidence preparation where applicable.
- The repository contains a one-command evaluation wrapper, but it reports a reference-label pass-rate table rather than a judge agreement table.
- The V2 prompt changed only a few case-level outcomes and did not move the overall aggregate agreement.
- No mode-level V1 → V2 artifact is available for a deeper mode-by-mode comparison.

## 16. Final scope confirmation

Implemented in Week 6:

- Evaluation dataset
- Taxonomy classification
- Regression cases
- Deterministic assertions
- Blind labeling with evidence-preparation assistance where applicable and final human decisions
- Judge V1
- Judge disagreement analysis
- Judge V2
- V1 → V2 comparison
- One-command evaluation
- Evaluation evidence/reporting

Not implemented:

- Query Expansion
- Retrieval Reranking
- HyDE
- Any other Week 7 RAG technique

## 17. Final status

IMPLEMENTATION COMPLETE — final end-to-end verification is pending.

The Week 6 evaluation framework and required evidence artifacts are implemented, but the latest complete 27-case verification was not completed. The repository preserves the stored one-command reference-label result showing 24/27 passes (88.89%), while the latest end-to-end run was manually stopped before completion and therefore remains not remeasured.
