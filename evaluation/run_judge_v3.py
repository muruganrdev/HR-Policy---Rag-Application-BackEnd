"""Summary formatter for the V3 judge report."""

from __future__ import annotations

from collections import OrderedDict


def build_summary_lines(
    *,
    total: int,
    agreement_count: int,
    disagreement_ids: list[str],
    mode_counts: dict[str, int],
    mode_agreements: dict[str, int],
    mode_disagreements: dict[str, int],
) -> list[str]:
    """Build the human-readable V3 summary used by the judge tests."""
    lines = [
        "## Judge V3 Summary",
        f"Total cases: {total}",
        f"Agreements: {agreement_count}/{total}",
        "",
        "## Disagreement IDs",
        ", ".join(disagreement_ids) if disagreement_ids else "None",
        "",
        "## Mode Summary",
    ]

    for mode, cases in OrderedDict(sorted(mode_counts.items())).items():
        agreement = mode_agreements.get(mode, 0)
        disagreement = mode_disagreements.get(mode, 0)
        agreement_pct = (agreement / cases * 100.0) if cases else 0.0
        lines.append(
            f"{mode}: cases={cases}, agreements={agreement}, disagreements={disagreement}, "
            f"agreement_pct={agreement_pct:.2f}%"
        )

    return lines
