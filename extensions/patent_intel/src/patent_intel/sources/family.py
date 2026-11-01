"""Family grouping and hit deduplication views (blueprint B-03).

Discipline (interface rule 4): family relations are used **only when a source
actually reported them**. Records without family metadata are never deterministically
merged — they stay ``family_status="unknown"`` and surface as pending for human or
kernel-side census review. Same publication number seen twice is deduplicated; the
same number with conflicting metadata is a *conflict*, never silently rewritten.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from patent_intel.sources.normalize import NormalizedID, normalize_publication_number

__all__ = [
    "FamilyGroup",
    "FamilyView",
    "dedupe_ranked_hits",
    "dedupe_publication_records",
    "account_new",
]


@dataclass
class FamilyGroup:
    family_id: str | None
    #: family_status: "reported" (source gave a family id) | "unknown" (no metadata)
    family_status: str
    members: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    #: family refs graded uncertain — recorded for review, never used for merging
    #: (adaptive roadmap Task 5: 不可靠关系不自动合并)
    deferred_family_refs: list[dict[str, Any]] = field(default_factory=list)

    def describe(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "family_status": self.family_status,
            "member_count": len(self.members),
            "members": [
                m.get("publication_number") or m.get("normalized_number") or "?" for m in self.members
            ],
            "conflicts": self.conflicts,
            "deferred_family_refs": len(self.deferred_family_refs),
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

        # 1) explicit family id from the source wins — refs graded "uncertain" are
        # deferred to the landed group for review, never used for merging (Task 5:
        # 不可靠关系不自动合并; confidence absent = treated as reported, preserving
        # the pre-Task-5 contract where plain {"family_id": …} refs merge)
        family_refs = record.get("family_refs") or []
        explicit_family = None
        deferred_refs: list[dict[str, Any]] = []
        if isinstance(family_refs, list):
            for ref in family_refs:
                if isinstance(ref, dict) and ref.get("family_id"):
                    if ref.get("confidence") == "uncertain":
                        deferred_refs.append(ref)
                        continue
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
        for ref in deferred_refs:
            if ref not in group.deferred_family_refs:
                group.deferred_family_refs.append(ref)
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


def dedupe_publication_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Dedup multi-subquery results by publication-number identity (roadmap §5.3).

    Records whose normalized numbers agree are the *same publication* — the first
    occurrence is kept and later metadata differences are recorded as conflicts,
    never silently rewritten. Unparseable numbers dedupe only by their exact raw
    string. The stats distinguish the accounting honestly:
    ``{"seen", "unique", "duplicates", "conflicts"}``.
    """
    unique: list[dict[str, Any]] = []
    by_identity: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    duplicates = 0
    for record in records:
        raw = str(record.get("publication_number") or record.get("normalized_number") or "")
        norm = normalize_publication_number(raw)
        identity = norm.normalized if norm.confidence != "uncertain" else raw.strip()
        if not identity:
            identity = f"<unnumbered:{len(unique)}>"  # keep unnumbered rows independent
        existing = by_identity.get(identity)
        if existing is None:
            enriched = dict(record)
            enriched["normalized_number"] = norm.normalized or raw
            enriched["number_confidence"] = norm.confidence
            by_identity[identity] = enriched
            unique.append(enriched)
            continue
        duplicates += 1
        for key in ("title", "publication_date", "assignee"):
            a, b = existing.get(key), record.get(key)
            if a and b and a != b:
                note = f"{identity}: {key} {a!r} vs {b!r}"
                if note not in conflicts:
                    conflicts.append(note)
    return unique, {
        "seen": len(records),
        "unique": len(unique),
        "duplicates": duplicates,
        "conflicts": conflicts,
    }


def account_new(
    records: list[dict[str, Any]],
    *,
    known_publications: Collection[str],
    known_families: Collection[str],
) -> dict[str, int]:
    """New-publication / new-family accounting against the caller's corpus state
    (roadmap §8.3: new_publications / new_families are corpus deltas, not hit
    counts). Family contribution uses only reported (non-uncertain) family refs —
    uncertain relations never contribute to family accounting. Records the caller
    already holds are not new; duplicates inside one batch count once.
    """
    known_pubs = {str(p) for p in known_publications}
    known_fams = {str(f) for f in known_families}
    new_pubs = 0
    new_families = 0
    seen_families: set[str] = set()
    for record in records:
        pub = str(record.get("publication_number") or record.get("normalized_number") or "").strip()
        if pub:
            norm = normalize_publication_number(pub)
            if norm.confidence != "uncertain" and norm.normalized and norm.normalized not in known_pubs:
                known_pubs.add(norm.normalized)
                new_pubs += 1
        for ref in record.get("family_refs") or []:
            if (
                isinstance(ref, dict)
                and ref.get("family_id")
                and ref.get("confidence") != "uncertain"
            ):
                family_id = str(ref["family_id"])
                if family_id not in known_fams and family_id not in seen_families:
                    seen_families.add(family_id)
                    new_families += 1
    return {"new_publications": new_pubs, "new_families": new_families}
