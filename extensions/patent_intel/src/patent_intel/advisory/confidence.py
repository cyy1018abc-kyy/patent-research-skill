"""Hard-negative and overconfidence diagnostics (roadmap 41A-4).

Read-only signals about *ranking geometry* — score margins, feature overlap,
and how much trust the top of a ranked list deserves. This module never says
whether a candidate is relevant or not (that judgment belongs to the human
review flow and the G-S discipline); it only makes suspicious score shapes
visible:

* ``above_gold``   — a non-gold candidate ranked above the best gold one;
* ``near_tie``     — adjacent scores so close that the order between them is
  not meaningful (a reranker or one more query term can flip it);
* ``dominant``     — the top score dwarfs the rest: if the top pick is wrong,
  the whole ranking collapses with it (overconfidence shape);
* ``zero_overlap`` — a scored candidate sharing no term with the query: the
  score mass is not explained by the stated query features.

Deterministic and standard-library only: same input → same ``describe()``
bytes on any platform (UT-R01 discipline, as in ``retrieval.metrics``).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "ConfidenceError",
    "CandidateSignal",
    "ConfidenceDiagnosis",
    "diagnose_candidates",
]

_DEFAULT_N = 10
_DEFAULT_MARGIN = 0.05
_DEFAULT_DOMINANCE = 0.5

_GRADE_ORDER = ("above_gold", "near_tie", "zero_overlap", "dominant")


class ConfidenceError(ValueError):
    """Raised on diagnostic-contract violations (duplicate ids, non-finite scores…)."""


@dataclass(frozen=True)
class CandidateSignal:
    """One ranked candidate's diagnostic signals (read-only view)."""

    family_id: str
    rank: int  # 1-based, best-first
    score: float
    is_gold: bool
    overlap: int
    overlap_ratio: float
    margin_above: float | None  # score[i-1] - score[i]; None for rank 1
    margin_below: float | None  # score[i] - score[i+1]; None for the last one
    margin_to_gold: float | None  # score - best ranked gold score; None if no gold ranked
    grades: tuple[str, ...]


def diagnose_candidates(
    ranked: Sequence[tuple[str, float]],
    *,
    query_terms: Iterable[str],
    candidate_terms: Mapping[str, Iterable[str]],
    gold: Iterable[str] = (),
    n: int = _DEFAULT_N,
    margin_threshold: float = _DEFAULT_MARGIN,
    dominance_ratio: float = _DEFAULT_DOMINANCE,
) -> "ConfidenceDiagnosis":
    """Diagnose a best-first ranked list of ``(family_id, score)`` candidates.

    ``candidate_terms`` must cover **every** ranked id (fail-closed: a candidate
    whose feature set is unknown is a data error, not a silent zero overlap).
    Gold ids absent from the list are fine — that is the "gold not retrieved"
    shape and is reported as such, never treated as an error.
    """
    if n <= 0:
        raise ConfidenceError(f"n must be positive, got {n}")
    if margin_threshold < 0.0:
        raise ConfidenceError(f"margin_threshold must be non-negative, got {margin_threshold}")
    if not 0.0 < dominance_ratio <= 1.0:
        raise ConfidenceError(f"dominance_ratio must be in (0, 1], got {dominance_ratio}")

    ids = [str(fid) for fid, _ in ranked]
    dupes = sorted({fid for fid in ids if ids.count(fid) > 1})
    if dupes:
        raise ConfidenceError(f"ranked list contains duplicate candidates: {dupes[:5]}")
    for fid, score in ranked:
        if not math.isfinite(float(score)):
            raise ConfidenceError(f"{fid}: score must be finite, got {score!r}")
    scores = [float(score) for _, score in ranked]

    missing = sorted({fid for fid, _ in ranked if str(fid) not in candidate_terms})
    if missing:
        raise ConfidenceError(f"candidate_terms missing ranked candidates: {missing[:5]}")

    qset = frozenset(str(t) for t in query_terms)
    gold_set = frozenset(str(g) for g in gold)

    best_gold_score: float | None = None
    best_gold_rank: int | None = None
    for rank, (fid, score) in enumerate(ranked, start=1):
        if fid in gold_set and (best_gold_score is None or score > best_gold_score):
            best_gold_score = score
            best_gold_rank = rank

    signals: list[CandidateSignal] = []
    grades: dict[str, list[str]] = {name: [] for name in _GRADE_ORDER}
    for rank, (fid, score) in enumerate(ranked, start=1):
        terms = frozenset(str(t) for t in candidate_terms[str(fid)])
        overlap = len(qset & terms)
        ratio = overlap / len(qset) if qset else 0.0
        margin_above = scores[rank - 2] - score if rank > 1 else None
        margin_below = score - scores[rank] if rank < len(ranked) else None
        margin_to_gold = score - best_gold_score if best_gold_score is not None else None

        matched: list[str] = []
        if fid not in gold_set:
            if margin_to_gold is not None and margin_to_gold > 0.0:
                matched.append("above_gold")
            if (margin_above is not None and margin_above <= margin_threshold) or (
                margin_below is not None and margin_below <= margin_threshold
            ):
                matched.append("near_tie")
            if overlap == 0:
                matched.append("zero_overlap")
            if (
                rank == 1
                and margin_below is not None
                and score > 0.0
                and margin_below >= dominance_ratio * score
            ):
                matched.append("dominant")
        for name in matched:
            grades[name].append(fid)

        signals.append(
            CandidateSignal(
                family_id=fid,
                rank=rank,
                score=score,
                is_gold=fid in gold_set,
                overlap=overlap,
                overlap_ratio=ratio,
                margin_above=margin_above,
                margin_below=margin_below,
                margin_to_gold=margin_to_gold,
                grades=tuple(matched),
            )
        )

    margins = sorted(scores[i] - scores[i + 1] for i in range(len(scores) - 1))
    subjects = [s for s in signals if not s.is_gold][:n]
    return ConfidenceDiagnosis(
        signals=signals,
        subjects=subjects,
        margins=margins,
        grades=grades,
        margin_threshold=margin_threshold,
        dominance_ratio=dominance_ratio,
        n=n,
        best_gold_rank=best_gold_rank,
        gold_count=len(gold_set & set(ids)),
    )


class ConfidenceDiagnosis:
    """Immutable result of :func:`diagnose_candidates`."""

    def __init__(
        self,
        *,
        signals: list[CandidateSignal],
        subjects: list[CandidateSignal],
        margins: list[float],
        grades: dict[str, list[str]],
        margin_threshold: float,
        dominance_ratio: float,
        n: int,
        best_gold_rank: int | None,
        gold_count: int,
    ) -> None:
        self.signals = signals
        self.subjects = subjects
        self.margins = margins
        self.grades = grades
        self._margin_threshold = margin_threshold
        self._dominance_ratio = dominance_ratio
        self._n = n
        self._best_gold_rank = best_gold_rank
        self._gold_count = gold_count

    def describe(self) -> dict[str, Any]:
        """JSON-safe, deterministic summary (same input → same bytes)."""
        count = len(self.margins)
        median: float | None
        if count == 0:
            median = None
        elif count % 2 == 1:
            median = self.margins[count // 2]
        else:
            median = (self.margins[count // 2 - 1] + self.margins[count // 2]) / 2.0
        top_score = self.signals[0].score if self.signals else None
        second_score = self.signals[1].score if len(self.signals) > 1 else None
        top_margin_below = self.signals[0].margin_below if self.signals else None
        dominance = None
        if top_score is not None and second_score is not None and top_score > 0.0:
            dominance = (top_score - second_score) / top_score
        return {
            "params": {
                "n": self._n,
                "margin_threshold": self._margin_threshold,
                "dominance_ratio": self._dominance_ratio,
            },
            "gold": {
                "gold_count_ranked": self._gold_count,
                "best_gold_rank": self._best_gold_rank,
            },
            "dominance": {
                "top_score": top_score,
                "second_score": second_score,
                "top_margin_below": top_margin_below,
                "ratio": dominance,
            },
            "margins": {
                "values": list(self.margins),
                "summary": {
                    "count": count,
                    "min": self.margins[0] if count else None,
                    "median": median,
                    "max": self.margins[-1] if count else None,
                    "tight": sum(1 for m in self.margins if m <= self._margin_threshold),
                },
            },
            "subjects": [self._signal_dict(s) for s in self.subjects],
            "grades": {name: list(ids) for name, ids in self.grades.items()},
            "caveat": "diagnostic signals about ranking geometry only; they never "
            "assert relevance or irrelevance",
        }

    @staticmethod
    def _signal_dict(s: CandidateSignal) -> dict[str, Any]:
        return {
            "family_id": s.family_id,
            "rank": s.rank,
            "score": s.score,
            "is_gold": s.is_gold,
            "overlap": s.overlap,
            "overlap_ratio": s.overlap_ratio,
            "margin_above": s.margin_above,
            "margin_below": s.margin_below,
            "margin_to_gold": s.margin_to_gold,
            "grades": list(s.grades),
        }
