"""Field-level conflict recording and resolution (adaptive roadmap Task 5, §6.6).

Discipline: **field-level source records, never whole-record overwrite.**

* the same field may carry values from several sources — every value is kept with
  its source and raw-artifact reference;
* resolution happens only by an explicit per-source priority supplied by the caller
  (e.g. zh title prefers CNIPA, en title prefers OPS) — the log itself never picks
  a winner silently;
* a human-confirmed value always wins resolution and is never overwritten by a
  later automatic sync (人工确认记录不能被自动同步覆盖);
* conflicts are kept and reported, not erased.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from patent_intel.contracts import utc_now_iso

__all__ = ["FieldValue", "ResolvedField", "FieldConflictLog"]

_OWNER = "WP-B"

_UNRANKED = 1_000_000  # sources absent from the caller's priority map rank last


@dataclass(frozen=True)
class FieldValue:
    """One source's value for one field of one publication."""

    source: str
    value: str
    raw_ref: str
    recorded_at: str
    confirmed: bool = False


@dataclass(frozen=True)
class ResolvedField:
    """The resolution outcome for one field — winner plus the kept conflict notes."""

    field: str
    value: str | None
    source: str | None
    #: "confirmed" | "priority" | "single" | "empty"
    decided_by: str
    conflicts: list[str] = field(default_factory=list)


class FieldConflictLog:
    """Multi-source field values per publication, with honest conflict accounting."""

    def __init__(self) -> None:
        #: (publication_id, field) -> [FieldValue, …] in recording order
        self._values: dict[tuple[str, str], list[FieldValue]] = {}

    def record(
        self,
        publication_id: str,
        field_name: str,
        *,
        source: str,
        value: str,
        raw_ref: str,
        confirmed: bool = False,
    ) -> FieldValue:
        """Record one source's value. Idempotent for identical (source, value) pairs;
        a *changed* value from the same source is kept alongside the old one — a
        source contradicting itself is a conflict, not a silent update."""
        if not value:
            raise ValueError("empty values are not recorded — absence is expressed by not recording")
        existing = self.values(publication_id, field_name)
        for entry in existing:
            if entry.source == source and entry.value == value:
                if confirmed and not entry.confirmed:
                    upgraded = FieldValue(
                        source=entry.source, value=entry.value, raw_ref=entry.raw_ref,
                        recorded_at=entry.recorded_at, confirmed=True,
                    )
                    self._values[(publication_id, field_name)][
                        existing.index(entry)
                    ] = upgraded
                    return upgraded
                return entry
        entry = FieldValue(
            source=source, value=value, raw_ref=raw_ref,
            recorded_at=utc_now_iso(), confirmed=confirmed,
        )
        self._values.setdefault((publication_id, field_name), []).append(entry)
        return entry

    def confirm(self, publication_id: str, field_name: str, *, source: str, value: str) -> FieldValue:
        """Human confirmation of one existing value — the only upgrade path, and
        one that later automatic records can never undo."""
        return self.record(
            publication_id, field_name, source=source, value=value,
            raw_ref="human-confirmation", confirmed=True,
        )

    def values(self, publication_id: str, field_name: str) -> list[FieldValue]:
        return list(self._values.get((publication_id, field_name), []))

    def resolve(
        self,
        publication_id: str,
        field_name: str,
        *,
        priority: Mapping[str, int] | None = None,
    ) -> ResolvedField:
        """Resolve one field. Confirmed values beat priority; priority beats order."""
        entries = self.values(publication_id, field_name)
        if not entries:
            return ResolvedField(field=field_name, value=None, source=None, decided_by="empty")
        conflicts = self._conflict_notes(entries)

        confirmed = [e for e in entries if e.confirmed]
        if confirmed:
            # multiple confirmations agreeing → fine; disagreeing → conflict kept,
            # the latest confirmation decides (recorded, never erased)
            winner = confirmed[-1]
            return ResolvedField(
                field=field_name, value=winner.value, source=winner.source,
                decided_by="confirmed", conflicts=conflicts,
            )
        if len(entries) == 1:
            only = entries[0]
            return ResolvedField(
                field=field_name, value=only.value, source=only.source,
                decided_by="single", conflicts=conflicts,
            )
        ranked = sorted(
            enumerate(entries),
            key=lambda item: ((priority or {}).get(item[1].source, _UNRANKED), item[0]),
        )
        winner = ranked[0][1]
        return ResolvedField(
            field=field_name, value=winner.value, source=winner.source,
            decided_by="priority", conflicts=conflicts,
        )

    def conflicts(self, publication_id: str | None = None) -> list[dict[str, Any]]:
        """All fields with more than one distinct value (optionally for one publication)."""
        out: list[dict[str, Any]] = []
        for (pid, field_name), entries in sorted(self._values.items()):
            if publication_id is not None and pid != publication_id:
                continue
            notes = self._conflict_notes(entries)
            if notes:
                out.append({"publication_id": pid, "field": field_name, "conflicts": notes})
        return out

    def describe(self) -> dict[str, Any]:
        return {
            "field_count": len(self._values),
            "conflict_count": len(self.conflicts()),
            "note": "字段级来源记录：多源值全部保留，冲突不擦除；人工确认不被自动覆盖",
        }

    @staticmethod
    def _conflict_notes(entries: list[FieldValue]) -> list[str]:
        distinct = {e.value for e in entries}
        if len(distinct) <= 1:
            return []
        by_value: dict[str, str] = {}
        for e in entries:
            by_value.setdefault(e.value, e.source)
        return [
            f"{value!r} ({source})" for value, source in by_value.items()
        ]
