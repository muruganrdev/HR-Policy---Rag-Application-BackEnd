# Judge V1 Genuine Disagreements

These are the only cases where the fresh Judge V1 verdict differs from the unchanged reference label.

## Q1

Question:
How much annual leave do employees get?

Actual Answer:
According to the context, all full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week.

Policy Evidence:
2. Annual Leave (Vacation Leave)
All full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week. New employees are eligible for annual leave after completing 3 months of continuous employment. Annual leave accrues at a rate of 1.67 days per month of service.

Human/Reference Label: FAIL

Human/Reference Reason: The answer provides the correct annual leave entitlement but is incomplete because it omits important policy details required for a complete answer, including the pro-rata rule, monthly accrual rate, and three-month eligibility condition.

Taxonomy Mode: exact_fact

Judge V1 Verdict: PASS

Judge V1 Reason: The answer accurately addresses the user's question and is supported by the provided policy context.

## Q2

Question:
How many days off can I take for vacation?

Actual Answer:
According to the context from the leave_policy.pdf, Chunk 2, all full-time employees are entitled to 20 working days of annual leave per calendar year. Therefore, you can take 20 days off for vacation.

Policy Evidence:
2. Annual Leave (Vacation Leave)
All full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week.
3. WFH Entitlement
Eligible employees may work from home for a maximum of 2 days per week.

Human/Reference Label: FAIL

Human/Reference Reason: The answer provides the correct vacation entitlement but is incomplete because it omits important policy details required for a complete answer, including the five-working-day advance request requirement and the manager approval process.

Taxonomy Mode: exact_fact

Judge V1 Verdict: PASS

Judge V1 Reason: The answer addresses the user's question about the number of days off for vacation and is supported by the context, which states that all full-time employees are entitled to 20 working days of annual leave per calendar year.

## Q3

Question:
How many days of unused annual leave can be carried over or encashed?

Actual Answer:
According to the context, unused annual leave of up to 10 days may be carried over to the next calendar year. Any balance exceeding 10 days will lapse on December 31st. Additionally, employees wishing to encash unused leave must submit a request to HR by November 30th, and a maximum of 5 days may be encashed per calendar year. So, the answer is: up to 10 days can be carried over or encashed.

Policy Evidence:
2. Annual Leave (Vacation Leave)
Unused annual leave of up to 10 days may be carried over to the next calendar year. Any balance exceeding 10 days will lapse on December 31st. Employees wishing to encash unused leave must submit a request to HR by November 30th. A maximum of 5 days may be encashed per calendar year.

Human/Reference Label: FAIL

Human/Reference Reason: The answer correctly states the 10-day carry-over and 5-day encashment limits, but its concluding statement incorrectly says up to 10 days can be encashed.

Taxonomy Mode: exact_fact

Judge V1 Verdict: PASS

Judge V1 Reason: The answer accurately addresses the user's question and is supported by the retrieved policy context.

## Q6

Question:
What happens if I am late to the office?

Actual Answer:
According to the provided HR policy documents, if you arrive between 9:11 AM and 9:30 AM, it constitutes a late arrival and will be recorded. Arriving after 9:30 AM constitutes a half-day absence for attendance purposes.

Policy Evidence:
3. Punctuality Requirements
A grace period of 10 minutes is allowed. Arriving between 9:11 AM and 9:30 AM constitutes a late arrival and will be recorded. Arriving after 9:30 AM constitutes a half-day absence for attendance purposes. Three recorded late arrivals in a calendar month will result in one day of LWP.

Human/Reference Label: FAIL

Human/Reference Reason: The answer correctly states the late-arrival and half-day thresholds but is incomplete because it omits the material monthly leave-without-pay consequence and the quarterly escalation for repeated lateness.

Taxonomy Mode: multi_tier_penalties

Judge V1 Verdict: PASS

Judge V1 Reason: The answer accurately addresses the user's question and is supported by the provided policy context.

## Q24

Question:
Within how many working days must a potential conflict of interest be disclosed to HR?

Actual Answer:
According to the context, a potential conflict of interest must be disclosed to HR in writing within 5 working days. This is stated in Chunk 4 of the employee_conduct_policy.pdf document.

Policy Evidence:
4. Conflict of Interest
Employees must avoid situations where their personal interests conflict with the interests of the
company.
Employees must disclose any potential conflict of interest to HR in writing within 5 working days.
Engaging in external employment or business ventures that compete with ACME Corporation is
prohibited without prior written approval.
Accepting gifts from vendors or clients above a value of INR 1,000 must be disclosed to HR.

9. Grievance Process
Employees who believe they have been treated unfairly have the right to raise a formal grievance.
The grievance must be submitted in writing to HR within 30 days of the incident. HR will
acknowledge receipt within 5 working days and complete the investigation within 30 working days.
 (C) 2024 ACME Corporation - Human Resources Department - SAMPLE DOCUMENT

6. Maximum Working Hours
No employee shall work more than 48 hours in any single week without explicit written approval
from HR and the department VP.
Employees are entitled to a mandatory rest period of at least 12 hours between shifts.
Consecutive working days without a day off shall not exceed 6 days.

4. Approval Process
Employees must request WFH days at least 24 hours in advance through the HR portal.
The direct manager must approve or reject the request within the same business day.
Managers may revoke approved WFH days with a minimum of 4 hours notice in cases of
operational urgency.

WFH arrangements can be suspended for the entire team during critical business periods such
as quarter-end reporting, audits, or major product launches.

plied at least 5 working days in advance through the HR portal.
The direct manager must approve leave requests within 2 working days of submission.

Human/Reference Label: PASS

Human/Reference Reason: The answer accurately states written disclosure to HR within 5 working days.

Taxonomy Mode: procedure_application

Judge V1 Verdict: FAIL

Judge V1 Reason: The generated answer does not match the user's question. The user asked about the time frame for disclosing a potential conflict of interest to HR, but the generated answer mentions a different document (employee_conduct_policy.pdf) and does not provide the correct information from the provided policy context.
