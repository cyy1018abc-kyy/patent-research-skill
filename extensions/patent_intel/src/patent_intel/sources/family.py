"""Family grouping and hit deduplication views (blueprint B-03).

Discipline (interface rule 4): family relations are used **only when a source
actually reported them**. Records without family metadata are never deterministically
merged — they stay ``family_status="unknown"`` and surface as pending for human or
kernel-side census review. Same publication number seen twice is deduplicated; the
same number with conflicting metadata is a *conflict*, never silently rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from patent_intel.sources.normalize import NormalizedID, normalize_publication_number

__all__ = ["FamilyGroup", "FamilyView", "dedupe_ranked_hits"]


@dataclass
class FamilyGroup:
    family_id: str | None
    #: family_status: "reported" (source gave a family id) | "unknown" (no metadata)
    family_status: str
    members: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def describe(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "family_status": self.family_status,
            "member_count": len(self.members),
            "members": [
                m.get("publication_number") or m.get("normalized_number") or "?" for m in self.members
            ],
            "conflicts": self.conflicts,
        }


def _record_number(record: dict[str, Any]) -> str:
    return str(record.get("publication_number") or record.get("normalized_number") or "")


class FamilyView:
    """Rebuildable family grouping over normalized patent records."""

    def __init__(self) -> None:
        self.groups: list[FamilyGroup] = []
        self._by_number: dict[str, FamilyGroup] = {}
        self._by_family: dict[str, FamilyGroup] = {}

    def add(self, record: dict[str, Any], *, normalized: NormalizedID | None = None) -> FamilyGroup:
        """Add one record; returns the group it landed in."""
        norm = normalized or normalize_publication_number(_record_number(record))
        enriched = dict(record)
        enriched["normalized_number"] = norm.normalized
        enriched["number_confidence"] = norm.confidence

        # 1) explicit family id from the source wins
        family_refs = record.get("family_refs") or []
        explicit_family = None
        if isinstance(family_refs, list):
            for ref in family_refs:
                if isinstance(ref, dict) and ref.get("family_id"):
                    explicit_family = str(ref["family_id"])
                    break

        group: FamilyGroup | None = None
        if explicit_family:
            group = self._by_family.get(explicit_family)
            if group is None:
                group = FamilyGroup(family_id=explicit_family, family_status="reported")
                self._by_family[explicit_family] = group
                self.groups.append(group)
        else:
            # 2) same normalized publication number → same single record
            group = self._by_number.get(norm.normalized)
            if group is None:
                group = FamilyGroup(family_id=None, family_status="unknown")
                self._by_number[norm.normalized] = group
                self.groups.append(group)

        if norm.normalized in {_record_number(m) for m in group.members}:
            self._check_conflict(group, enriched)
        else:
            group.members.append(enriched)
        return group

    def _check_conflict(self, group: FamilyGroup, record: dict[str, Any]) -> None:
        """Same publication number, different metadata → conflict entry, data kept."""
        for member in group.members:
            if _record_number(member) != record.get("normalized_number"):
                continue
            for key in ("title", "publication_date", "assignee"):
                a, b = member.get(key), record.get(key)
                if a and b and a != b:
                    note = f"{record.get('normalized_number')}: {key} {a!r} vs {b!r}"
                    if note not in group.conflicts:
                        group.conflicts.append(note)

    def describe(self) -> dict[str, Any]:
        return {
            "group_count": len(self.groups),
            "reported_families": sum(1 for g in self.groups if g.family_status == "reported"),
            "unknown_family_groups": sum(1 for g in self.groups if g.family_status == "unknown"),
            "conflict_count": sum(len(g.conflicts) for g in self.groups),
            "groups": [g.describe() for g in self.groups],
        }


def dedupe_ranked_hits(ranked: list[tuple[int, str, dict[str, Any]]]) -> list[tuple[int, str, dict[str, Any]]]:
    """Collapse ranked hits that belong to the same family, keeping the best rank.

    ``ranked`` items are ``(rank, family_id_or_pub, entry)``. Entries whose family id
    is unknown stay independent — without family metadata we cannot know two numbers
    are one family (UT-S03: 不确定映射不得自动合并).
    """
    seen: set[str] = set()
    out: list[tuple[int, str, dict[str, Any]]] = []
    for rank, key, entry in sorted(ranked, key=lambda x: x[0]):
        family = entry.get("family_id") if isinstance(entry, dict) else None
        if family:
            if family in seen:
                continue
            seen.add(family)
        out.append((rank, key, entry))
    return out
