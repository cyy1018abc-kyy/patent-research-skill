"""Technical-feature extraction for the query view (blueprint A-01, WP-A).

Deterministic, offline rule-based decomposition of feature statements into
:class:`FeatureSpec` records:

* sub-clauses (split on ；/;/。/newline) become independent features — features
  never bleed into each other (UT-Q01);
* negation markers (不含/没有/无需/不包括/without/...) flip ``negation`` and set
  ``requiredness=negation`` — a negated constraint must stay a *negative* filter,
  never a positive term (UT-Q01: 否定词不丢失);
* numeric constraints (≥/≤/>/</=/±, 正负公差) are captured in ``numeric_bounds``
  and graded ``numeric_bound`` — they must not be dropped or rounded into vague
  terms;
* optional markers (可选/任选/可以是/may/optionally) grade ``optional``.

The authoritative feature definition stays in Discovery/patentkit; these records are
the *query view* and always carry ``source_refs`` back to their origin statement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from patent_intel.contracts import FeatureSpec, Requiredness

__all__ = ["FeatureExtractionError", "extract_features", "CLAUSE_SPLIT"]

_CLAUSE_SPLIT = re.compile(r"[；;。\n]+")

_NEGATION_MARKERS = (
    "不含", "不包括", "没有", "无需", "无须", "不使用", "不依赖", "排除",
    "without", "not comprising", "excluding", "free of", "absent",
)
_OPTIONAL_MARKERS = ("可选", "任选", "可以是", "其中一个实施例", "may optionally", "optionally", "in some embodiments")
_NUMERIC = re.compile(
    r"(?P<op>≥|≤|>=|<=|>|<|=|±|约)\s*(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>%|ms|s|us|μs|Hz|kHz|MHz|ppm|dB|V|A|W|mm|cm|m|nm)?"
)

_OWNER = "WP-A"


class FeatureExtractionError(ValueError):
    """Malformed feature input."""


@dataclass(frozen=True)
class FeatureBundle:
    """Extraction result: features + the axis they belong to."""

    axis_id: str
    features: list[FeatureSpec]

    def approved_only(self) -> list[FeatureSpec]:
        return [f for f in self.features if f.approved]


def _detect_negation(text: str) -> bool:
    low = text.lower()
    return any(marker in text for marker in _NEGATION_MARKERS) or any(
        marker in low for marker in _NEGATION_MARKERS
    )


def _detect_optional(text: str) -> bool:
    low = text.lower()
    return any(marker in text for marker in _OPTIONAL_MARKERS) or any(
        marker in low for marker in _OPTIONAL_MARKERS
    )


def _extract_numeric_bounds(text: str) -> list[dict[str, str]]:
    bounds = []
    for match in _NUMERIC.finditer(text):
        bounds.append(
            {
                "op": match.group("op"),
                "value": match.group("value"),
                "unit": match.group("unit") or "",
                "context": text[max(0, match.start() - 12): match.end() + 8].strip(),
            }
        )
    return bounds


def extract_features(
    statements: list[str],
    *,
    axis_id: str,
    source_tag: str = "user-input",
    approved: bool = False,
) -> FeatureBundle:
    """Split feature statements into independent, graded FeatureSpec records.

    ``approved`` defaults to False: extraction never auto-approves — every feature
    awaits human review (the bundle feeds query planning only after approval).
    """
    if not axis_id:
        raise FeatureExtractionError("axis_id is required (target-qualified, e.g. N1@TGT-0001)")
    features: list[FeatureSpec] = []
    index = 0
    for statement in statements:
        statement = statement.strip()
        if not statement:
            continue
        for clause in _CLAUSE_SPLIT.split(statement):
            clause = clause.strip()
            if not clause:
                continue
            index += 1
            negation = _detect_negation(clause)
            optional = _detect_optional(clause) and not negation
            bounds = _extract_numeric_bounds(clause)
            if negation:
                requiredness = Requiredness.NEGATION
            elif bounds and len(clause) < 60:  # primarily a numeric constraint
                requiredness = Requiredness.NUMERIC_BOUND
            elif optional:
                requiredness = Requiredness.OPTIONAL
            else:
                requiredness = Requiredness.REQUIRED
            features.append(
                FeatureSpec(
                    owner=_OWNER,
                    feature_id=f"FEAT-{axis_id.split('@')[0]}-{index:03d}",
                    statement=clause,
                    source_refs=[f"{source_tag}:{statement[:40]}"],
                    requiredness=requiredness,
                    negation=negation,
                    approved=approved,
                    axis_id=axis_id,
                    numeric_bounds=bounds or None,
                )
            )
    if not features:
        raise FeatureExtractionError("no feature statements provided")
    return FeatureBundle(axis_id=axis_id, features=features)
