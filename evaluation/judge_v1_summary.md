# Judge V1 Summary

## Judge V1 Results

- Total cases: 27
- Judge PASS: 25
- Judge FAIL: 2
- Human PASS: 22
- Human FAIL: 5
- Agreements: 22
- Disagreements: 5
- Agreement percentage: 81.48%

## Agreement by Mode

| Mode | Cases | Agreements | Disagreements | Agreement % |
|---|---:|---:|---:|---:|
| calculation_rule | 3 | 3 | 0 | 100.00% |
| eligibility_conditions | 3 | 3 | 0 | 100.00% |
| exact_fact | 10 | 7 | 3 | 70.00% |
| multi_condition_matrix | 1 | 1 | 0 | 100.00% |
| multi_tier_penalties | 4 | 3 | 1 | 75.00% |
| procedure_application | 5 | 4 | 1 | 80.00% |
| unanswerable_fallback | 1 | 1 | 0 | 100.00% |

## Disagreement IDs

Q1, Q2, Q3, Q6, Q24

## Disagreements

### Q1

- Taxonomy mode: exact_fact
- Human label: FAIL
- Human reason: The answer provides the correct annual leave entitlement but is incomplete because it omits important policy details required for a complete answer, including the pro-rata rule, monthly accrual rate, and three-month eligibility condition.
- Judge label: PASS
- Judge reason: The answer accurately addresses the user's question and is supported by the provided policy context.

### Q2

- Taxonomy mode: exact_fact
- Human label: FAIL
- Human reason: The answer provides the correct vacation entitlement but is incomplete because it omits important policy details required for a complete answer, including the five-working-day advance request requirement and the manager approval process.
- Judge label: PASS
- Judge reason: The answer addresses the user's question about the number of days off for vacation and is supported by the context, which states that all full-time employees are entitled to 20 working days of annual leave per calendar year.

### Q3

- Taxonomy mode: exact_fact
- Human label: FAIL
- Human reason: The answer correctly states the 10-day carry-over and 5-day encashment limits, but its concluding statement incorrectly says up to 10 days can be encashed.
- Judge label: PASS
- Judge reason: The answer accurately addresses the user's question and is supported by the retrieved policy context.

### Q6

- Taxonomy mode: multi_tier_penalties
- Human label: FAIL
- Human reason: The answer correctly states the late-arrival and half-day thresholds but is incomplete because it omits the material monthly leave-without-pay consequence and the quarterly escalation for repeated lateness.
- Judge label: PASS
- Judge reason: The answer accurately addresses the user's question and is supported by the provided policy context.

### Q24

- Taxonomy mode: procedure_application
- Human label: PASS
- Human reason: The answer accurately states written disclosure to HR within 5 working days.
- Judge label: FAIL
- Judge reason: The generated answer does not match the user's question. The user asked about the time frame for disclosing a potential conflict of interest to HR, but the generated answer mentions a different document (employee_conduct_policy.pdf) and does not provide the correct information from the provided policy context.
