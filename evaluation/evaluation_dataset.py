"""
Week 4 Evaluation Dataset for HR Policy RAG Application.

This dataset contains representative evaluation questions mapped to their
ground-truth source PDF documents and expected keywords for Hit-rate@3 evaluation.
"""

EVALUATION_DATASET = [
    # --- Leave Policy (leave_policy.pdf) ---
    {
        "id": 1,
        "question": "How much annual leave do employees get?",
        "expected_source": "leave_policy.pdf",
        "expected_keywords": ["annual leave", "20", "calendar year", "accrues"]
    },
    {
        "id": 2,
        "question": "How many days off can I take for vacation?",
        "expected_source": "leave_policy.pdf",
        "expected_keywords": ["annual leave", "20", "vacation"]
    },
    {
        "id": 3,
        "question": "How many days of unused annual leave can be carried over or encashed?",
        "expected_source": "leave_policy.pdf",
        "expected_keywords": ["carried over", "10 days", "encash", "5 days"]
    },
    {
        "id": 4,
        "question": "What is the paid maternity and paternity leave duration?",
        "expected_source": "leave_policy.pdf",
        "expected_keywords": ["maternity", "26 weeks", "paternity", "5 working days"]
    },

    # --- Attendance Policy (attendance_policy.pdf) ---
    {
        "id": 5,
        "question": "What is the grace period for arriving at work in the morning?",
        "expected_source": "attendance_policy.pdf",
        "expected_keywords": ["grace period", "10 minutes", "9:00 AM", "punctuality"]
    },
    {
        "id": 6,
        "question": "What happens if I am late to the office?",
        "expected_source": "attendance_policy.pdf",
        "expected_keywords": ["late arrival", "9:11 AM", "half-day absence", "LWP"]
    },
    {
        "id": 7,
        "question": "How is habitual absenteeism handled by HR?",
        "expected_source": "attendance_policy.pdf",
        "expected_keywords": ["habitual absent", "6 days", "verbal counselling", "written warning"]
    },

    # --- Work From Home Policy (work_from_home_policy.pdf) ---
    {
        "id": 8,
        "question": "Can I work from home and what is the weekly limit?",
        "expected_source": "work_from_home_policy.pdf",
        "expected_keywords": ["work from home", "2 days", "week", "Wednesday", "Friday"]
    },
    {
        "id": 9,
        "question": "What are the eligibility requirements for remote work?",
        "expected_source": "work_from_home_policy.pdf",
        "expected_keywords": ["6 months", "continuous employment", "10 Mbps", "eligibility"]
    },
    {
        "id": 10,
        "question": "How much advance notice is required to request a work from home day?",
        "expected_source": "work_from_home_policy.pdf",
        "expected_keywords": ["24 hours", "advance", "HR portal", "manager"]
    },

    # --- Working Hours Policy (working_hours_policy.pdf) ---
    {
        "id": 11,
        "question": "What are the core working hours and break timings?",
        "expected_source": "working_hours_policy.pdf",
        "expected_keywords": ["40 paid hours", "9:00 AM", "6:00 PM", "lunch break"]
    },
    {
        "id": 12,
        "question": "What is the shift allowance for employees working the night shift?",
        "expected_source": "working_hours_policy.pdf",
        "expected_keywords": ["night shift", "20%", "shift allowance", "10:00 PM"]
    },
    {
        "id": 13,
        "question": "How is overtime work compensated for non-exempt employees?",
        "expected_source": "working_hours_policy.pdf",
        "expected_keywords": ["overtime", "1.5x", "2.0x", "non-exempt"]
    },

    # --- Employee Conduct Policy (employee_conduct_policy.pdf) ---
    {
        "id": 14,
        "question": "How and within how many days should workplace harassment be reported?",
        "expected_source": "employee_conduct_policy.pdf",
        "expected_keywords": ["harassment", "Internal Complaints Committee", "ICC", "30 days"]
    },
    {
        "id": 15,
        "question": "What is the threshold value for disclosing gifts received from clients or vendors?",
        "expected_source": "employee_conduct_policy.pdf",
        "expected_keywords": ["gifts", "INR 1,000", "conflict of interest", "HR"]
    },
    {
        "id": 16,
        "question": "What are the progressive steps in the company disciplinary process?",
        "expected_source": "employee_conduct_policy.pdf",
        "expected_keywords": ["Verbal Warning", "Written Warning", "PIP", "Termination"]
    },

    # --- Notice Period Policy (notice_period_policy.pdf) ---
    {
        "id": 17,
        "question": "What is the notice period for employee resignation across different grades?",
        "expected_source": "notice_period_policy.pdf",
        "expected_keywords": ["Grade 1-3", "30 days", "Grade 4-6", "60 days", "Grade 7-9", "90 days"]
    },
    {
        "id": 18,
        "question": "How is the notice period buyout amount calculated for early exit?",
        "expected_source": "notice_period_policy.pdf",
        "expected_keywords": ["buyout", "Basic Salary", "30", "days not served"]
    },
    {
        "id": 19,
        "question": "What is the timeline for processing the Full and Final settlement after leaving?",
        "expected_source": "notice_period_policy.pdf",
        "expected_keywords": ["Full and Final", "F&F", "45 working days", "settlement"]
    }
]


if __name__ == "__main__":
    print(f"Total evaluation test questions: {len(EVALUATION_DATASET)}")
    for item in EVALUATION_DATASET:
        print(f"[{item['id']:02d}] {item['expected_source']:<28} -> {item['question']}")
