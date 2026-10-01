from evaluation.trajectory_evaluator import (
    _argument_validity_for_result,
    _step_efficiency,
    _validate_tool_arguments,
    calculate_task_cost,
    compare_tool_sequences,
    evaluate_case,
    extract_latency,
    find_outcome_trajectory_gaps,
    summarize_metrics,
    _print_report,
)
from evaluation.trajectory_dataset import TRAJECTORY_DATASET


def test_official_dataset_has_ten_cases_with_expected_sequences_and_arguments():
    assert len(TRAJECTORY_DATASET) == 10
    assert all(
        case.get("question")
        and case.get("expected_answer_contains")
        and case.get("expected_tool_sequences")
        and case.get("expected_arguments")
        for case in TRAJECTORY_DATASET
    )
    assert TRAJECTORY_DATASET[6]["expected_tool_sequences"] == [
        ["get_employee_data", "lookup_annual_leave_policy"],
        ["lookup_annual_leave_policy", "get_employee_data"],
    ]


def test_exact_expected_sequence_matches():
    comparison = compare_tool_sequences(
        ["get_employee_data", "lookup_annual_leave_policy"],
        ["get_employee_data", "lookup_annual_leave_policy"],
    )

    assert comparison["trajectory_correct"] is True
    assert comparison["tool_choice_accuracy"] == 1.0


def test_wrong_tool_is_detected():
    comparison = compare_tool_sequences(
        ["get_employee_data"], ["get_department_employees"]
    )

    assert comparison["trajectory_correct"] is False
    assert comparison["tool_choice_accuracy"] == 0.0


def test_repeated_tool_is_detected_and_reduces_accuracy():
    comparison = compare_tool_sequences(
        ["get_employee_data", "lookup_annual_leave_policy"],
        ["get_employee_data", "get_employee_data", "lookup_annual_leave_policy"],
    )

    assert comparison["trajectory_correct"] is False
    assert comparison["tool_choice_accuracy"] == 1 / 3


def test_missing_tool_is_detected():
    comparison = compare_tool_sequences(
        ["get_employee_data", "lookup_annual_leave_policy"], ["get_employee_data"]
    )

    assert comparison["trajectory_correct"] is False
    assert comparison["tool_choice_accuracy"] == 0.5


def test_duplicate_attempt_in_existing_agent_steps_is_included():
    from evaluation.trajectory_evaluator import actual_tool_sequence

    result = {
        "steps": [
            {"phase": "tool", "tool": "get_employee_data"},
            {
                "phase": "observation",
                "tool": "get_employee_data",
                "observation": {"status": "duplicate"},
            },
        ]
    }

    assert actual_tool_sequence(result) == ["get_employee_data", "get_employee_data"]


def test_duplicate_attempt_logged_only_in_trace_is_included():
    from evaluation.trajectory_evaluator import actual_tool_sequence

    result = {
        "steps": [
            {
                "phase": "tool",
                "tool": "get_employee_data",
                "arguments": {"employee_id": "003"},
                "observation": {"status": "success", "result": {}},
            }
        ],
        "trace": (
            'Action: get_employee_data\nArguments: {"employee_id": "003"}\n'
            'Duplicate tool call prevented: get_employee_data with arguments '
            '{"employee_id": "003"}.'
        ),
    }

    assert actual_tool_sequence(result) == ["get_employee_data", "get_employee_data"]
    validity = _argument_validity_for_result(result)
    assert validity["total_arguments"] == 2


def test_outcome_trajectory_gap_is_reported():
    case = {
        "id": "W8Q1",
        "question": "Employee lookup",
        "expected_tools": ["get_employee_data", "lookup_annual_leave_policy"],
        "expected_answer_contains": ["840,000"],
    }
    record = evaluate_case(
        case,
        {
            "answer": "Neha Iyer's annual salary is 840,000.",
            "steps": [{"phase": "tool", "tool": "get_employee_data"}],
            "iteration_count": 1,
            "elapsed_seconds": 2.5,
            "tokens_used": 1000,
            "estimated_cost": 0.001,
            "termination_reason": None,
        },
    )

    assert record["answer_correct"] is True
    assert record["trajectory_correct"] is False
    gaps = find_outcome_trajectory_gaps([record])
    assert gaps == [record]


def test_controlled_fixture_detects_outcome_pass_with_wrong_trajectory():
    case = {
        "id": "CONTROLLED-GAP-FIXTURE",
        "question": "What is Neha Iyer's annual salary?",
        "expected_tool_sequences": [["get_employee_data"]],
        "expected_arguments": {
            "get_employee_data": {"employee_name": "Neha Iyer"}
        },
        "expected_answer_contains": ["Neha Iyer", "840,000"],
    }
    result_fixture = {
        "answer": "Neha Iyer's annual salary is 840,000.",
        "steps": [
            {
                "phase": "tool",
                "tool": "get_department_employees",
                "arguments": {"department_name": "Engineering"},
                "observation": {"status": "success", "result": {}},
            }
        ],
    }

    record = evaluate_case(case, result_fixture)

    assert record["answer_correct"] is True
    assert record["trajectory_correct"] is False
    assert find_outcome_trajectory_gaps([record]) == [record]


def test_cost_is_calculated_from_existing_token_count():
    assert calculate_task_cost({"tokens_used": 2500}, cost_per_1k_tokens=0.002) == 0.005


def test_latency_is_extracted_from_existing_elapsed_seconds():
    assert extract_latency({"elapsed_seconds": 12.75}) == 12.75
    assert extract_latency({}) is None


def test_argument_validity_distinguishes_format_from_live_grounding():
    checked = _validate_tool_arguments("get_employee_data", {"employee_id": "999"})

    assert checked["syntactic_valid"] is True
    assert checked["grounded_valid"] is False
    assert checked["valid"] is False


def test_argument_validity_uses_live_department_and_manager_values():
    assert _validate_tool_arguments(
        "get_department_employees", {"department_name": "Product"}
    )["valid"] is True
    assert _validate_tool_arguments(
        "get_employees_by_manager", {"manager_name": "Deepak Sharma"}
    )["valid"] is True


def test_step_efficiency_uses_the_best_matching_alternate_path():
    case = {
        "expected_tool_sequences": [
            ["get_employee_data", "lookup_annual_leave_policy"],
            [
                "get_employee_data",
                "lookup_annual_leave_policy",
                "calculate_annual_leave_disposition",
            ],
        ]
    }

    assert _step_efficiency(
        case,
        [
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        ],
        [
            "get_employee_data",
            "lookup_annual_leave_policy",
            "calculate_annual_leave_disposition",
        ],
    ) == 1.0


def test_argument_validity_counts_duplicate_attempts():
    validity = _argument_validity_for_result(
        {
            "steps": [
                {
                    "phase": "tool",
                    "tool": "get_employee_data",
                    "arguments": {"employee_id": "003"},
                    "observation": {"status": "success", "result": {}},
                },
                {
                    "phase": "observation",
                    "tool": "get_employee_data",
                    "arguments": {"employee_id": "003"},
                    "observation": {"status": "duplicate"},
                },
            ]
        }
    )

    assert validity["total_arguments"] == 2
    assert validity["valid_arguments"] == 2


def test_report_prints_cost_percentiles_and_maximum(capsys):
    records = [
        {
            "id": str(index),
            "question": "Cost report fixture",
            "actual_tools": [],
            "answer_correct": True,
            "trajectory_correct": True,
            "tool_choice_slots": 1,
            "matched_tool_choices": 1,
            "argument_validity": {"valid_arguments": 1, "total_arguments": 1},
            "step_efficiency": 1.0,
            "estimated_cost": cost,
            "latency": None,
            "tokens": 10,
            "termination_reason": None,
        }
        for index, cost in enumerate((0.001, 0.003), start=1)
    ]
    metrics = summarize_metrics(records)
    metrics["outcome_trajectory_gap"] = -0.2
    report = {
        "results": records,
        "metrics": metrics,
        "outcome_trajectory_gaps": [],
        "failure_mode_counts": {},
    }

    _print_report(report)

    output = capsys.readouterr().out
    assert "Cost p50:                 $0.002000" in output
    assert "Cost max:                 $0.003000" in output
    assert "Live outcome-vs-trajectory gap: -20.00 percentage points." in output