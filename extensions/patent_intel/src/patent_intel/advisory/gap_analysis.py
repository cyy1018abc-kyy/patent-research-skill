"""Gap analysis (blueprint D-04): which features still lack anchored evidence.

Feeds WP-A (search more) and the human review queue; it never feeds a conclusion
that "no prior art exists for X" — absence of evidence in the searched sample is
exactly that.
"""

from __future__ import annotations

from typing import Any

from patent_intel.evidence.coverage_matrix import CoverageMatrix

__all__ = ["analyze_gaps", "GapReport"]

_OWNER = "WP-D"


def analyze_gaps(matrix: CoverageMatrix, features: list[dict[str, Any]]) -> "GapReport":
    by_id = {str(f.get("feature_id")): f for f in features}
    no_evidence: list[dict[str, str]] = []
    only_structural: list[dict[str, str]] = []
    supported: list[str] = []
    for row in matrix.rows:
        fid = str(row["feature_id"])
        statuses = {cell.get("status") for cell in row["cells"].values()}
        feature = by_id.get(fid, {})
        if "supported" in statuses:
            supported.append(fid)
        elif "linked" in statuses:
            only_structural.append({"feature_id": fid, "statement": str(feature.get("statement") or "")})
        else:
            no_evidence.append({"feature_id": fid, "statement": str(feature.get("statement") or "")})
    return GapReport(
        supported_features=supported,
        structural_only_features=only_structural,
        no_evidence_features=no_evidence,
    )


class GapReport:
    def __init__(
        self,
        *,
        supported_features: list[str],
        structural_only_features: list[dict[str, str]],
        no_evidence_features: list[dict[str, str]],
    ) -> None:
        self.supported_features = supported_features
        self.structural_only_features = structural_only_features
        self.no_evidence_features = no_evidence_features

    def search_recommendations(self) -> list[dict[str, str]]:
        """What WP-A should chase next, phrased as retrieval advice (not conclusions)."""
        return [
            {"feature_id": item["feature_id"], "advice": "plan additional queries for this feature; "
             "current sample contains no anchored evidence"}
            for item in self.no_evidence_features
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "supported": self.supported_features,
            "structural_only": self.structural_only_features,
            "no_evidence": self.no_evidence_features,
            "caveat": "gaps describe the current searched sample; they never support "
            "a claim that no prior art exists",
        }
