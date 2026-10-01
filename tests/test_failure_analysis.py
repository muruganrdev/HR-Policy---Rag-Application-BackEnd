from evaluation.failure_analysis import (
    build_failure_matrix,
    classify_case,
    classify_termination,
    detect_repeated_tools,
    find_outcome_trajectory_gaps,
)


def _case(expected_tools):
    return {"id": "FIXTURE", "question": "Fixture question", "expected_tools": expected_tools}


def test_classifies_wrong_tool_and_missing_tool():
    result = classify_case(
        _case(["get_employee_data", "lookup_annual_leave_policy"]),
        {"actual_tools": ["get_department_employees"], "answer_correct": False},
    )

    assert result["primary_failure_mode"] == "WRONG_TOOL"

    missing = classify_case(
        _case(["get_employee_data", "lookup_annual_leave_policy"]),
        {"actual_tools": ["get_employee_data"], "answer_correct": False},
    )
    assert missing["primary_failure_mode"] == "MISSING_TOOL"


def test_classifies_wrong_tool_order():
    result = classify_case(
        _case(["get_employee_data", "lookup_annual_leave_policy"]),
        {
            "actual_tools": ["lookup_annual_leave_policy", "get_employee_data"],
            "answer_correct": False,
        },
    )

    assert result["primary_failure_mode"] == "WRONG_ORDER"


def test_classifies_wrong_arguments_against_question_fixture():
    steps = [
        {
            "phase": "tool",
            "tool": "get_employee_data",
            "arguments": {"employee_id": "004"},
            "observation": {"status": "success"},
        }
    ]
    result = classify_case(
        _case(["get_employee_data"]),
        {"actual_tools": ["get_employee_data"], "answer_correct": False},
        steps,
        expected_arguments=[{"employee_id": "005"}],
    )

    assert result["primary_failure_mode"] == "WRONG_ARGUMENT"


def test_loop_is_primary_and_budget_termination_is_secondary():
    repeated_steps = [
        {
            "phase": "tool",
            "tool": "get_employee_data",
            "arguments": {"employee_name": "Rahul Das"},
            "observation": {"status": "success"},
        },
        {
            "phase": "observation",
            "tool": "get_employee_data",
            "arguments": {"employee_name": "Rahul Das"},
            "observation": {"status": "duplicate"},
        },
    ]
    result = classify_case(
        _case(["get_employee_data"]),
        {
            "actual_tools": ["get_employee_data", "get_employee_data"],
            "answer_correct": False,
            "termination_reason": "max_iterations",
        },
        repeated_steps,
    )

    assert result["primary_failure_mode"] == "TOOL_LOOP"
    assert result["secondary_failure_mode"] == "MAX_ITERATIONS"
    assert result["repeated_tool_analysis"]["identical_argument_repetitions"] == 1


def test_loop_is_detected_when_duplicate_exists_only_in_actual_sequence():
    result = classify_case(
        _case(["get_employee_data"]),
        {
            "actual_tools": ["get_employee_data", "get_employee_data"],
            "answer_correct": False,
        },
        [
            {
                "phase": "tool",
                "tool": "get_employee_data",
                "arguments": {"employee_id": "003"},
                "observation": {"status": "success"},
            }
        ],
    )

    assert result["primary_failure_mode"] == "TOOL_LOOP"
    assert result["repeated_tool_analysis"]["repeat_attempts"] == 1


def test_classifies_premature_final_and_tool_error():
    premature = classify_case(
        _case(["get_employee_data", "lookup_annual_leave_policy"]),
        {"actual_tools": ["get_employee_data"], "answer_correct": False},
        [{"phase": "final", "answer": "Final too early"}],
    )
    failed_tool = classify_case(
        _case(["get_employee_data"]),
        {"actual_tools": ["get_employee_data"], "answer_correct": False},
        [
            {
                "phase": "tool",
                "tool": "get_employee_data",
                "arguments": {"employee_id": "999"},
                "observation": {"status": "error", "error": "not found"},
            }
        ],
    )

    assert premature["primary_failure_mode"] == "PREMATURE_FINAL"
    assert failed_tool["primary_failure_mode"] == "TOOL_ERROR"


def test_classifies_correct_trajectory_with_wrong_answer():
    result = classify_case(
        _case(["get_department_employees"]),
        {
            "actual_tools": ["get_department_employees"],
            "answer_correct": False,
        },
    )

    assert result["primary_failure_mode"] == "FINAL_ANSWER_ERROR"


def test_termination_classification_includes_all_budget_reasons():
    assert classify_termination("wall_clock") == "WALL_CLOCK"
    assert classify_termination("max_iterations") == "MAX_ITERATIONS"
    assert classify_termination("max_tokens") == "MAX_TOKENS"
    assert classify_termination("max_cost") == "MAX_COST"
    assert classify_termination(None) is None


def test_detects_repeat_counts_and_identical_arguments():
    steps = [
        {"phase": "tool", "tool": "lookup_annual_leave_policy", "arguments": {"jurisdiction": "INDIA"}},
        {
            "phase": "observation",
            "tool": "lookup_annual_leave_policy",
            "arguments": {"jurisdiction": "INDIA"},
            "observation": {"status": "duplicate"},
        },
        {
            "phase": "observation",
            "tool": "lookup_annual_leave_policy",
            "arguments": {"jurisdiction": "INDIA"},
            "observation": {"status": "duplicate"},
        },
    ]

    analysis = detect_repeated_tools(steps)

    assert analysis["repeated_tool_counts"] == {"lookup_annual_leave_policy": 2}
    assert analysis["repeat_attempts"] == 2
    assert analysis["identical_argument_repetitions"] == 2


def test_detects_outcome_trajectory_gap():
    records = [
        {"answer_correct": True, "trajectory_correct": False},
        {"answer_correct": True, "trajectory_correct": True},
    ]

    assert find_outcome_trajectory_gaps(records) == [records[0]]


def test_generates_failure_matrix_rows():
    case = _case(["get_employee_data"])
    case_result = {
        "id": "FIXTURE",
        "actual_tools": ["get_employee_data"],
        "answer_correct": True,
        "trajectory_correct": True,
        "tool_choice_accuracy": 1.0,
        "termination_reason": None,
        "iterations": 1,
        "latency": 2.0,
        "tokens": 10,
        "estimated_cost": 0.00001,
    }

    rows = build_failure_matrix([case], [case_result])

    assert len(rows) == 1
    assert rows[0]["case_id"] == "FIXTURE"
    assert rows[0]["primary_failure_mode"] == "NONE"
    assert rows[0]["termination_reason"] == "none"
    assert rows[0]["expected_tools"] == rows[0]["actual_tools"]