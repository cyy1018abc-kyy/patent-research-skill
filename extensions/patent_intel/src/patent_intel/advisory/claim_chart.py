"""Claim chart drafting (blueprint D-04): claim × candidate scaffold from kernel
review states — never an automatic infringement/novelty analysis.

Honesty rules (UT-E02):
* a cell shows what the *kernel review* recorded about that candidate
  (novelty_check), plus the projection's anchored evidence if available;
* "all core features appear across candidates" is reported as a **combination
  hypothesis** — it must never be phrased or exported as "single document covers
  everything" when no single candidate does (novelty vs inventive-step logic is a
  human/legal judgement the extension does not make);
* no claim about grant prospects is ever emitted.
"""

from __future__ import annotations

from typing import Any

from patent_intel.documents.schema import StructuredPatentDocument
from patent_intel.evidence.coverage_matrix import CoverageMatrix

__all__ = ["build_claim_chart", "ClaimChart"]

_OWNER = "WP-D"

_NOVELTY_LABELS = {
    "blocking": "kernel: blocking (single-doc novelty obstacle per kernel review)",
    "covered": "kernel: covered (claim-level per kernel review)",
    "partial": "kernel: partial",
    "untouched": "kernel: unreviewed",
}


def build_claim_chart(
    doc: StructuredPatentDocument,
    matrix: CoverageMatrix,
    candidates: list[dict[str, Any]],
) -> "ClaimChart":
    """Scaffold a claim chart for every parsed claim × every candidate column."""
    by_candidate = {str(c.get("id") or ""): c for c in candidates}
    rows: list[dict[str, Any]] = []
    for claim in doc.claims:
        cells: dict[str, dict[str, Any]] = {}
        for cand_id, cand in by_candidate.items():
            kernel_state = str(cand.get("novelty_check") or "untouched")
            anchored = any(
                row["cells"].get(cand_id, {}).get("status") == "supported"
                for row in matrix.rows
            )
            cells[cand_id] = {
                "kernel_state": kernel_state,
                "kernel_label": _NOVELTY_LABELS.get(kernel_state, kernel_state),
                "anchored_evidence": anchored,
                "disclosure_detail": "TBD — requires human feature-by-feature mapping",
            }
        rows.append({"claim_number": claim.number, "claim_text": claim.text[:120], "cells": cells})

    # combination hypothesis: no single 'blocking' candidate, but ≥2 partial ones
    single_doc_novelty = [
        cand_id for cand_id, cand in by_candidate.items()
        if cand.get("novelty_check") == "blocking"
    ]
    partial_docs = [
        cand_id for cand_id, cand in by_candidate.items()
        if cand.get("novelty_check") == "partial"
    ]
    combination_hypothesis = (not single_doc_novelty) and len(partial_docs) >= 2
    return ClaimChart(
        rows=rows,
        single_doc_novelty_candidates=single_doc_novelty,
        combination_hypothesis=combination_hypothesis,
        partial_candidates=partial_docs,
    )


class ClaimChart:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        single_doc_novelty_candidates: list[str],
        combination_hypothesis: bool,
        partial_candidates: list[str],
    ) -> None:
        self.rows = rows
        self.single_doc_novelty_candidates = single_doc_novelty_candidates
        self.combination_hypothesis = combination_hypothesis
        self.partial_candidates = partial_candidates

    def to_markdown(self) -> str:
        cand_ids = sorted({c for row in self.rows for c in row["cells"]}) or ["(no candidates)"]
        header = "| claim | " + " | ".join(cand_ids) + " |"
        sep = "|---" * (len(cand_ids) + 1) + "|"
        lines = [header, sep]
        for row in self.rows:
            cells = []
            for cand_id in cand_ids:
                cell = row["cells"].get(cand_id)
                cells.append("TBD" if cell is None else str(cell["kernel_state"]))
            lines.append(f"| {row['claim_number']} | " + " | ".join(cells) + " |")
        return "\n".join(lines)

    def describe(self) -> dict[str, Any]:
        return {
            "claim_count": len(self.rows),
            "single_doc_novelty_candidates": self.single_doc_novelty_candidates,
            "combination_hypothesis": self.combination_hypothesis,
            "partial_candidates": self.partial_candidates,
            "caveat": (
                "combination_hypothesis is a HINT that several partial documents might "
                "deserve a combined human analysis — it is not an inventive-step or "
                "novelty conclusion, and it never implies grant prospects"
            ),
        }
