"""Evidence projection builder (blueprint D-01): a rebuildable, read-only view of
feature ↔ candidate ↔ evidence relations derived from the kernel workspace.

Discipline:
* every projection traces to the kernel candidate's own fields (tags → axes,
  novelty_check, evidence_ref) — the projection adds no judgements of its own;
* relations mirror kernel-reviewed states only: ``blocking``/``covered`` →
  ``discloses``, ``partial`` → ``partially_discloses``; unreviewed candidates
  produce **no** disclosure relation (absence of judgement is not a relation);
* rebuilds are deterministic and complete from (kernel workspace + sidecar
  features): deleting the sidecar evidence cache and rebuilding yields identical
  output (cache-deletion invariant, tested).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from patent_intel.contracts import EvidenceProjection, ReviewState, Relation
from patent_intel.io.safe_io import write_json_atomic
from patent_intel.kernel_bridge import read_candidates

__all__ = ["EvidenceGraphBuilder", "fingerprint_record", "export_projections"]

_OWNER = "WP-D"

_NOVELTY_TO_RELATION = {
    "blocking": Relation.DISCLOSES,
    "covered": Relation.DISCLOSES,
    "partial": Relation.PARTIALLY_DISCLOSES,
}


def fingerprint_record(record: dict[str, Any]) -> str:
    """Stable fingerprint of a kernel record (for impact analysis)."""
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class EvidenceGraphBuilder:
    """Builds EvidenceProjection records from the kernel workspace (read-only)."""

    def __init__(self, *, features: list[dict[str, Any]] | None = None) -> None:
        # features: serialized FeatureSpec dicts from the sidecar (query view)
        self._features = features or []

    def build_from_workspace(self, workspace: Path) -> list[EvidenceProjection]:
        workspace = Path(workspace)
        candidates = read_candidates(workspace)
        projections: list[EvidenceProjection] = []

        for cand in candidates:
            cand_id = str(cand.get("id") or "")
            if not cand_id:
                continue
            fp = fingerprint_record(cand)
            tags = cand.get("tags") or []
            novelty = str(cand.get("novelty_check") or "untouched")
            relation = _NOVELTY_TO_RELATION.get(novelty)
            evidence_ref = cand.get("evidence_ref")
            anchor: dict[str, Any] | None = None
            if evidence_ref:
                evidence_path = (workspace / "03_candidates" / str(evidence_ref)).resolve()
                if not evidence_path.is_file():
                    evidence_path = (workspace / str(evidence_ref)).resolve()
                if evidence_path.is_file():
                    anchor = {
                        "raw_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                        "source_document": str(evidence_ref),
                    }

            matched_axes = {str(tag) for tag in tags if isinstance(tag, str)}
            for feature in self._features:
                axis = feature.get("axis_id")
                if axis and axis in matched_axes:
                    # axis-level linkage is structural; disclosure relation only
                    # when the kernel review supports it
                    if relation is not None:
                        projections.append(
                            EvidenceProjection(
                                owner=_OWNER,
                                feature_id=str(feature.get("feature_id")),
                                candidate_id=cand_id,
                                relation=relation,
                                source_fingerprint=fp,
                                review_state=ReviewState.PENDING,
                                anchor=anchor,
                            )
                        )
                    else:
                        # structural link without disclosure claim
                        projections.append(
                            EvidenceProjection(
                                owner=_OWNER,
                                feature_id=str(feature.get("feature_id")),
                                candidate_id=cand_id,
                                relation=Relation.CITED_BY,  # neutral: candidate cites this axis
                                source_fingerprint=fp,
                                review_state=ReviewState.PENDING,
                                anchor=anchor,
                            )
                        )
        # deterministic order for rebuild stability
        projections.sort(key=lambda p: (p.feature_id, p.candidate_id, p.relation))
        return projections


def export_projections(projections: list[EvidenceProjection], out_dir: Path) -> Path:
    """Write projections to the sidecar (JSON). Returns the written path."""
    out_dir = Path(out_dir)
    payload = [p.to_dict() for p in projections]
    path = out_dir / "projections.json"
    write_json_atomic(path, {"projections": payload, "count": len(payload)})
    return path
