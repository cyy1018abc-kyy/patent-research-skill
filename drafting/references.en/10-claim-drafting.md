# 10 Claim drafting (draft-grade)

> Precondition: the preconditions of [09](09-disclosure-drafting.md) are met. The output
> is a **draft**; a patent attorney must review before use.

## Independent claim: zero-disclosure atoms after the preamble

The **zero-disclosure atoms** found in tier 2 of the three-tier determination (see
[00](00-prerequisites.md)) — features no column-D combination can assemble — are the core
of the independent claim. How to write it:

- Preamble: the features shared with the closest document D1 (background correspondence);
- Characterizing portion: "characterized in that" + the distinguishing features
  (zero-disclosure atoms + necessary supporting features);
- every feature must be traceable to a specification paragraph in the support mapping table.

## Layered design of the dependent claims

1. **Numerical layer**: generic concept (independent claim) → numerical range (dependent).
   Ranges must stay inside grade-A (measured) provenance and the specification disclosure —
   over-breadth is the most dangerous defect and cannot be cured in a response;
2. **Alternative-means layer**: 1–2 alternative implementations per key means (anti-design-around);
3. **Scenario layer**: application-scenario limitations (automotive / aviation …,
   matching the scenario sub-queries of the search).

Three questions per dependent claim: which independent claim does it depend on? Do the
added features contradict it? Is there a supporting paragraph?

## Numerical-range self-check (the most frequent trap)

| Check | Tool |
|---|---|
| Claim numbers ⊆ specification disclosure | `claims/numerical_consistency_check.md` (see [00](00-prerequisites.md); the checklist panel is research reference 06) |
| Every number has an A/B/C source | `patentkit provenance check` (V031/V032) |
| Grade C (illustrative example) declared explicitly | the registry's note field |

## Revision discipline

Multi-round revisions follow the loop in [13](13-revision-loop.md): patch → change log →
re-run the gates. **Never touch unrelated content in passing** — any substantive change
invalidates the related human confirmations (the fingerprint changed) and requires
re-confirmation.

## Boundaries

- No grant predictions; never write "this claim is solid" style promises;
- Functional limitations: before writing "a device for …", confirm the specification
  discloses the corresponding structure;
- every comparison document cited while drafting must come from the evidence ledger
  (`patentkit ledger`); V034 blocks invented citations.
