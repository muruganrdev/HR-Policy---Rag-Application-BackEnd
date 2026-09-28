"""Exactly ten deterministic questions for the Agent/Workflow race evaluation."""

from __future__ import annotations

RACE_DATASET = [
    {
        "id": "Q1",
        "question": "For employee 001, how should the current annual leave balance be handled?",
        "employee_id": "001",
        "dependent": True,
        "expected": {"carryover_days": 2.0, "encashable_days": 2.0, "lapsed_days": 0.0},
    },
    {
        "id": "Q2",
        "question": "For employee 002, how many annual leave days can be carried over?",
        "employee_id": "002",
        "dependent": False,
        "expected": {"carryover_days": 4.0},
    },
    {
        "id": "Q3",
        "question": "For employee 003, how many days can be carried over and encashed?",
        "employee_id": "003",
        "dependent": False,
        "expected": {"carryover_days": 10.0, "encashable_days": 5.0},
    },
    {
        "id": "Q4",
        "question": "For employee 004, what portion of the annual leave balance lapses?",
        "employee_id": "004",
        "dependent": True,
        "expected": {"lapsed_days": 2.0},
    },
    {
        "id": "Q5",
        "question": "For employee 005, give the full annual leave disposition.",
        "employee_id": "005",
        "dependent": True,
        "expected": {"carryover_days": 10.0, "encashable_days": 5.0, "lapsed_days": 10.0},
    },
    {
        "id": "Q6",
        "question": "For employee 006, can the entire annual leave balance be carried over?",
        "employee_id": "006",
        "dependent": False,
        "expected": {"carryover_days": 5.0, "lapsed_days": 0.0},
    },
    {
        "id": "Q7",
        "question": "For employee 004, what is the maximum number of days that may be encashed?",
        "employee_id": "004",
        "dependent": False,
        "expected": {"encashable_days": 5.0},
    },
    {
        "id": "Q8",
        "question": "For employee 005, how many unused annual leave days lapse?",
        "employee_id": "005",
        "dependent": False,
        "expected": {"lapsed_days": 10.0},
    },
    {
        "id": "Q9",
        "question": "For employee 001, does any annual leave balance lapse?",
        "employee_id": "001",
        "dependent": False,
        "expected": {"lapsed_days": 0.0},
    },
    {
        "id": "Q10",
        "question": "For employee 006, report the annual leave carry-over, encashment, and lapse amounts.",
        "employee_id": "006",
        "dependent": False,
        "expected": {"carryover_days": 5.0, "encashable_days": 5.0, "lapsed_days": 0.0},
    },
]

assert len(RACE_DATASET) == 10
