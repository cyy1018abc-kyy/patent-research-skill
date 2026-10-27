"""Change-impact preview (blueprint D-03): what must be re-reviewed after an edit.

When a kernel record changes (its fingerprint moves), every projection built on the
old fingerprint is marked ``stale`` — review states never survive silently across
content changes (the same discipline as kernel confirm/fingerprint binding, applied
to the extension's own views). This is a preview helper; the kernel's V038
revision-linkage rules remain the authoritative change-control mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from patent_intel.contracts import EvidenceProjection, ReviewState

__all__ = ["ImpactPreview", "preview_fingerprint_change"]

_OWNER = "WP-D"


@dataclass
class ImpactPreview:
    changed_items: list[str] = field(default_factory=list)
    stale_projections: list[EvidenceProjection] = field(default_factory=list)
    unaffected_count: int = 0

    def describe(self) -> dict[str, Any]:
        return {
            "changed_items": self.changed_items,
            "stale_count": len(self.stale_projections),
            "stale_by_feature": sorted({p.feature_id for p in self.stale_projections}),
            "stale_by_candidate": sorted({p.candidate_id for p in self.stale_projections}),
            "unaffected_count": self.unaffected_count,
            "note": "stale projections require re-review; kernel V038 rules govern the "
            "workspace itself — this preview only manages the extension's views",
        }


def preview_fingerprint_change(
    projections: list[EvidenceProjection],
    current_fingerprints: dict[str, str],
    *,
    changed: dict[str, str] | None = None,
) -> ImpactPreview:
    """Mark projections whose ``source_fingerprint`` no longer matches the candidate.

    ``current_fingerprints`` maps candidate_id → current fingerprint; ``changed``
    optionally maps candidate_id → old fingerprint for reporting. A projection whose
    candidate no longer exists at all is also stale (deleted upstream).
    """
    preview = ImpactPreview()
    for proj in projections:
        current = current_fingerprints.get(proj.candidate_id)
        if current is None or current != proj.source_fingerprint:
            stale = EvidenceProjection(
                owner=proj.owner,
                feature_id=proj.feature_id,
                candidate_id=proj.candidate_id,
                relation=proj.relation,
                source_fingerprint=proj.source_fingerprint,
                review_state=ReviewState.STALE,
                anchor=proj.anchor,
                created_at=proj.created_at,
                extra=dict(proj.extra),
            )
            preview.stale_projections.append(stale)
            if proj.candidate_id not in preview.changed_items:
                preview.changed_items.append(proj.candidate_id)
        else:
            preview.unaffected_count += 1
    preview.changed_items.sort()
    return preview
