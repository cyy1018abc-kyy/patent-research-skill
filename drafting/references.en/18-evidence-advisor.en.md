# 18 · Evidence Advisor (optional `patent_intel` extension)

> **Boundary first**: the evidence advisor comes from the optional `patent_intel`
> extension. It produces **reviewable views and suggestions**: evidence projections,
> coverage matrices, claim-chart drafts, amendment proposals. Claim amendments and
> novelty conclusions remain owned exclusively by kernel rules (`draft audit` /
> `revise` / V038 human confirmation); the extension has no auto-confirm backdoor
> and never emits statements about grant prospects. Without the extension the
> drafting workflow is unchanged.

## Evidence views (`evidence build`)

```bash
python -m patent_intel evidence build --root <ws>
```

- Rebuilds the `feature × candidate × evidence` projection read-only from kernel
  candidates; every cell is either anchored with `raw_sha256` or explicitly
  `no_evidence` — "probably supported" is not a state.
- Projections are deletable/rebuildable (sidecar); deleting them never changes
  kernel `check` results.
- **Stale discipline**: when a candidate's content changes (fingerprint moves),
  projections built on the old fingerprint are marked `stale` and await re-review —
  approved views never silently survive content changes.

## Claim chart drafts (library API)

- Rows = claims, columns = candidates; cells carry the kernel review state plus a
  "TBD — requires human feature-by-feature mapping" placeholder. The extension
  performs no infringement/novelty determination.
- **Single-document vs combination**: with no single `blocking` candidate but ≥2
  `partial` ones, the output is a *combination hypothesis* hint (it deserves a
  combined human analysis) — **never** "the combination necessarily destroys
  inventive step" (UT-E02: two documents each disclosing part ≠ one covering all).

## Amendment proposals (`advisory review`)

- Every proposal carries `requires_human_review=true` and names the kernel gate it
  must pass (`draft audit` + `revise` + human confirmation, V038).
- Proposals cite only candidates that exist in the workspace; support-mapping risk
  (does the amendment stay supported by the description?) is flagged as a human
  judgement (EX-02) — the extension does not answer it.

## Usage discipline

1. "no evidence / uncovered" in reports describes **the current searched sample**
   only — never "no prior art exists";
2. projections are views, not a second kernel truth — judgement follows kernel
   candidates and human confirmation;
3. before copying any proposal into a draft, complete the kernel gates; extension
   output is material, not authority.
