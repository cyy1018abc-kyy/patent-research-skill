"""Feature × candidate × evidence coverage matrix (blueprint D-02).

Every cell is either explicitly supported (candidate id + kernel evidence ref +
raw artifact hash) or explicitly empty — there is no "probably supported" state
(interface rule 6 discipline carried into WP-D).
"""

from __future__ import annotations

from typing import Any

from patent_intel.contracts import EvidenceProjection

__all__ = ["build_coverage_matrix", "CoverageMatrix"]

_OWNER = "WP-D"


def build_coverage_matrix(
    features: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    projections: list[EvidenceProjection],
) -> "CoverageMatrix":
    """Assemble the matrix from kernel candidate records + projections.

    Cell values:
    * ``{"status": "supported", "relation": …, "anchor": …}`` — projection with anchor;
    * ``{"status": "linked", "relation": …}`` — structural link, no verified anchor;
    * ``{"status": "no_evidence"}`` — explicitly empty (never silently blank).
    """
    proj_index: dict[tuple[str, str], list[EvidenceProjection]] = {}
    for proj in projections:
        proj_index.setdefault((proj.feature_id, proj.candidate_id), []).append(proj)

    cand_ids = [str(c.get("id") or "") for c in candidates if c.get("id")]
    rows: list[dict[str, Any]] = []
    for feature in features:
        fid = str(feature.get("feature_id"))
        cells: dict[str, dict[str, Any]] = {}
        for cand_id in cand_ids:
            projs = proj_index.get((fid, cand_id), [])
            if not projs:
                cells[cand_id] = {"status": "no_evidence"}
                continue
            best = projs[0]
            if best.anchor:
                cells[cand_id] = {
                    "status": "supported",
                    "relation": best.relation,
                    "raw_sha256": best.anchor.get("raw_sha256"),
                    "source_document": best.anchor.get("source_document"),
                }
            else:
                cells[cand_id] = {"status": "linked", "relation": best.relation}
        rows.append({"feature_id": fid, "statement": feature.get("statement"), "cells": cells})

    supported = sum(1 for row in rows for cell in row["cells"].values() if cell["status"] == "supported")
    total = sum(len(row["cells"]) for row in rows)
    return CoverageMatrix(rows=rows, coverage_ratio=(supported / total) if total else 0.0)


class CoverageMatrix:
    def __init__(self, rows: list[dict[str, Any]], coverage_ratio: float) -> None:
        self.rows = rows
        self.coverage_ratio = coverage_ratio

    def evidence_gaps(self) -> list[str]:
        """Features with zero supported cells — the honest 'needs more search' list."""
        return [
            row["feature_id"]
            for row in self.rows
            if all(cell["status"] != "supported" for cell in row["cells"].values())
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "coverage_ratio": round(self.coverage_ratio, 4),
            "note": "supported = kernel-reviewed projection with anchored evidence; "
            "linked = structural only; no_evidence is explicit, never blank",
        }
