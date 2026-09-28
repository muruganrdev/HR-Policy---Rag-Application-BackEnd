from __future__ import annotations

import csv
from pathlib import Path

from evaluation.run_race import (
    _zero_lapse_present,
    evaluate_answer,
    p50,
    write_csv,
    write_summary,
)
from evaluation.race_dataset import RACE_DATASET


ROOT = Path(__file__).resolve().parents[1]


def test_dataset_has_ten_existing_employee_cases_and_dependencies():
    assert len(RACE_DATASET) == 10
    assert {case["employee_id"] for case in RACE_DATASET} <= {
        "001", "002", "003", "004", "005", "006"
    }
    assert sum(case["dependent"] for case in RACE_DATASET) >= 3


def test_deterministic_evaluator_accepts_paraphrased_facts():
    case = RACE_DATASET[4]
    result = {
        "answer": "Ten days can be carried forward, five days can be encashed, and ten days lapse.",
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is True


def test_deterministic_evaluator_rejects_budget_termination():
    case = RACE_DATASET[0]
    result = {
        "answer": "Two days can be carried over and encashed.",
        "terminated_by_budget": True,
    }
    assert evaluate_answer(case, result) is False


def test_p50_uses_median():
    assert p50([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert p50([1.0, 2.0, 3.0]) == 2.0


def test_csv_writer_writes_one_row_per_case(tmp_path, monkeypatch):
    import evaluation.run_race as runner

    path = tmp_path / "race.csv"
    monkeypatch.setattr(runner, "CSV_PATH", path)
    rows = [
        {"id": case["id"], "question": case["question"], "agent_pass": True}
        for case in RACE_DATASET
    ]
    write_csv(rows)

    with path.open(newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 10
    assert {row["id"] for row in written} == {case["id"] for case in RACE_DATASET}


def test_summary_contains_both_systems(tmp_path, monkeypatch):
    import evaluation.run_race as runner

    path = tmp_path / "summary.md"
    monkeypatch.setattr(runner, "SUMMARY_PATH", path)
    rows = [
        {
            "id": case["id"],
            "dependent": case["dependent"],
            "agent_pass": True,
            "workflow_pass": False,
            "agent_latency_seconds": 1.0,
            "workflow_latency_seconds": 2.0,
            "agent_tokens": 10,
            "workflow_tokens": 20,
            "agent_estimated_cost": 0.00001,
            "workflow_estimated_cost": 0.00002,
            "agent_terminated_by_budget": False,
        }
        for case in RACE_DATASET
    ]
    write_summary(rows)
    text = path.read_text(encoding="utf-8")
    assert "Agent" in text
    assert "Fixed Workflow" in text
    assert "Pass rate" in text
    assert "Q1" in text


# ---------------------------------------------------------------------------
# Focused zero-lapse evaluator tests
# ---------------------------------------------------------------------------

def test_zero_lapse_present_no_days_lapse():
    assert _zero_lapse_present("2 days can be carried over and no days lapse.") is True


def test_zero_lapse_present_does_not_lapse():
    assert _zero_lapse_present("The full balance does not lapse.") is True


def test_zero_lapse_present_no_annual_leave_balance_lapses():
    assert _zero_lapse_present("No annual leave balance lapses.") is True


def test_zero_lapse_present_zero_days_lapse():
    assert _zero_lapse_present("Zero days lapse.") is True


def test_zero_lapse_present_0_days_are_lapsed():
    assert _zero_lapse_present("0 days are lapsed.") is True


def test_zero_lapse_present_no_leave_expires():
    assert _zero_lapse_present("The employee has no leave that expires.") is True


def test_zero_lapse_present_no_balance_does_not_lapse():
    assert _zero_lapse_present("No, the balance does not lapse.") is True


def test_zero_lapse_present_doesnt_lapse():
    assert _zero_lapse_present("The remaining balance doesn't lapse.") is True


def test_zero_lapse_present_rejects_10_days_lapse():
    assert _zero_lapse_present("10 days lapse.") is False


def test_zero_lapse_present_rejects_2_days_lapse():
    assert _zero_lapse_present("2 days lapse.") is False


def test_zero_lapse_present_rejects_mixed_not_in_aside():
    assert _zero_lapse_present(
        "10 days lapse, but this does not affect encashment."
    ) is False


def test_zero_lapse_present_rejects_remaining_lapse():
    assert _zero_lapse_present(
        "5 days can be carried over, but the remaining 10 days lapse."
    ) is False


# --- evaluate_answer end-to-end: Q1 (lapsed_days == 0) ---

def test_evaluate_answer_q1_accepts_natural_no_lapse():
    case = RACE_DATASET[0]
    result = {
        "answer": (
            "Employee 001 can carry over 2 days and encash 2 days. "
            "No annual leave balance lapses."
        ),
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is True


def test_evaluate_answer_q1_accepts_does_not_lapse():
    case = RACE_DATASET[0]
    result = {
        "answer": (
            "Asha Rao can carry over 2 days and encash 2 days. "
            "The balance does not lapse."
        ),
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is True


# --- evaluate_answer end-to-end: Q6 (lapsed_days == 0) ---

def test_evaluate_answer_q6_accepts_carry_over_no_lapse():
    case = RACE_DATASET[5]
    result = {
        "answer": (
            "Yes, the entire annual leave balance of 5 days can be carried over. "
            "No days lapse."
        ),
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is True


# --- evaluate_answer end-to-end: Q9 (lapsed_days == 0 only) ---

def test_evaluate_answer_q9_accepts_does_not_lapse():
    case = RACE_DATASET[8]
    result = {
        "answer": "No, the annual leave balance does not lapse.",
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is True


def test_evaluate_answer_q9_accepts_no_balance_lapses():
    case = RACE_DATASET[8]
    result = {
        "answer": "No annual leave balance lapses for employee 001.",
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is True


# --- Regression: non-zero lapse cases must NOT be falsely passed ---

def test_evaluate_answer_q4_not_fooled_by_not():
    case = RACE_DATASET[3]
    result = {
        "answer": "The employee's leave does not lapse.",
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is False


def test_evaluate_answer_q8_non_zero_lapse_still_requires_number():
    case = RACE_DATASET[7]
    result = {
        "answer": "Some days lapse.",
        "terminated_by_budget": False,
    }
    assert evaluate_answer(case, result) is False
