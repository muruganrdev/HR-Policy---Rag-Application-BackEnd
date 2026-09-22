import pytest

from evaluation.assertions import (
    assert_handbook_version_citation,
    assert_notice_period_numeric,
    assert_out_of_jurisdiction_refusal,
    assert_policy_section_reference,
)


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Section 2 (Annual Leave (Vacation Leave)) covers the entitlement.", True),
        ("Section 5 (Overtime) explains the rate.", True),
    ],
)
def test_policy_section_reference_valid(answer, expected):
    result = assert_policy_section_reference(answer)
    assert result["passed"] is expected


@pytest.mark.parametrize(
    "answer",
    [
        "The policy does not specify a section reference.",
        "Section 99 is not in the HR policy documents.",
    ],
)
def test_policy_section_reference_invalid(answer):
    result = assert_policy_section_reference(answer)
    assert result["passed"] is False


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("The handbook version is Version: 1.0.", True),
        ("Version 1.0 is cited here.", True),
    ],
)
def test_handbook_version_valid(answer, expected):
    result = assert_handbook_version_citation(answer)
    assert result["passed"] is expected


@pytest.mark.parametrize(
    "answer",
    [
        "The handbook version is missing.",
        "Version 2.0 is cited here.",
    ],
)
def test_handbook_version_invalid(answer):
    result = assert_handbook_version_citation(answer)
    assert result["passed"] is False


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Grade 4–6 has a notice period of 60 days.", True),
        ("Grade 1–3 notice period is 30 days.", True),
    ],
)
def test_notice_period_numeric_valid(answer, expected):
    result = assert_notice_period_numeric(answer)
    assert result["passed"] is expected


@pytest.mark.parametrize(
    "answer",
    [
        "Notice period varies by grade.",
        "The notice period is different for different employees.",
    ],
)
def test_notice_period_numeric_invalid(answer):
    result = assert_notice_period_numeric(answer)
    assert result["passed"] is False


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("I don't know based on the provided HR policy documents.", True),
        ("This is not found in the provided HR policy documents.", True),
    ],
)
def test_refusal_valid(answer, expected):
    result = assert_out_of_jurisdiction_refusal(answer)
    assert result["passed"] is expected


@pytest.mark.parametrize(
    "answer",
    [
        "Employees are entitled to 20 working days of annual leave per calendar year.",
        "The company provides 12 days of sick leave per year.",
    ],
)
def test_refusal_invalid(answer):
    result = assert_out_of_jurisdiction_refusal(answer)
    assert result["passed"] is False
