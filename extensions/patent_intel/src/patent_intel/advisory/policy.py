"""Amendment proposal guardrails (blueprint D-05).

`policy.py` is the single place the advisory layer's self-limitations are encoded:

1. every proposal requires human review (contract-enforced in AdvisoryProposal);
2. every proposal names the kernel gate its adoption must pass
   (``draft audit`` / ``revise``) — the extension cannot and will not write claims;
3. proposals must carry resolvable evidence refs (candidate ids that exist in the
   workspace the proposal was built from);
4. support-mapping risk is flagged, not assessed: whether an amendment stays
   supported by the description is a legal judgement (EX-02).
"""

from __future__ import annotations

from typing import Any

from patent_intel.contracts import AdvisoryProposal, EvidenceProjection

__all__ = ["AdvisoryPolicyError", "ensure_proposal_policy", "KERNEL_GATE_REFS"]

_OWNER = "WP-D"

#: kernel entry points an adopted proposal must traverse — naming them in every
#: proposal keeps the human loop explicit.
KERNEL_GATE_REFS = {
    "claim_amendment": "patentkit draft audit + revise + human confirm (V038)",
    "new_claim": "patentkit draft audit + revise + human confirm (V038)",
    "feature_refinement": "patentkit review assess + human confirm",
}


class AdvisoryPolicyError(ValueError):
    """A proposal violates the advisory-layer policy and must not be emitted."""


def ensure_proposal_policy(
    proposal: AdvisoryProposal,
    *,
    known_candidate_ids: set[str] | None = None,
) -> None:
    """Validate a proposal against the policy; raise with a precise reason."""
    if not proposal.requires_human_review:  # pragma: no cover - contract also blocks this
        raise AdvisoryPolicyError("requires_human_review must be true")
    gate_ref = proposal.kernel_gate_ref
    if not gate_ref:
        raise AdvisoryPolicyError(
            f"proposal {proposal.proposal_id} must name the kernel gate it must pass "
            f"(expected one of: {sorted(KERNEL_GATE_REFS.values())})"
        )
    kind = str(proposal.change.get("kind") or "")
    expected = KERNEL_GATE_REFS.get(kind)
    if expected and expected not in gate_ref:
        raise AdvisoryPolicyError(
            f"change kind {kind!r} requires kernel gate {expected!r}, got {gate_ref!r}"
        )
    if known_candidate_ids is not None:
        for ref in proposal.evidence_refs:
            cand = ref.get("candidate_id") if isinstance(ref, dict) else None
            if cand and str(cand) not in known_candidate_ids:
                raise AdvisoryPolicyError(
                    f"evidence ref {cand!r} is not a known candidate; proposals may only "
                    "cite candidates that exist in the workspace"
                )


def proposals_from_projections(
    *,
    proposal_id: str,
    target_fingerprint: str,
    change_kind: str,
    change_payload: dict[str, Any],
    projections: list[EvidenceProjection],
    caveats: list[str] | None = None,
) -> AdvisoryProposal:
    """Build a policy-compliant proposal anchored to existing projections."""
    if change_kind not in KERNEL_GATE_REFS:
        raise AdvisoryPolicyError(
            f"unknown change kind {change_kind!r} (known: {sorted(KERNEL_GATE_REFS)})"
        )
    evidence_refs = [
        {"candidate_id": p.candidate_id, "feature_id": p.feature_id, "relation": p.relation}
        for p in projections
    ]
    proposal = AdvisoryProposal(
        owner=_OWNER,
        proposal_id=proposal_id,
        target_fingerprint=target_fingerprint,
        change={"kind": change_kind, **change_payload},
        evidence_refs=evidence_refs,
        requires_human_review=True,
        caveats=caveats
        or [
            "support-mapping risk not assessed — verify the amendment stays supported "
            "by the description (EX-02)",
        ],
        kernel_gate_ref=KERNEL_GATE_REFS[change_kind],
    )
    ensure_proposal_policy(proposal)
    return proposal
