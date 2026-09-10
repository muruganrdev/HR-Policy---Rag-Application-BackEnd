# Week 5 — HR Policy RAG Evaluation

## Section 1 — Expected Answers / Ground Truth

### Q1 — How much annual leave do employees get?

**Expected Source:** leave_policy.pdf

**Expected Answer:**
Full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time workweek. Annual leave accrues at a rate of 1.67 days per month of service, and new employees become eligible to take annual leave after completing 3 months of continuous employment.

**Supporting Information:**
- Policy Document: `leave_policy.pdf`
- Page Number: Page 1
- Section: Section 2 ("Annual Leave (Vacation Leave)")
- Key Conditions & Numbers:
  - Full-time entitlement: 20 working days per calendar year.
  - Part-time entitlement: Pro-rata basis based on 40-hour workweek.
  - Accrual rate: 1.67 days per month of service.
  - Eligibility waiting period: After completing 3 months of continuous employment.
  - Excerpt: *"All full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week. New employees are eligible for annual leave after completing 3 months of continuous employment. Annual leave accrues at a rate of 1.67 days per month of service."*

**Expected Keywords:**
- annual leave
- 20
- calendar year
- accrues

**Ground Truth Verification:** ✅ Verified against source document

---

### Q2 — How many days off can I take for vacation?

**Expected Source:** leave_policy.pdf

**Expected Answer:**
Full-time employees can take up to 20 working days off for vacation (annual leave) per calendar year, accruing at 1.67 days per month of service once 3 months of continuous employment are completed. Part-time employees receive pro-rata vacation leave. Leave applications must be submitted via the HR portal at least 5 working days in advance and require managerial approval within 2 working days.

**Supporting Information:**
- Policy Document: `leave_policy.pdf`
- Page Number: Page 1
- Section: Section 2 ("Annual Leave (Vacation Leave)")
- Key Conditions & Numbers:
  - 20 working days per calendar year for full-time staff.
  - Part-time: Pro-rata against a 40-hour full-time week.
  - Accrual: 1.67 days per month of service.
  - Eligibility: After 3 months of continuous service.
  - Advance notice requirement: Applied at least 5 working days in advance via HR portal; manager approves within 2 working days.
  - Excerpt: *"All full-time employees are entitled to 20 working days of annual leave per calendar year... Annual leave must be applied at least 5 working days in advance through the HR portal. The direct manager must approve leave requests within 2 working days of submission."*

**Expected Keywords:**
- annual leave
- 20
- vacation

**Ground Truth Verification:** ✅ Verified against source document

---

### Q3 — How many days of unused annual leave can be carried over or encashed?

**Expected Source:** leave_policy.pdf

**Expected Answer:**
Employees may carry over a maximum of 10 days of unused annual leave to the next calendar year; any remaining unused balance exceeding 10 days will automatically lapse on December 31st. For encashment, employees may encash a maximum of 5 days of unused annual leave per calendar year by submitting a formal request to HR by November 30th.

**Supporting Information:**
- Policy Document: `leave_policy.pdf`
- Page Number: Page 1
- Section: Section 2 ("Annual Leave (Vacation Leave)")
- Key Conditions & Numbers:
  - Carry-over limit: Up to 10 days into the following calendar year.
  - Forfeiture rule: Any balance exceeding 10 days lapses on December 31st.
  - Encashment limit: Maximum of 5 days per calendar year.
  - Encashment deadline: Request must be submitted to HR by November 30th.
  - Excerpt: *"Unused annual leave of up to 10 days may be carried over to the next calendar year. Any balance exceeding 10 days will lapse on December 31st. Employees wishing to encash unused leave must submit a request to HR by November 30th. A maximum of 5 days may be encashed per calendar year."*

**Expected Keywords:**
- carried over
- 10 days
- encash
- 5 days

**Ground Truth Verification:** ✅ Verified against source document

---

### Q4 — What is the paid maternity and paternity leave duration?

**Expected Source:** leave_policy.pdf

**Expected Answer:**
- **Maternity Leave:** Eligible female employees are entitled to 26 weeks of paid maternity leave for the first two live births. This leave may commence up to 8 weeks before the expected delivery date. Employees must give at least 12 weeks' prior notice to HR accompanied by medical proof of expected delivery date.
- **Paternity Leave:** Male employees are entitled to 5 working days of paid paternity leave, which must be utilized within 30 days of the child's birth.

**Supporting Information:**
- Policy Document: `leave_policy.pdf`
- Page Number: Page 1–2
- Section: Section 4 ("Maternity and Paternity Leave")
- Key Conditions & Numbers:
  - Maternity duration: 26 weeks paid leave (applicable for first two live births).
  - Maternity commencement: Up to 8 weeks before expected date of delivery.
  - Maternity notice requirement: Notify HR at least 12 weeks prior with medical documentation.
  - Paternity duration: 5 working days paid leave.
  - Paternity usage window: Must be taken within 30 days of the birth of a child.
  - Excerpt: *"Eligible female employees are entitled to 26 weeks of paid maternity leave for the first two live births. The leave may commence 8 weeks before the expected date of delivery. Male employees are entitled to 5 working days of paid paternity leave within 30 days of the birth of a child. Employees must notify HR at least 12 weeks before the expected start of maternity leave."*

**Expected Keywords:**
- maternity
- 26 weeks
- paternity
- 5 working days

**Ground Truth Verification:** ✅ Verified against source document

---

### Q5 — What is the grace period for arriving at work in the morning?

**Expected Source:** attendance_policy.pdf

**Expected Answer:**
The grace period for morning arrival is 10 minutes. Employees are expected to be present and ready to work at their workstations by 9:00 AM; arrival up to 9:10 AM is covered by the grace period, whereas arriving between 9:11 AM and 9:30 AM constitutes a recorded late arrival.

**Supporting Information:**
- Policy Document: `attendance_policy.pdf`
- Page Number: Page 1
- Section: Section 3 ("Punctuality Requirements")
- Key Conditions & Numbers:
  - Standard start time: 9:00 AM.
  - Grace period: 10 minutes (until 9:10 AM).
  - Late arrival classification: 9:11 AM to 9:30 AM.
  - Excerpt: *"Employees are expected to be present and ready to work at their workstation by 9:00 AM. A grace period of 10 minutes is allowed. Arriving between 9:11 AM and 9:30 AM constitutes a late arrival and will be recorded."*

**Expected Keywords:**
- grace period
- 10 minutes
- 9:00 AM
- punctuality

**Ground Truth Verification:** ✅ Verified against source document

---

### Q6 — What happens if I am late to the office?

**Expected Source:** attendance_policy.pdf

**Expected Answer:**
Arrival after the 10-minute morning grace period is handled as follows:
1. **Between 9:11 AM and 9:30 AM:** Constitutes a recorded late arrival.
2. **After 9:30 AM:** Constitutes a half-day absence for attendance purposes.
3. **Monthly penalty:** 3 recorded late arrivals in a single calendar month result in a deduction of 1 day of Leave Without Pay (LWP).
4. **Quarterly threshold:** More than 5 late arrivals in a quarter may trigger a formal performance discussion.

**Supporting Information:**
- Policy Document: `attendance_policy.pdf`
- Page Number: Page 1
- Section: Section 3 ("Punctuality Requirements")
- Key Conditions & Numbers:
  - Grace period cutoff: 9:10 AM.
  - Late arrival window: 9:11 AM to 9:30 AM (recorded).
  - Half-day absence: Arriving after 9:30 AM.
  - Penalty: 3 late arrivals in a calendar month = 1 day of LWP.
  - Escalation: >5 late arrivals in a quarter may trigger a formal performance discussion.
  - Excerpt: *"Arriving between 9:11 AM and 9:30 AM constitutes a late arrival and will be recorded. Arriving after 9:30 AM constitutes a half-day absence for attendance purposes. Three recorded late arrivals in a calendar month will result in one day of LWP (Leave Without Pay). Repeated late arrivals (more than 5 in a quarter) may trigger a formal performance discussion."*

**Expected Keywords:**
- late arrival
- 9:11 AM
- half-day absence
- LWP

**Ground Truth Verification:** ✅ Verified against source document

---

### Q7 — How is habitual absenteeism handled by HR?

**Expected Source:** attendance_policy.pdf

**Expected Answer:**
An employee is considered habitually absent if they are absent for more than 6 days in a quarter without approved leave or if their absence pattern raises concern. HR and management address habitual absenteeism through progressive steps:
1. **First occurrence:** Verbal counselling conducted by the line manager.
2. **Second occurrence:** Formal written warning issued by HR.
3. **Third occurrence:** Formal disciplinary proceedings initiated in accordance with the Employee Conduct Policy.

**Supporting Information:**
- Policy Document: `attendance_policy.pdf`
- Page Number: Page 2
- Section: Section 6 ("Habitual Absenteeism")
- Key Conditions & Numbers:
  - Definition threshold: More than 6 days absent without approved leave in a quarter, or a concerning pattern.
  - Step 1: Line manager verbal counselling.
  - Step 2: HR written warning.
  - Step 3: Formal disciplinary proceedings under Employee Conduct Policy.
  - Excerpt: *"An employee is considered habitually absent if they are absent for more than 6 days in a quarter without approved leave, or if their pattern of absence raises concern. First occurrence: Verbal counselling by the line manager. Second occurrence: Written warning issued by HR. Third occurrence: Formal disciplinary proceedings in accordance with the Employee Conduct Policy."*

**Expected Keywords:**
- habitual absent
- 6 days
- verbal counselling
- written warning

**Ground Truth Verification:** ✅ Verified against source document

---

### Q8 — Can I work from home and what is the weekly limit?

**Expected Source:** work_from_home_policy.pdf

**Expected Answer:**
Yes, eligible employees may work from home for a maximum of 2 days per week. The default designated WFH days are Wednesday and Friday, unless an alternative schedule is approved by the department head. Unused WFH days cannot be carried forward to subsequent weeks, WFH days falling on public holidays or annual leave are not replaced, and employees on probation (first 6 months) are not eligible.

**Supporting Information:**
- Policy Document: `work_from_home_policy.pdf`
- Page Number: Page 1
- Section: Section 3 ("WFH Entitlement")
- Key Conditions & Numbers:
  - Weekly allowance: Maximum 2 days per week.
  - Default days: Wednesday and Friday (department head can approve alternatives).
  - Carry-over: Unused WFH days cannot be rolled over to the following week.
  - Replacement: Days lost to public holidays or annual leave are not replaced.
  - Probation exclusion: Ineligible during the 6-month probationary period.
  - Excerpt: *"Eligible employees may work from home for a maximum of 2 days per week. The default WFH days are Wednesday and Friday, unless otherwise approved by the department head. Employees may not carry forward unused WFH days to the following week. WFH days during public holidays or annual leave periods are not replaced. During probationary periods (first 6 months), employees are not eligible for WFH arrangements."*

**Expected Keywords:**
- work from home
- 2 days
- week
- Wednesday
- Friday

**Ground Truth Verification:** ✅ Verified against source document

---

### Q9 — What are the eligibility requirements for remote work?

**Expected Source:** work_from_home_policy.pdf

**Expected Answer:**
To be eligible for remote work (WFH), an employee must satisfy all four of the following requirements:
1. **Employment Duration:** Have completed at least 6 months of continuous employment with ACME Corporation (past the probationary period).
2. **Role Suitability:** Hold a role that can be performed remotely without negatively affecting customer service or team operations (roles requiring physical presence like reception, facilities, or on-site IT support are excluded).
3. **Performance Record:** Demonstrate a consistent track record of meeting performance targets and deadlines.
4. **Home Work Environment & Connectivity:** Maintain a suitable home workspace with reliable high-speed internet (minimum 10 Mbps) and a private work area.

**Supporting Information:**
- Policy Document: `work_from_home_policy.pdf`
- Page Number: Page 1
- Section: Section 2 ("Eligibility")
- Key Conditions & Numbers:
  - Minimum tenure: 6 months continuous employment.
  - Minimum internet bandwidth: 10 Mbps reliable connection.
  - Physical workspace: Private workspace at home.
  - Excluded roles: Reception, facilities, on-site IT support, and other roles requiring physical presence.
  - Excerpt: *"Employees are eligible for WFH arrangements if they meet all of the following criteria: Have completed at least 6 months of continuous employment with ACME Corporation. Hold a role that can be performed remotely without impacting customer service or team operations. Have a demonstrated track record of meeting performance targets and deadlines. Have a suitable home working environment with reliable internet (minimum 10 Mbps) and a private workspace. Roles that require physical presence (e.g., reception, facilities, on-site IT support) are excluded from WFH eligibility."*

**Expected Keywords:**
- 6 months
- continuous employment
- 10 Mbps
- eligibility

**Ground Truth Verification:** ✅ Verified against source document

---

### Q10 — How much advance notice is required to request a work from home day?

**Expected Source:** work_from_home_policy.pdf

**Expected Answer:**
Employees must request WFH days at least 24 hours in advance through the HR portal. The direct manager is required to approve or reject the request within the same business day. (Note: Managers may revoke an approved WFH day with a minimum of 4 hours' notice in situations of operational urgency).

**Supporting Information:**
- Policy Document: `work_from_home_policy.pdf`
- Page Number: Page 1
- Section: Section 4 ("Approval Process")
- Key Conditions & Numbers:
  - Advance submission: At least 24 hours in advance.
  - Submission channel: HR portal.
  - Manager response: Within the same business day.
  - Revocation notice: Minimum 4 hours notice in case of operational urgency.
  - Excerpt: *"Employees must request WFH days at least 24 hours in advance through the HR portal. The direct manager must approve or reject the request within the same business day. Managers may revoke approved WFH days with a minimum of 4 hours notice in cases of operational urgency."*

**Expected Keywords:**
- 24 hours
- advance
- HR portal
- manager

**Ground Truth Verification:** ✅ Verified against source document

---

### Q11 — What are the core working hours and break timings?

**Expected Source:** working_hours_policy.pdf

**Expected Answer:**
- **Working Hours:** Full-time employees work 40 paid hours per week, structured as 8 hours per day across 5 working days (Monday to Friday). Core hours are 9:00 AM to 6:00 PM. (With managerial approval, flexible start between 8:00 AM and 10:00 AM is permitted with core hours of 10:00 AM to 4:00 PM).
- **Break Timings:**
  - **Lunch Break:** 1 hour unpaid lunch break from 1:00 PM to 2:00 PM.
  - **Short Breaks:** Two 15-minute paid breaks daily — one at 11:00 AM and one at 4:00 PM.

**Supporting Information:**
- Policy Document: `working_hours_policy.pdf`
- Page Number: Page 1
- Section: Section 2 ("Standard Working Hours") (and Section 3 "Flexible Working Arrangements")
- Key Conditions & Numbers:
  - Weekly paid hours: 40 paid hours (8 hours/day, Monday–Friday).
  - Standard core hours: 9:00 AM to 6:00 PM.
  - Lunch break: 1:00 PM to 2:00 PM (1 hour, unpaid).
  - Short breaks: Two 15-minute breaks at 11:00 AM and 4:00 PM.
  - Excerpt: *"The standard working week for full-time employees consists of 40 paid hours, structured as 8 hours per day across 5 working days (Monday to Friday). Core hours: 9:00 AM to 6:00 PM. Lunch break: 1:00 PM to 2:00 PM (unpaid, 1 hour). Short breaks: Employees are entitled to two 15-minute breaks - one at 11:00 AM and one at 4:00 PM."*

**Expected Keywords:**
- 40 paid hours
- 9:00 AM
- 6:00 PM
- lunch break

**Ground Truth Verification:** ✅ Verified against source document

---

### Q12 — What is the shift allowance for employees working the night shift?

**Expected Source:** working_hours_policy.pdf

**Expected Answer:**
Employees assigned to the night shift (10:00 PM to 6:00 AM) receive a 20% shift allowance calculated on their base salary. Shift schedules are communicated at least 7 days in advance.

**Supporting Information:**
- Policy Document: `working_hours_policy.pdf`
- Page Number: Page 1
- Section: Section 4 ("Shift Work")
- Key Conditions & Numbers:
  - Night shift hours: 10:00 PM to 6:00 AM.
  - Allowance: 20% on base salary.
  - Schedule notice: At least 7 days in advance.
  - Excerpt: *"Shift assignments will be communicated at least 7 days in advance. Night shift employees receive a 20% shift allowance on their base salary."*

**Expected Keywords:**
- night shift
- 20%
- shift allowance
- 10:00 PM

**Ground Truth Verification:** ✅ Verified against source document

---

### Q13 — How is overtime work compensated for non-exempt employees?

**Expected Source:** working_hours_policy.pdf

**Expected Answer:**
For non-exempt employees, overtime work (work performed beyond 40 hours in a standard week or beyond 8 hours in a standard day) that is pre-approved in writing by the department head is compensated at:
- **1.5x the hourly rate** for overtime worked on weekdays.
- **2.0x (double time) the hourly rate** for overtime worked on weekends and public holidays.
(Note: Exempt/managerial employees receive compensatory leave at a 1:1 ratio instead of monetary overtime pay. Overtime exceeding 12 hours in a single day is prohibited without emergency VP-level approval).

**Supporting Information:**
- Policy Document: `working_hours_policy.pdf`
- Page Number: Page 1–2
- Section: Section 5 ("Overtime")
- Key Conditions & Numbers:
  - Overtime threshold: >40 hours/week or >8 hours/day.
  - Non-exempt weekday rate: 1.5x hourly rate.
  - Non-exempt weekend/public holiday rate: 2.0x hourly rate.
  - Prerequisite: Written pre-approval from department head.
  - Daily cap: No more than 12 hours in a single day (unless emergency VP approval).
  - Excerpt: *"Overtime is defined as any work performed beyond 40 hours in a standard week or beyond 8 hours in a standard day. All overtime must be pre-approved in writing by the employee's department head. For non-exempt employees, overtime is compensated at 1.5x the hourly rate for weekdays and 2.0x for weekend and public holiday work. Exempt (managerial) employees receive compensatory leave at a 1:1 ratio for overtime worked."*

**Expected Keywords:**
- overtime
- 1.5x
- 2.0x
- non-exempt

**Ground Truth Verification:** ✅ Verified against source document

---

### Q14 — How and within how many days should workplace harassment be reported?

**Expected Source:** employee_conduct_policy.pdf

**Expected Answer:**
- **How to report:** Workplace harassment, discrimination, or bullying must be formally reported to HR or to the company's designated Internal Complaints Committee (ICC).
- **Time limit:** The report must be submitted within 30 days of the incident.
Complaints are handled under a zero-tolerance policy and investigated confidentially and impartially.

**Supporting Information:**
- Policy Document: `employee_conduct_policy.pdf`
- Page Number: Page 1
- Section: Section 3 ("Workplace Harassment and Discrimination")
- Key Conditions & Numbers:
  - Reporting recipient: HR or Internal Complaints Committee (ICC).
  - Deadline: Within 30 days.
  - Scope: Physical, verbal, psychological, or cyber harassment/discrimination.
  - Excerpt: *"ACME Corporation has a zero-tolerance policy towards any form of harassment, discrimination, or bullying in the workplace, including physical, verbal, psychological, or cyber harassment... Employees who witness or experience harassment must report it to HR or the designated Internal Complaints Committee (ICC) within 30 days. All complaints will be investigated confidentially and impartially."*

**Expected Keywords:**
- harassment
- Internal Complaints Committee
- ICC
- 30 days

**Ground Truth Verification:** ✅ Verified against source document

---

### Q15 — What is the threshold value for disclosing gifts received from clients or vendors?

**Expected Source:** employee_conduct_policy.pdf

**Expected Answer:**
The threshold value for disclosing gifts received from vendors or clients is any amount above INR 1,000. Any gift exceeding this value must be formally disclosed to HR to avoid conflicts of interest. (Additionally, any potential conflict of interest must be disclosed to HR in writing within 5 working days).

**Supporting Information:**
- Policy Document: `employee_conduct_policy.pdf`
- Page Number: Page 1
- Section: Section 4 ("Conflict of Interest")
- Key Conditions & Numbers:
  - Gift value threshold: Above INR 1,000.
  - Disclosure recipient: Human Resources (HR).
  - Conflict disclosure timeframe: Potential conflicts disclosed in writing within 5 working days.
  - Excerpt: *"Employees must avoid situations where their personal interests conflict with the interests of the company... Accepting gifts from vendors or clients above a value of INR 1,000 must be disclosed to HR."*

**Expected Keywords:**
- gifts
- INR 1,000
- conflict of interest
- HR

**Ground Truth Verification:** ✅ Verified against source document

---

### Q16 — What are the progressive steps in the company disciplinary process?

**Expected Source:** employee_conduct_policy.pdf

**Expected Answer:**
ACME Corporation's progressive disciplinary process consists of 4 distinct steps:
- **Step 1: Verbal Warning** — Issued for minor first-time offences.
- **Step 2: Written Warning** — Issued for repeated minor offences or an initial moderate offence.
- **Step 3: Final Written Warning and Performance Improvement Plan (PIP)** — Issued for sustained or significant non-compliance.
- **Step 4: Termination of Employment** — Enacted for serious misconduct or repeated policy violations.
(Note: Serious misconduct such as fraud, physical violence, or data theft can lead to immediate termination without prior warnings, subject to a fair investigation).

**Supporting Information:**
- Policy Document: `employee_conduct_policy.pdf`
- Page Number: Page 2
- Section: Section 8 ("Disciplinary Process")
- Key Conditions & Numbers:
  - Step 1: Verbal Warning (minor first-time).
  - Step 2: Written Warning (repeated minor / first moderate).
  - Step 3: Final Written Warning and Performance Improvement Plan (PIP).
  - Step 4: Termination of employment (serious misconduct or repeated violations).
  - Immediate termination clause: Fraud, violence, data theft.
  - Excerpt: *"Violations of this policy will be addressed through ACME Corporation's progressive disciplinary process: Step 1: Verbal Warning - for minor first-time offences. Step 2: Written Warning - for repeated minor offences or a first moderate offence. Step 3: Final Written Warning and Performance Improvement Plan (PIP). Step 4: Termination of employment for serious misconduct or repeated policy violations. Serious misconduct (e.g., fraud, physical violence, data theft) may result in immediate termination without prior warnings, subject to a fair investigation."*

**Expected Keywords:**
- Verbal Warning
- Written Warning
- PIP
- Termination

**Ground Truth Verification:** ✅ Verified against source document

---

### Q17 — What is the notice period for employee resignation across different grades?

**Expected Source:** notice_period_policy.pdf

**Expected Answer:**
The resignation notice period depends on the employee's grade:
- **Grade 1–3 (Junior / Associate):** 30 days (1 month)
- **Grade 4–6 (Senior / Lead):** 60 days (2 months)
- **Grade 7–9 (Manager / Senior Manager):** 90 days (3 months)
- **Grade 10 and above (Director / VP / C-Suite):** 90 days minimum, or as specified in the individual employment contract.
Notice periods officially begin on the date the written resignation is submitted and accepted by HR.

**Supporting Information:**
- Policy Document: `notice_period_policy.pdf`
- Page Number: Page 1
- Section: Section 2 ("Employee Notice Period (Resignation)")
- Key Conditions & Numbers:
  - Grade 1–3: 30 days (1 month).
  - Grade 4–6: 60 days (2 months).
  - Grade 7–9: 90 days (3 months).
  - Grade 10+: 90 days minimum or employment contract term.
  - Start date: Date written resignation is submitted and accepted by HR.
  - Excerpt: *"When an employee wishes to resign, the following notice periods apply based on the employee grade: Grade 1-3 (Junior / Associate): 30 days (1 month); Grade 4-6 (Senior / Lead): 60 days (2 months); Grade 7-9 (Manager / Senior Manager): 90 days (3 months); Grade 10 and above (Director / VP / C-Suite): 90 days minimum, or as specified in the employment contract. Notice periods begin on the date the written resignation is submitted and accepted by HR."*

**Expected Keywords:**
- Grade 1-3
- 30 days
- Grade 4-6
- 60 days
- Grade 7-9
- 90 days

**Ground Truth Verification:** ✅ Verified against source document

---

### Q18 — How is the notice period buyout amount calculated for early exit?

**Expected Source:** notice_period_policy.pdf

**Expected Answer:**
The notice period buyout amount for an early exit is calculated using the following formula:
$$\text{Buyout Amount} = \left(\frac{\text{Basic Salary}}{30}\right) \times \text{Number of days not served}$$
Buyout requests must be submitted in writing to HR and require formal approval from both the department head and the HR Director.

**Supporting Information:**
- Policy Document: `notice_period_policy.pdf`
- Page Number: Page 1
- Section: Section 4 ("Notice Period Buyout")
- Key Conditions & Numbers:
  - Formula: `(Basic Salary / 30) x Number of days not served`
  - Approval prerequisites: Written submission to HR; approvals from Department Head and HR Director.
  - Excerpt: *"Employees who wish to leave before completing the full notice period may apply for an early exit by paying a notice period buyout to the company. The buyout amount is calculated as: (Basic Salary / 30) x Number of days not served. Buyout requests must be submitted in writing to HR and require approval from the department head and HR Director."*

**Expected Keywords:**
- buyout
- Basic Salary
- 30
- days not served

**Ground Truth Verification:** ✅ Verified against source document

---

### Q19 — What is the timeline for processing the Full and Final settlement after leaving?

**Expected Source:** notice_period_policy.pdf

**Expected Answer:**
The Full and Final (F&F) settlement is processed within 45 working days of the employee's last working day, subject to completing all exit formalities and knowledge transfer obligations. The settlement covers salary for days worked, encashable leave balance, approved reimbursements, and gratuity (for employees with 5+ years of service under the Payment of Gratuity Act), minus any deductions for outstanding loans, dues, or unserved notice period buyout.

**Supporting Information:**
- Policy Document: `notice_period_policy.pdf`
- Page Number: Page 2
- Section: Section 8 ("Full and Final Settlement")
- Key Conditions & Numbers:
  - Processing timeline: Within 45 working days of the last working day.
  - Prerequisites: Completion of all exit formalities and adequate knowledge transfer.
  - Components included: Salary for days worked, encashable leave balance, approved reimbursements, gratuity (for 5+ years service).
  - Adjustments: Withheld/adjusted for loans, dues, or notice period buyout.
  - Excerpt: *"The Full and Final (F&F) settlement will be processed within 45 working days of the last working day, subject to completion of all exit formalities. F&F includes: salary for days worked, encashable leave balance, approved reimbursements, and gratuity (as per the Payment of Gratuity Act, for employees with 5+ years of service). F&F will be withheld or adjusted for outstanding loans, notice period buyout, or any dues owed to the company."*

**Expected Keywords:**
- Full and Final
- F&F
- 45 working days
- settlement

**Ground Truth Verification:** ✅ Verified against source document

---

### Q20 — How many paid sick leave days are employees entitled to per year and can unused sick leave be carried over?

**Expected Source:** leave_policy.pdf

**Expected Answer:**
Full-time employees are entitled to 12 days of paid sick leave per calendar year. Unused sick leave cannot be carried over to the next year and cannot be encashed (sick leave does not accrue, and any unused balance lapses). Additionally, for sick leave absences exceeding 2 consecutive days, a medical certificate from a registered medical practitioner must be provided; for 1–2 day absences, the manager must be notified by 9:00 AM on the first day.

**Supporting Information:**
- Policy Document: `leave_policy.pdf`
- Page Number: Page 1
- Section: Section 3 ("Sick Leave")
- Key Conditions & Numbers:
  - Annual entitlement: 12 days of paid sick leave per calendar year (for full-time employees).
  - Carry-over rule: Cannot be carried over (does not accrue).
  - Encashment rule: Cannot be encashed.
  - Medical certificate requirement: Required for absences exceeding 2 consecutive days.
  - Notification rule: Manager notified by 9:00 AM on first day for 1–2 day absences.
  - Excerpt: *"Full-time employees are entitled to 12 days of paid sick leave per calendar year. Sick leave does not accrue and unused sick leave cannot be carried over or encashed. For absences of 1-2 days, employees must notify their manager by 9:00 AM on the first day of absence. For absences exceeding 2 consecutive days, a medical certificate from a registered medical practitioner must be submitted."*

**Expected Keywords:**
- 12 days
- sick leave
- carried over
- medical certificate

**Ground Truth Verification:** ✅ Verified against source document


# Section 2 — Expected vs Actual Answer Comparison

This section compares the ground-truth expected answers (established in Step 1) with the actual baseline RAG outputs (collected in Step 2) across all 20 evaluation questions.

### Baseline Summary Matrix

| Q | Expected Source | Actual Cited Source(s) | Retrieval Status | Answer Status | Missing / Incorrect Information |
|---|---|---|---|---|---|
| Q1 | `leave_policy.pdf` | `leave_policy.pdf, notice_period_policy.pdf` | **PASS** | **PARTIAL** | Accrues at 1.67 days per month of service; Eligible after 3 months of continuous employment |
| Q2 | `leave_policy.pdf` | `leave_policy.pdf, working_hours_policy.pdf, work_from_home_policy.pdf` | **PASS** | **PARTIAL** | Applied at least 5 working days in advance via HR portal; Managerial approval required within 2 working days; Accrual rate (1.67 days/month) and 3 months eligibility |
| Q3 | `leave_policy.pdf` | `leave_policy.pdf, work_from_home_policy.pdf` | **PASS** | **PASS** | None |
| Q4 | `leave_policy.pdf` | `leave_policy.pdf, notice_period_policy.pdf` | **PASS** | **PASS** | None essential |
| Q5 | `attendance_policy.pdf` | `attendance_policy.pdf, working_hours_policy.pdf, work_from_home_policy.pdf` | **PASS** | **PASS** | None |
| Q6 | `attendance_policy.pdf` | `attendance_policy.pdf` | **PASS** | **PARTIAL** | After 9:30 AM: Half-day absence; 3 late arrivals in a calendar month = 1 day LWP deduction; >5 late arrivals in a quarter = formal performance discussion |
| Q7 | `attendance_policy.pdf` | `attendance_policy.pdf, work_from_home_policy.pdf` | **PASS** | **PASS** | None essential |
| Q8 | `work_from_home_policy.pdf` | `work_from_home_policy.pdf, working_hours_policy.pdf` | **PASS** | **PASS** | None |
| Q9 | `work_from_home_policy.pdf` | `work_from_home_policy.pdf, working_hours_policy.pdf` | **PASS** | **PASS** | None |
| Q10 | `work_from_home_policy.pdf` | `work_from_home_policy.pdf, attendance_policy.pdf` | **PASS** | **PASS** | None |
| Q11 | `working_hours_policy.pdf` | `working_hours_policy.pdf, attendance_policy.pdf, work_from_home_policy.pdf` | **PASS** | **PASS** | None |
| Q12 | `working_hours_policy.pdf` | `working_hours_policy.pdf, attendance_policy.pdf, leave_policy.pdf` | **PASS** | **PASS** | None |
| Q13 | `working_hours_policy.pdf` | `working_hours_policy.pdf, leave_policy.pdf` | **PASS** | **PASS** | None |
| Q14 | `employee_conduct_policy.pdf` | `employee_conduct_policy.pdf, attendance_policy.pdf, work_from_home_policy.pdf` | **PASS** | **PASS** | None |
| Q15 | `employee_conduct_policy.pdf` | `None` | **FAIL** | **FAIL** | Gift value threshold: Above INR 1,000; Disclosure recipient: HR |
| Q16 | `employee_conduct_policy.pdf` | `employee_conduct_policy.pdf, notice_period_policy.pdf` | **PASS** | **PASS** | None |
| Q17 | `notice_period_policy.pdf` | `notice_period_policy.pdf, work_from_home_policy.pdf` | **PASS** | **PASS** | None |
| Q18 | `notice_period_policy.pdf` | `notice_period_policy.pdf, attendance_policy.pdf` | **PASS** | **PASS** | None |
| Q19 | `notice_period_policy.pdf` | `notice_period_policy.pdf, employee_conduct_policy.pdf` | **PASS** | **PASS** | None |
| Q20 | `leave_policy.pdf` | `leave_policy.pdf, work_from_home_policy.pdf, working_hours_policy.pdf` | **PASS** | **PASS** | None |

---

## Detailed Question-by-Question Comparison

### Q1 — How much annual leave do employees get?

**Expected Answer:**
Full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time workweek. Annual leave accrues at a rate of 1.67 days per month of service, and new employees become eligible to take annual leave after completing 3 months of continuous employment.

**Actual RAG Answer:**
> According to the context, all full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week.

**Expected Source:** `leave_policy.pdf`

**Retrieved Source:** `leave_policy.pdf, notice_period_policy.pdf`

**Expected Facts / Keywords:**
- 20 working days per calendar year for full-time staff
- Pro-rata annual leave for part-time staff (40-hour workweek)
- Accrues at 1.67 days per month of service
- Eligible after 3 months of continuous employment

**Matched Facts:**
- 20 working days per calendar year for full-time staff
- Pro-rata annual leave for part-time staff (40-hour workweek)

**Missing / Incorrect Facts:**
- Accrues at 1.67 days per month of service
- Eligible after 3 months of continuous employment

**Retrieval Status:** `PASS`
**Answer Status:** `PARTIAL`

**Reason:**
Expected source leave_policy.pdf was retrieved. The RAG answer accurately covers full-time (20 days) and part-time (pro-rata) entitlements, but omits the 1.67 days/month accrual rate and 3-month eligibility waiting period.

---

### Q2 — How many days off can I take for vacation?

**Expected Answer:**
Full-time employees can take up to 20 working days off for vacation (annual leave) per calendar year, accruing at 1.67 days per month of service once 3 months of continuous employment are completed. Part-time employees receive pro-rata vacation leave. Leave applications must be submitted via the HR portal at least 5 working days in advance and require managerial approval within 2 working days.

**Actual RAG Answer:**
> According to the context from the leave_policy.pdf, Chunk 2, all full-time employees are entitled to 20 working days of annual leave per calendar year. Therefore, you can take 20 days off for vacation.

**Expected Source:** `leave_policy.pdf`

**Retrieved Source:** `leave_policy.pdf, working_hours_policy.pdf, work_from_home_policy.pdf`

**Expected Facts / Keywords:**
- 20 working days off for vacation (full-time staff)
- Accrues at 1.67 days/month after 3 months continuous service
- Applied at least 5 working days in advance via HR portal
- Managerial approval required within 2 working days

**Matched Facts:**
- 20 working days off for vacation (full-time staff)

**Missing / Incorrect Facts:**
- Applied at least 5 working days in advance via HR portal
- Managerial approval required within 2 working days
- Accrual rate (1.67 days/month) and 3 months eligibility

**Retrieval Status:** `PASS`
**Answer Status:** `PARTIAL`

**Reason:**
Expected source leave_policy.pdf was retrieved. The RAG answer correctly identifies the 20 days entitlement for vacation, but omits application submission procedures (5 days notice, manager approval within 2 days).

---

### Q3 — How many days of unused annual leave can be carried over or encashed?

**Expected Answer:**
Employees may carry over a maximum of 10 days of unused annual leave to the next calendar year; any remaining unused balance exceeding 10 days will automatically lapse on December 31st. For encashment, employees may encash a maximum of 5 days of unused annual leave per calendar year by submitting a formal request to HR by November 30th.

**Actual RAG Answer:**
> According to the context, unused annual leave of up to 10 days may be carried over to the next calendar year. Any balance exceeding 10 days will lapse on December 31st. Additionally, employees wishing to encash unused leave must submit a request to HR by November 30th, and a maximum of 5 days may be encashed per calendar year.
> 
> So, the answer is: up to 10 days can be carried over or encashed.

**Expected Source:** `leave_policy.pdf`

**Retrieved Source:** `leave_policy.pdf, work_from_home_policy.pdf`

**Expected Facts / Keywords:**
- Maximum 10 days carry-over to next calendar year
- Balance exceeding 10 days lapses on Dec 31st
- Maximum 5 days encashment per calendar year
- Encashment request submitted to HR by Nov 30th

**Matched Facts:**
- Maximum 10 days carry-over to next calendar year
- Balance exceeding 10 days lapses on Dec 31st
- Maximum 5 days encashment per calendar year
- Encashment request submitted to HR by Nov 30th

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source leave_policy.pdf was retrieved. The actual answer includes all key quantitative rules: 10 days carry-over, Dec 31 forfeiture, 5 days encashment limit, and Nov 30 HR request deadline.

---

### Q4 — What is the paid maternity and paternity leave duration?

**Expected Answer:**
Maternity Leave: Eligible female employees are entitled to 26 weeks of paid maternity leave for the first two live births (commencing up to 8 weeks before delivery date, 12 weeks notice to HR). Paternity Leave: Male employees are entitled to 5 working days of paid paternity leave (utilized within 30 days of child's birth).

**Actual RAG Answer:**
> According to the provided HR policy documents, the paid maternity leave duration is 26 weeks for the first two live births. The paid paternity leave duration is 5 working days.

**Expected Source:** `leave_policy.pdf`

**Retrieved Source:** `leave_policy.pdf, notice_period_policy.pdf`

**Expected Facts / Keywords:**
- Maternity duration: 26 weeks paid leave
- Maternity scope: First two live births
- Paternity duration: 5 working days paid leave

**Matched Facts:**
- Maternity duration: 26 weeks paid leave
- Maternity scope: First two live births
- Paternity duration: 5 working days paid leave

**Missing / Incorrect Facts:**
- None essential

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source leave_policy.pdf was retrieved. The RAG answer states both maternity (26 weeks, first two births) and paternity (5 working days) durations accurately.

---

### Q5 — What is the grace period for arriving at work in the morning?

**Expected Answer:**
The grace period for morning arrival is 10 minutes. Employees are expected to be present and ready to work at their workstations by 9:00 AM; arrival up to 9:10 AM is covered by the grace period.

**Actual RAG Answer:**
> According to the context in the "Attendance Policy" document (Chunk 3), the grace period for arriving at work in the morning is 10 minutes.

**Expected Source:** `attendance_policy.pdf`

**Retrieved Source:** `attendance_policy.pdf, working_hours_policy.pdf, work_from_home_policy.pdf`

**Expected Facts / Keywords:**
- Grace period: 10 minutes
- Standard start time: 9:00 AM (until 9:10 AM)

**Matched Facts:**
- Grace period: 10 minutes

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source attendance_policy.pdf was retrieved. The answer concisely and accurately identifies the 10-minute grace period.

---

### Q6 — What happens if I am late to the office?

**Expected Answer:**
Arrival after 10-minute grace period: 1) 9:11 AM to 9:30 AM: Recorded late arrival. 2) After 9:30 AM: Half-day absence. 3) 3 recorded late arrivals in a calendar month result in deduction of 1 day Leave Without Pay (LWP). 4) More than 5 late arrivals in a quarter may trigger formal performance discussion.

**Actual RAG Answer:**
> According to the provided HR policy documents, if you arrive between 9:11 AM and 9:30 AM, it constitutes a late arrival and will be recorded.

**Expected Source:** `attendance_policy.pdf`

**Retrieved Source:** `attendance_policy.pdf`

**Expected Facts / Keywords:**
- 9:11 AM to 9:30 AM: Recorded late arrival
- After 9:30 AM: Half-day absence
- 3 late arrivals in a calendar month = 1 day LWP deduction
- >5 late arrivals in a quarter = formal performance discussion

**Matched Facts:**
- 9:11 AM to 9:30 AM: Recorded late arrival

**Missing / Incorrect Facts:**
- After 9:30 AM: Half-day absence
- 3 late arrivals in a calendar month = 1 day LWP deduction
- >5 late arrivals in a quarter = formal performance discussion

**Retrieval Status:** `PASS`
**Answer Status:** `PARTIAL`

**Reason:**
Expected source attendance_policy.pdf was retrieved. The RAG answer mentions the late arrival window (9:11-9:30 AM), but omits half-day absence after 9:30 AM, 3-late LWP penalty, and >5 quarterly threshold.

---

### Q7 — How is habitual absenteeism handled by HR?

**Expected Answer:**
Habitual absenteeism (>6 days absent in a quarter without approved leave): 1) First occurrence: Verbal counselling by line manager. 2) Second occurrence: Written warning by HR. 3) Third occurrence: Formal disciplinary proceedings in accordance with Employee Conduct Policy.

**Actual RAG Answer:**
> According to the provided HR policy documents, habitual absenteeism is handled as follows:
> 
> * First occurrence: Verbal counselling by the line manager.
> * Second occurrence: Written warning issued by HR.
> * Third occurrence: Formal disciplinary proceedings in accordance with the Employee Conduct Policy.
> 
> This information can be found in Chunk 6 of the attendance_policy.pdf document.

**Expected Source:** `attendance_policy.pdf`

**Retrieved Source:** `attendance_policy.pdf, work_from_home_policy.pdf`

**Expected Facts / Keywords:**
- Step 1: Verbal counselling by line manager
- Step 2: Written warning issued by HR
- Step 3: Formal disciplinary proceedings under Employee Conduct Policy
- Definition threshold: >6 days absent without approved leave in a quarter

**Matched Facts:**
- Step 1: Verbal counselling by line manager
- Step 2: Written warning issued by HR
- Step 3: Formal disciplinary proceedings under Employee Conduct Policy

**Missing / Incorrect Facts:**
- None essential

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source attendance_policy.pdf was retrieved. All 3 progressive disciplinary handling steps are enumerated accurately.

---

### Q8 — Can I work from home and what is the weekly limit?

**Expected Answer:**
Yes, eligible employees may work from home for a maximum of 2 days per week. Default designated WFH days are Wednesday and Friday, unless alternative schedule approved by department head.

**Actual RAG Answer:**
> According to the context, you can work from home, and the weekly limit is 2 days per week, with the default WFH days being Wednesday and Friday, unless otherwise approved by the department head. (Source: work_from_home_policy.pdf, Chunk: 3)

**Expected Source:** `work_from_home_policy.pdf`

**Retrieved Source:** `work_from_home_policy.pdf, working_hours_policy.pdf`

**Expected Facts / Keywords:**
- Can work from home: Yes
- Weekly limit: Maximum 2 days per week
- Default days: Wednesday and Friday
- Alternative schedule requires department head approval

**Matched Facts:**
- Can work from home: Yes
- Weekly limit: Maximum 2 days per week
- Default days: Wednesday and Friday
- Alternative schedule requires department head approval

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source work_from_home_policy.pdf was retrieved. The actual answer completely and accurately answers all components of the prompt.

---

### Q9 — What are the eligibility requirements for remote work?

**Expected Answer:**
Eligibility criteria for remote work: 1) At least 6 months continuous employment (past probation). 2) Role can be performed remotely (reception, facilities, on-site IT excluded). 3) Track record of meeting performance targets. 4) Suitable home environment with reliable internet (min 10 Mbps) & private workspace.

**Actual RAG Answer:**
> According to Chunk: 2 of the work_from_home_policy.pdf, the eligibility requirements for remote work are:
> 
> * Have completed at least 6 months of continuous employment with ACME Corporation.
> * Hold a role that can be performed remotely without impacting customer service or team operations.
> * Have a demonstrated track record of meeting performance targets and deadlines.
> * Have a suitable home working environment with reliable internet (minimum 10 Mbps) and a private workspace.
> 
> Roles that require physical presence (e.g., reception, facilities, on-site IT support) are excluded from WFH eligibility.

**Expected Source:** `work_from_home_policy.pdf`

**Retrieved Source:** `work_from_home_policy.pdf, working_hours_policy.pdf`

**Expected Facts / Keywords:**
- 6 months continuous employment
- Role suitability (on-site roles like reception/facilities/IT excluded)
- Track record of meeting performance targets
- Reliable high-speed internet (minimum 10 Mbps) and private workspace

**Matched Facts:**
- 6 months continuous employment
- Role suitability (on-site roles like reception/facilities/IT excluded)
- Track record of meeting performance targets
- Reliable high-speed internet (minimum 10 Mbps) and private workspace

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source work_from_home_policy.pdf was retrieved. All 4 eligibility requirements and role exclusions are stated with 100% precision.

---

### Q10 — How much advance notice is required to request a work from home day?

**Expected Answer:**
Employees must request WFH days at least 24 hours in advance through the HR portal. Direct manager must approve/reject within the same business day.

**Actual RAG Answer:**
> According to the context, employees must request WFH days at least 24 hours in advance through the HR portal.

**Expected Source:** `work_from_home_policy.pdf`

**Retrieved Source:** `work_from_home_policy.pdf, attendance_policy.pdf`

**Expected Facts / Keywords:**
- At least 24 hours in advance
- Submission channel: HR portal

**Matched Facts:**
- At least 24 hours in advance
- Submission channel: HR portal

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source work_from_home_policy.pdf was retrieved. The core advance notice requirement (24 hours via HR portal) is correctly provided.

---

### Q11 — What are the core working hours and break timings?

**Expected Answer:**
Working Hours: 40 paid hours/week (8 hours/day, Mon-Fri). Core hours: 9:00 AM to 6:00 PM. Break Timings: 1 hour unpaid lunch break (1:00 PM to 2:00 PM) and two 15-minute paid short breaks (11:00 AM and 4:00 PM).

**Actual RAG Answer:**
> According to the provided HR policy documents, the core working hours are from 9:00 AM to 6:00 PM.
> 
> As per the content in Chunk 2 of the attendance_policy.pdf, the lunch break is from 1:00 PM to 2:00 PM, which is unpaid.
> 
> Additionally, as per the content in Chunk 2 of the working_hours_policy.pdf, there are two short breaks: one at 11:00 AM and one at 4:00 PM, both lasting 15 minutes.

**Expected Source:** `working_hours_policy.pdf`

**Retrieved Source:** `working_hours_policy.pdf, attendance_policy.pdf, work_from_home_policy.pdf`

**Expected Facts / Keywords:**
- Core hours: 9:00 AM to 6:00 PM
- Lunch break: 1:00 PM to 2:00 PM (1 hour, unpaid)
- Short breaks: Two 15-minute breaks at 11:00 AM and 4:00 PM

**Matched Facts:**
- Core hours: 9:00 AM to 6:00 PM
- Lunch break: 1:00 PM to 2:00 PM (1 hour, unpaid)
- Short breaks: Two 15-minute breaks at 11:00 AM and 4:00 PM

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source working_hours_policy.pdf was retrieved. Core hours and all break timings (lunch and two 15-min short breaks) are accurately detailed.

---

### Q12 — What is the shift allowance for employees working the night shift?

**Expected Answer:**
Night shift employees (10:00 PM to 6:00 AM) receive a 20% shift allowance calculated on their base salary.

**Actual RAG Answer:**
> According to the context, in Chunk 4 of the working_hours_policy.pdf, it is stated that:
> 
> "Night shift employees receive a 20% shift allowance on their base salary."
> 
> So, the answer is: 20%

**Expected Source:** `working_hours_policy.pdf`

**Retrieved Source:** `working_hours_policy.pdf, attendance_policy.pdf, leave_policy.pdf`

**Expected Facts / Keywords:**
- 20% shift allowance on base salary
- Night shift window: 10:00 PM to 6:00 AM

**Matched Facts:**
- 20% shift allowance on base salary

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source working_hours_policy.pdf was retrieved. The 20% shift allowance rate is accurately identified.

---

### Q13 — How is overtime work compensated for non-exempt employees?

**Expected Answer:**
Overtime for non-exempt employees (pre-approved in writing): 1.5x hourly rate for weekdays, 2.0x hourly rate for weekends and public holidays.

**Actual RAG Answer:**
> According to the context, for non-exempt employees, overtime is compensated at 1.5x the hourly rate for weekdays and 2.0x for weekend and public holiday work.

**Expected Source:** `working_hours_policy.pdf`

**Retrieved Source:** `working_hours_policy.pdf, leave_policy.pdf`

**Expected Facts / Keywords:**
- 1.5x hourly rate for weekdays
- 2.0x hourly rate for weekends and public holidays

**Matched Facts:**
- 1.5x hourly rate for weekdays
- 2.0x hourly rate for weekends and public holidays

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source working_hours_policy.pdf was retrieved. Overtime compensation multipliers (1.5x weekdays, 2.0x weekends/holidays) are 100% accurate.

---

### Q14 — How and within how many days should workplace harassment be reported?

**Expected Answer:**
Workplace harassment must be formally reported to HR or the Internal Complaints Committee (ICC) within 30 days of the incident.

**Actual RAG Answer:**
> According to the context, employees who witness or experience harassment must report it to HR or the designated Internal Complaints Committee (ICC) within 30 days.

**Expected Source:** `employee_conduct_policy.pdf`

**Retrieved Source:** `employee_conduct_policy.pdf, attendance_policy.pdf, work_from_home_policy.pdf`

**Expected Facts / Keywords:**
- Report recipient: HR or Internal Complaints Committee (ICC)
- Time limit: Within 30 days

**Matched Facts:**
- Report recipient: HR or Internal Complaints Committee (ICC)
- Time limit: Within 30 days

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source employee_conduct_policy.pdf was retrieved. Both the reporting authority (HR/ICC) and the 30-day deadline are accurately answered.

---

### Q15 — What is the threshold value for disclosing gifts received from clients or vendors?

**Expected Answer:**
Accepting gifts from vendors or clients above a value of INR 1,000 must be disclosed to HR.

**Actual RAG Answer:**
> I don't know based on the provided HR policy documents.

**Expected Source:** `employee_conduct_policy.pdf`

**Retrieved Source:** `None (0 chunks cited)`

**Expected Facts / Keywords:**
- Gift value threshold: Above INR 1,000
- Disclosure recipient: HR

**Matched Facts:**

**Missing / Incorrect Facts:**
- Gift value threshold: Above INR 1,000
- Disclosure recipient: HR

**Retrieval Status:** `FAIL`
**Answer Status:** `FAIL`

**Reason:**
Retrieval failure: Dense vector retrieval + reranking failed to retrieve the relevant gift disclosure chunk from employee_conduct_policy.pdf. Consequently, the LLM responded with 'I don't know based on the provided HR policy documents.'

---

### Q16 — What are the progressive steps in the company disciplinary process?

**Expected Answer:**
Progressive disciplinary process: Step 1: Verbal Warning (minor first-time). Step 2: Written Warning (repeated minor / first moderate). Step 3: Final Written Warning and Performance Improvement Plan (PIP). Step 4: Termination of employment (serious misconduct or repeated violations).

**Actual RAG Answer:**
> According to the context, the progressive steps in the company disciplinary process are:
> 
> 1. Verbal Warning - for minor first-time offences.
> 2. Written Warning - for repeated minor offences or a first moderate offence.
> 3. Final Written Warning and Performance Improvement Plan (PIP).
> 4. Termination of employment for serious misconduct or repeated policy violations.
> 
> These steps are outlined in the "Disciplinary Process" section of the employee_conduct_policy.pdf document, Chunk 8.

**Expected Source:** `employee_conduct_policy.pdf`

**Retrieved Source:** `employee_conduct_policy.pdf, notice_period_policy.pdf`

**Expected Facts / Keywords:**
- Step 1: Verbal Warning
- Step 2: Written Warning
- Step 3: Final Written Warning and Performance Improvement Plan (PIP)
- Step 4: Termination of employment

**Matched Facts:**
- Step 1: Verbal Warning
- Step 2: Written Warning
- Step 3: Final Written Warning and Performance Improvement Plan (PIP)
- Step 4: Termination of employment

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source employee_conduct_policy.pdf was retrieved. All 4 progressive disciplinary steps are fully listed with exact details.

---

### Q17 — What is the notice period for employee resignation across different grades?

**Expected Answer:**
Resignation notice periods: Grade 1-3: 30 days (1 month). Grade 4-6: 60 days (2 months). Grade 7-9: 90 days (3 months). Grade 10+: 90 days minimum, or as specified in employment contract.

**Actual RAG Answer:**
> According to the provided HR policy documents, specifically the "Notice Period Policy" (Chunk 2), the notice periods for employee resignation across different grades are:
> 
> * Grade 1-3 (Junior / Associate): 30 days (1 month)
> * Grade 4-6 (Senior / Lead): 60 days (2 months)
> * Grade 7-9 (Manager / Senior Manager): 90 days (3 months)
> * Grade 10 and above (Director / VP / C-Suite): 90 days minimum, or as specified in the employment contract.

**Expected Source:** `notice_period_policy.pdf`

**Retrieved Source:** `notice_period_policy.pdf, work_from_home_policy.pdf`

**Expected Facts / Keywords:**
- Grade 1-3: 30 days (1 month)
- Grade 4-6: 60 days (2 months)
- Grade 7-9: 90 days (3 months)
- Grade 10+: 90 days minimum / contract term

**Matched Facts:**
- Grade 1-3: 30 days (1 month)
- Grade 4-6: 60 days (2 months)
- Grade 7-9: 90 days (3 months)
- Grade 10+: 90 days minimum / contract term

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source notice_period_policy.pdf was retrieved. The grade-wise notice period breakdown is 100% complete and accurate.

---

### Q18 — How is the notice period buyout amount calculated for early exit?

**Expected Answer:**
Notice period buyout amount is calculated as: (Basic Salary / 30) x Number of days not served. Requires written request to HR and approvals from Department Head and HR Director.

**Actual RAG Answer:**
> According to the provided HR policy documents, the notice period buyout amount is calculated as: (Basic Salary / 30) x Number of days not served.

**Expected Source:** `notice_period_policy.pdf`

**Retrieved Source:** `notice_period_policy.pdf, attendance_policy.pdf`

**Expected Facts / Keywords:**
- Formula: (Basic Salary / 30) x Number of days not served

**Matched Facts:**
- Formula: (Basic Salary / 30) x Number of days not served

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source notice_period_policy.pdf was retrieved. The exact mathematical buyout formula is provided accurately.

---

### Q19 — What is the timeline for processing the Full and Final settlement after leaving?

**Expected Answer:**
Full and Final (F&F) settlement is processed within 45 working days of the last working day, subject to completion of exit formalities and knowledge transfer.

**Actual RAG Answer:**
> According to the context, the Full and Final settlement will be processed within 45 working days of the last working day, subject to completion of all exit formalities. This information can be found in the notice_period_policy.pdf, Chunk 8.

**Expected Source:** `notice_period_policy.pdf`

**Retrieved Source:** `notice_period_policy.pdf, employee_conduct_policy.pdf`

**Expected Facts / Keywords:**
- Timeline: Within 45 working days of the last working day
- Condition: Completion of all exit formalities

**Matched Facts:**
- Timeline: Within 45 working days of the last working day
- Condition: Completion of all exit formalities

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source notice_period_policy.pdf was retrieved. Settlement timeline (45 working days) and key condition (exit formalities) are accurate.

---

### Q20 — How many paid sick leave days are employees entitled to per year and can unused sick leave be carried over?

**Expected Answer:**
Entitled to 12 days of paid sick leave per calendar year. Unused sick leave cannot be carried over or encashed.

**Actual RAG Answer:**
> According to the context, employees are entitled to 12 days of paid sick leave per calendar year. Unused sick leave cannot be carried over or encashed.

**Expected Source:** `leave_policy.pdf`

**Retrieved Source:** `leave_policy.pdf, work_from_home_policy.pdf, working_hours_policy.pdf`

**Expected Facts / Keywords:**
- 12 days of paid sick leave per calendar year
- Unused sick leave cannot be carried over or encashed

**Matched Facts:**
- 12 days of paid sick leave per calendar year
- Unused sick leave cannot be carried over or encashed

**Missing / Incorrect Facts:**
- None

**Retrieval Status:** `PASS`
**Answer Status:** `PASS`

**Reason:**
Expected source leave_policy.pdf was retrieved. Both annual entitlement (12 days) and carry-over/encashment prohibition are answered accurately.

---

## Step 2 → Step 3 Summary

- **Total Questions Evaluated:** 20
- **Retrieval PASS Count:** 19 (95.0%)
- **Retrieval FAIL Count:** 1 (5.0%)
- **Answer PASS Count:** 16 (80.0%)
- **Answer PARTIAL Count:** 3 (15.0%)
- **Answer FAIL Count:** 1 (5.0%)
- **Questions Requiring Investigation:** Q1, Q2, Q6, Q15
- **Questions Where Retrieval Succeeded but Answer Was Incomplete:** Q1, Q2, Q6
- **Questions Where Retrieval Itself Failed:** Q15

## Questions Requiring Investigation

The following table highlights the 4 questions that exhibited retrieval or answer generation deficiencies during the baseline evaluation. No fixes or code changes have been made at this stage.

| Priority Candidate | Q | Problem Type | Evidence |
|---|---|---|---|
| Candidate | Q15 | Retrieval Failure | Expected source `employee_conduct_policy.pdf` (gift disclosure threshold chunk) was not retrieved. Actual RAG answer was 'I don't know based on the provided HR policy documents.' |
| Candidate | Q1 | Incomplete Answer | Expected source `leave_policy.pdf` was retrieved, but actual answer omitted accrual rate (1.67 days/month) and 3-month eligibility waiting period. |
| Candidate | Q2 | Incomplete Answer | Expected source `leave_policy.pdf` was retrieved, but actual answer omitted application process (5 working days advance notice via HR portal; manager approval within 2 days). |
| Candidate | Q6 | Incomplete Answer | Expected source `attendance_policy.pdf` was retrieved, but actual answer omitted half-day absence rule after 9:30 AM, 3-late LWP penalty, and >5 quarter threshold. |

## Section 3 — Issue Investigation and Priority Grouping

This section presents the empirical investigation of the 4 candidate questions (Q15, Q1, Q2, Q6) that exhibited deficiencies during the Step 2 baseline evaluation and Step 3 comparative analysis. The issues are analyzed, classified, and grouped by root cause and priority.

### 3.1 Investigation Summary

| Question | Result | Problem Type | Root Cause Area | Priority | Evidence |
|---|---|---|---|---|---|
| Q15 | FAIL | Retrieval Failure | Distance Threshold Filtering (`DISTANCE_THRESHOLD = 1.2`) | **P1** | Gift disclosure chunk (`employee_conduct_policy.pdf` Chunk 4) vector distance was 1.5426 (>1.2 threshold), resulting in 0 retrieved context chunks and an 'I don't know' answer. |
| Q1 | PARTIAL | Answer Generation / Completeness | LLM Synthesis / Prompt Instruction Scope | **P2** | `leave_policy.pdf` Chunk 2 was retrieved and contained accrual rate (1.67 days/mo) and probation rule (3 mos), but LLM omitted these secondary facts in its final response. |
| Q2 | PARTIAL | Answer Generation / Completeness | LLM Synthesis / Prompt Instruction Scope | **P2** | `leave_policy.pdf` Chunk 2 was retrieved and contained advance notice (5 days via HR portal) and manager approval (2 days), but LLM focused solely on the 20 days figure. |
| Q6 | PARTIAL | Answer Generation / Completeness | LLM Synthesis / Prompt Instruction Scope | **P2** | `attendance_policy.pdf` Chunk 3 was retrieved and contained all late arrival tiers (half-day absence, 3-late LWP penalty, >5 quarter threshold), but LLM summarized only the first tier (9:11-9:30 AM). |

---

### 3.2 Detailed Investigation

#### Q15 — What is the threshold value for disclosing gifts received from clients or vendors?

- **Expected Answer:** Accepting gifts from vendors or clients above a value of INR 1,000 must be disclosed to HR.
- **Actual Answer:** *"I don't know based on the provided HR policy documents."*
- **Expected Source:** `employee_conduct_policy.pdf` (Section 4: Conflict of Interest, Chunk 4)
- **Retrieved Source/Chunk Information:** 0 chunks passed retrieval filtering (`citations: []`). Vector distance for Chunk 4 was `1.5426`.
- **Retrieval Result:** `FAIL` (Expected chunk filtered out before context assembly)
- **Evidence:** ChromaDB inspection confirms that `employee_conduct_policy.pdf` Chunk 4 contains the exact gift threshold policy (*"Accepting gifts from vendors or clients above a value of INR 1,000 must be disclosed to HR"*). Dense vector query for Q15 yielded a cosine distance of `1.5426`. Because `app/rag.py` enforces a strict distance threshold filter (`DISTANCE_THRESHOLD = 1.2`), Chunk 4 was discarded at Line 185. Consequently, 0 context chunks were passed to the generator.
- **Problem Classification:** `Retrieval Failure` (Distance Threshold Filtering Issue)
- **Priority:** `P1 (High Priority)`
- **Conclusion:** Q15 failed entirely because the distance threshold (`1.2`) aggressively discarded the relevant context chunk (distance `1.5426`). The LLM correctly refused to answer when given no context, confirming this is purely a retrieval pipeline filtering issue.

#### Q1 — How much annual leave do employees get?

- **Expected Answer:** Full-time employees receive 20 working days of annual leave per calendar year (pro-rata for part-time). Annual leave accrues at 1.67 days per month of service, with eligibility after 3 months of continuous employment.
- **Actual Answer:** *"According to the context, all full-time employees are entitled to 20 working days of annual leave per calendar year. Part-time employees receive annual leave on a pro-rata basis calculated against a 40-hour full-time week."*
- **Expected Source:** `leave_policy.pdf` (Section 2: Annual Leave, Chunk 2)
- **Retrieved Source/Chunk Information:** `leave_policy.pdf` Chunk 2 retrieved successfully (Distance < 1.2).
- **Retrieval Result:** `PASS` (Relevant chunk retrieved and provided to generator)
- **Evidence:** `leave_policy.pdf` Chunk 2 was passed to the LLM context. The chunk text explicitly contained: *"All full-time employees are entitled to 20 working days... New employees are eligible for annual leave after completing 3 months of continuous employment. Annual leave accrues at a rate of 1.67 days per month of service."* The LLM extracted the primary entitlement sentence but failed to summarize the accrual rate and probation waiting period.
- **Problem Classification:** `Answer Generation / Completeness` (LLM Synthesis Issue)
- **Priority:** `P2 (Medium Priority)`
- **Conclusion:** Retrieval succeeded completely. The omission of accrual rate and probation period is an answer generation completeness issue, where the LLM summarized the lead fact but stopped short of synthesizing secondary conditions present in the context.

#### Q2 — How many days off can I take for vacation?

- **Expected Answer:** Full-time employees can take up to 20 working days off for vacation per calendar year. Applications must be submitted via the HR portal at least 5 working days in advance and require manager approval within 2 working days.
- **Actual Answer:** *"According to the context from the leave_policy.pdf, Chunk 2, all full-time employees are entitled to 20 working days of annual leave per calendar year. Therefore, you can take 20 days off for vacation."*
- **Expected Source:** `leave_policy.pdf` (Section 2: Annual Leave, Chunk 2)
- **Retrieved Source/Chunk Information:** `leave_policy.pdf` Chunk 2 retrieved successfully.
- **Retrieval Result:** `PASS` (Relevant chunk retrieved and provided to generator)
- **Evidence:** The retrieved context Chunk 2 explicitly included procedural rules: *"Annual leave must be applied at least 5 working days in advance through the HR portal. The direct manager must approve leave requests within 2 working days of submission."* The LLM answered the direct numerical question (20 days) but omitted the procedural application requirements.
- **Problem Classification:** `Answer Generation / Completeness` (LLM Synthesis Issue)
- **Priority:** `P2 (Medium Priority)`
- **Conclusion:** Retrieval succeeded. The issue is strictly answer-generation completeness, as the LLM answered the literal question without including procedural context available in the prompt context.

#### Q6 — What happens if I am late to the office?

- **Expected Answer:** Arrival between 9:11-9:30 AM is a recorded late arrival. Arrival after 9:30 AM is a half-day absence. 3 late arrivals in a month result in 1 day Leave Without Pay (LWP). More than 5 late arrivals in a quarter trigger a formal performance discussion.
- **Actual Answer:** *"According to the provided HR policy documents, if you arrive between 9:11 AM and 9:30 AM, it constitutes a late arrival and will be recorded."*
- **Expected Source:** `attendance_policy.pdf` (Section 3: Punctuality Requirements, Chunk 3)
- **Retrieved Source/Chunk Information:** `attendance_policy.pdf` Chunk 3 retrieved successfully.
- **Retrieval Result:** `PASS` (Relevant chunk retrieved and provided to generator)
- **Evidence:** `attendance_policy.pdf` Chunk 3 contained the full 4-tier late policy in a single block: *"Arriving between 9:11 AM and 9:30 AM constitutes a late arrival... Arriving after 9:30 AM constitutes a half-day absence... Three recorded late arrivals... will result in one day of LWP... Repeated late arrivals (more than 5 in a quarter) may trigger a formal performance discussion."* The LLM extracted only the first sentence (Tier 1) and stopped generating.
- **Problem Classification:** `Answer Generation / Completeness` (LLM Synthesis Issue)
- **Priority:** `P2 (Medium Priority)`
- **Conclusion:** Retrieval succeeded. The LLM provided a truncated summary of a multi-clause policy rule present in the context chunk.

---

### 3.3 Issue Groups

The 4 candidate questions fall into 2 distinct issue groups based on empirical evidence:

| Group | Questions | Issue Type | Priority | Evidence / Root Cause Area |
|---|---|---|---|---|
| **Group 1** | Q15 | Retrieval Failure | **P1 (High)** | Distance threshold filtering (`DISTANCE_THRESHOLD = 1.2`) in `app/rag.py` discarded Chunk 4 (distance `1.5426`), preventing context from reaching the generator. |
| **Group 2** | Q1, Q2, Q6 | Answer Completeness | **P2 (Medium)** | Retrieval succeeded and context contained all required facts, but LLM generation prompt/synthesis generated incomplete summaries. |

---

### 3.4 Priority Ranking

| Priority | Group | Questions | Reason | Potential Future Investigation (Hypothesis Only) |
|---|---|---|---|---|
| **P1 (High)** | Group 1 | Q15 | System is completely unable to answer the question because zero evidence reaches the generator. | Tune distance threshold, evaluate hybrid search, or refine query expansion/re-ranking. |
| **P2 (Medium)** | Group 2 | Q1, Q2, Q6 | System retrieves relevant evidence and provides generally correct core answers, but omits secondary conditions and multi-clause details. | Enhance system prompt generation instructions (e.g., explicit instruction to include all eligibility criteria, procedural steps, and penalties). |

---

### 3.5 Step 4 Conclusion

- **Total Questions Evaluated:** 20
- **Retrieval Failures:** 1 (Q15)
- **Partial / Incomplete Answers:** 3 (Q1, Q2, Q6)
- **Questions Requiring Investigation:** 4
- **Grouped Issue Count:** 2 distinct groups (Group 1: Retrieval Filtering; Group 2: Answer Completeness)
- **Highest-Priority Issue:** **P1 (Q15 Retrieval Failure due to `DISTANCE_THRESHOLD = 1.2` filtering)**
- **RAG Code Modification Status:** **NO RAG pipeline code was modified** (`app/rag.py`, retrieval parameters, embeddings, chunking, thresholds, and prompts remain completely unchanged).