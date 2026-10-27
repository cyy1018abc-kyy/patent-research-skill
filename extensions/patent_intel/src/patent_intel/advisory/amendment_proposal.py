"""Amendment proposal assembly (blueprint D-05) — the advisory layer's only output
type that can influence a claim, and it stops at being a proposal."""

from __future__ import annotations

import hashlib
from typing import Any

from patent_intel.advisory.policy import (
    AdvisoryPolicyError,
    KERNEL_GATE_REFS,
    ensure_proposal_policy,
    proposals_from_projections,
)

__all__ = [
    "build_amendment_proposal",
    "target_fingerprint_from_claims",
    "AdvisoryPolicyError",
    "KERNEL_GATE_REFS",
    "ensure_proposal_policy",
]

_OWNER = "WP-D"


def target_fingerprint_from_claims(claims: list[dict[str, Any]]) -> str:
    """Stable fingerprint over the claim set the proposal targets."""
    canonical = hashlib.sha256(
        "\n".join(
            f"{c.get('number')}:{c.get('text')}" for c in sorted(claims, key=lambda c: str(c.get("number")))
        ).encode("utf-8")
    ).hexdigest()[:16]
    return canonical


def build_amendment_proposal(
    *,
    proposal_id: str,
    claims: list[dict[str, Any]],
    change_kind: str,
    change_payload: dict[str, Any],
    projections: list[Any],
    known_candidate_ids: set[str] | None = None,
    caveats: list[str] | None = None,
) -> Any:
    """Assemble an AdvisoryProposal for a claim change, then policy-check it.

    The proposal is a document to be reviewed by a human and re-entered through the
    kernel's draft/revise gates; it is never applied to any file by this package.
    """
    proposal = proposals_from_projections(
        proposal_id=proposal_id,
        target_fingerprint=target_fingerprint_from_claims(claims),
        change_kind=change_kind,
        change_payload=change_payload,
        projections=projections,
        caveats=caveats,
    )
    ensure_proposal_policy(proposal, known_candidate_ids=known_candidate_ids)
    return proposal
