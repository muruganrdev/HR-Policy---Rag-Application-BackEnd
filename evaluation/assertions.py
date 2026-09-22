"""Deterministic assertion helpers for Week 6 evaluation checks."""

from __future__ import annotations

import re
from typing import Iterable

VALID_SECTION_TITLES = {
    "annual leave (vacation leave)",
    "maternity and paternity leave",
    "punctuality requirements",
    "habitual absenteeism",
    "wfh entitlement",
    "eligibility",
    "approval process",
    "standard working hours",
    "shift work",
    "overtime",
    "workplace harassment and discrimination",
    "conflict of interest",
    "confidentiality and data protection",
    "knowledge transfer obligations",
    "employee notice period (resignation)",
}

VALID_SECTION_NUMBERS = {2, 3, 4, 5, 6}

EXPECTED_HANDBOOK_VERSION = "1.0"


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _extract_section_references(answer: str) -> list[str]:
    refs: list[str] = []
    for pattern in (
        r"section\s*([0-9]+)",
        r"(?<!\w)([0-9]+)\.\s*[A-Za-z]",
    ):
        for match in re.finditer(pattern, answer, flags=re.IGNORECASE):
            refs.append(match.group(1))
    return refs


def assert_policy_section_reference(answer: str, valid_sections: Iterable[str] | None = None) -> dict:
    """Ensure a policy section is present and is one of the known valid HR sections."""
    if answer is None:
        return {"passed": False, "reason": "No answer provided"}

    valid_section_set = set(valid_sections) if valid_sections is not None else VALID_SECTION_TITLES
    normalized = _normalize_text(answer)

    direct_title_match = any(title in normalized for title in valid_section_set)
    extracted_refs = _extract_section_references(answer)
    numeric_section_match = any(int(ref) in VALID_SECTION_NUMBERS for ref in extracted_refs)

    if direct_title_match or numeric_section_match:
        return {"passed": True, "reason": "Valid policy section reference found"}

    if extracted_refs:
        return {"passed": False, "reason": "Invalid policy section reference"}

    return {"passed": False, "reason": "No policy section reference found"}


def assert_handbook_version_citation(answer: str, expected_version: str = EXPECTED_HANDBOOK_VERSION) -> dict:
    """Check whether the answer explicitly cites the repository version value."""
    if not answer:
        return {"passed": False, "reason": "No answer provided"}

    normalized = answer.lower()
    matches = re.findall(r"(?:version|ver\.?|v)\s*[:=]?\s*['\"]?(v?\d+\.\d+)['\"]?", answer, flags=re.IGNORECASE)

    if matches:
        cited_version = matches[0].lstrip("v")
        if cited_version == expected_version:
            return {"passed": True, "reason": "Handbook version citation matches repository version"}
        return {"passed": False, "reason": f"Incorrect version cited: {cited_version}"}

    if re.search(r"\b\d+\.\d+\b", normalized):
        return {"passed": False, "reason": "Version present but does not match the repository version"}

    return {"passed": False, "reason": "Handbook version citation missing"}


def assert_notice_period_numeric(answer: str) -> dict:
    """Check that a notice-period answer contains a numeric figure, without judging semantic correctness."""
    if not answer:
        return {"passed": False, "reason": "No answer provided"}

    normalized = answer.lower()
    if "notice" not in normalized:
        return {"passed": False, "reason": "No notice-period language found"}

    numeric_pattern = re.compile(r"\b\d+\s*(?:day|days)\b|\b\d+\s*-\s*(?:day|days)\b", re.IGNORECASE)
    if numeric_pattern.search(answer):
        return {"passed": True, "reason": "Numeric notice-period figure found"}

    return {"passed": False, "reason": "No numeric notice-period figure found"}


def assert_out_of_jurisdiction_refusal(answer: str) -> dict:
    """Detect the repository's unsupported-policy refusal pattern using deterministic string matching."""
    if not answer:
        return {"passed": False, "reason": "No answer provided"}

    normalized = answer.lower()
    refusal_patterns = (
        "i don't know",
        "not found in the provided hr policy documents",
        "not specified in the policy",
        "not available in the hr documents",
        "not available in the provided hr policy documents",
        "not found in the hr policy documents",
    )

    if any(pattern in normalized for pattern in refusal_patterns):
        return {"passed": True, "reason": "Unsupported-policy refusal detected"}

    return {"passed": False, "reason": "No refusal pattern detected"}


__all__ = [
    "VALID_SECTION_TITLES",
    "EXPECTED_HANDBOOK_VERSION",
    "assert_policy_section_reference",
    "assert_handbook_version_citation",
    "assert_notice_period_numeric",
    "assert_out_of_jurisdiction_refusal",
]
