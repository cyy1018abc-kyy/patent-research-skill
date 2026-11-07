"""Time-sensitive view (roadmap 41C-1): publication/priority dates as advisory filters.

Discipline:

* suggestions **never change recall or ranking** — the view annotates an existing
  ranked list with date structure so a human (or a later, explicit stage) decides
  what to filter; the input order is echoed back verbatim and nothing re-sorts;
* a missing date stays ``unknown``/``partial`` — it never becomes a fabricated
  value; multi-source date conflicts are flagged and their values preserved
  (sorted, deduplicated) — never silently resolved;
* suggestions come from a closed vocabulary and are phrased as *filter advice*,
  not as relevance or novelty conclusions (a date alone never says what is
  prior art — that judgment stays with the human review flow).

Deterministic and standard-library only; same input → same ``describe()`` bytes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date as _date
from typing import Any

__all__ = ["TimeViewError", "TimeSignal", "TimeViewReport", "time_view"]

_OWNER = "WP-C"

_SUGGESTIONS = ("review_date_conflict", "filter_publication_after_target", "priority_date_missing")


class TimeViewError(ValueError):
    """Raised on impossible time-view requests (unparseable target date)."""


@dataclass(frozen=True)
class TimeSignal:
    """One candidate's date structure + advisory suggestion (read-only view)."""

    family_id: str
    rank: int  # 1-based position in the ranked list passed in — never re-sorted
    publication_date: str | None
    priority_date: str | None
    date_status: str  # "known" | "partial" | "unknown" | "conflicted"
    conflicts: tuple[str, ...]
    suggestion: str | None


class TimeViewReport:
    """Immutable result of :func:`time_view`."""

    def __init__(self, *, signals: list[TimeSignal], ranked_order: list[str]) -> None:
        self.signals = signals
        self.ranked_order = ranked_order

    def describe(self) -> dict[str, Any]:
        """JSON-safe, deterministic summary (same input → same bytes)."""
        status_counts = {name: 0 for name in ("known", "partial", "unknown", "conflicted")}
        suggestion_counts = {name: 0 for name in _SUGGESTIONS}
        for signal in self.signals:
            status_counts[signal.date_status] += 1
            if signal.suggestion is not None:
                suggestion_counts[signal.suggestion] += 1
        return {
            "ranked_order": list(self.ranked_order),
            "signals": [self._signal_dict(s) for s in self.signals],
            "summary": {
                "count": len(self.signals),
                "date_status": status_counts,
                "suggestions": suggestion_counts,
            },
            "caveat": "advisory date structure only — it never changes recall or ranking; "
            "a date alone is not a relevance or novelty conclusion",
        }

    @staticmethod
    def _signal_dict(s: TimeSignal) -> dict[str, Any]:
        return {
            "family_id": s.family_id,
            "rank": s.rank,
            "publication_date": s.publication_date,
            "priority_date": s.priority_date,
            "date_status": s.date_status,
            "conflicts": list(s.conflicts),
            "suggestion": s.suggestion,
        }


def _collect_values(entry: Mapping[str, Any], singular: str, plural: str) -> list[str]:
    values: list[str] = []
    for key in (singular, plural):
        raw = entry.get(key)
        if raw is None:
            continue
        items = raw if isinstance(raw, (list, tuple)) else [raw]
        for item in items:
            text = str(item).strip()
            if text:
                values.append(text)
    return values


def _resolve_date(values: list[str]) -> tuple[str | None, str | None]:
    """One confident date or an honest conflict; unparseable values never become dates."""
    if not values:
        return None, None
    distinct = sorted(set(values))
    if len(distinct) > 1:
        return None, f"conflicting values: {distinct}"
    try:
        _date.fromisoformat(distinct[0])
    except ValueError:
        return None, f"unparseable date value: {distinct[0]!r}"
    return distinct[0], None


def time_view(
    ranked: Sequence[str],
    dates_by_family: Mapping[str, Mapping[str, Any]],
    *,
    target_filing_date: str | None = None,
) -> TimeViewReport:
    """Annotate a best-first ranked list with publication/priority date structure.

    ``dates_by_family[family_id]`` accepts ``publication_date``/``priority_date``
    (single value) or ``publication_dates``/``priority_dates`` (multi-source
    values); a family with no entry is ``unknown`` — never fabricated. When
    ``target_filing_date`` is given (ISO date), candidates published **after**
    it carry the ``filter_publication_after_target`` suggestion (advisory only).
    """
    target: _date | None = None
    if target_filing_date is not None:
        try:
            target = _date.fromisoformat(str(target_filing_date))
        except ValueError as exc:
            raise TimeViewError(
                f"target_filing_date must be an ISO date (YYYY-MM-DD), got {target_filing_date!r}"
            ) from exc

    signals: list[TimeSignal] = []
    ranked_order: list[str] = []
    for rank, family_id in enumerate(ranked, start=1):
        family_id = str(family_id)
        ranked_order.append(family_id)
        entry = dates_by_family.get(family_id) or {}
        pub_values = _collect_values(entry, "publication_date", "publication_dates")
        prio_values = _collect_values(entry, "priority_date", "priority_dates")
        publication_date, pub_conflict = _resolve_date(pub_values)
        priority_date, prio_conflict = _resolve_date(prio_values)
        conflicts = tuple(c for c in (pub_conflict, prio_conflict) if c is not None)

        if conflicts:
            date_status = "conflicted"
        elif publication_date is None and priority_date is None:
            date_status = "unknown"
        elif publication_date is None or priority_date is None:
            date_status = "partial"
        else:
            date_status = "known"

        suggestion: str | None = None
        if conflicts:
            suggestion = "review_date_conflict"
        elif target is not None and publication_date is not None:
            if _date.fromisoformat(publication_date) > target:
                suggestion = "filter_publication_after_target"
        if suggestion is None and publication_date is not None and priority_date is None:
            suggestion = "priority_date_missing"

        signals.append(
            TimeSignal(
                family_id=family_id,
                rank=rank,
                publication_date=publication_date,
                priority_date=priority_date,
                date_status=date_status,
                conflicts=conflicts,
                suggestion=suggestion,
            )
        )
    return TimeViewReport(signals=signals, ranked_order=ranked_order)
