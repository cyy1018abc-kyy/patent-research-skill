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

## Domain-specific claim forms (2025 Guidelines practice)

On top of the general discipline, specific subject matters carry their own **claim forms** and
**binding requirements** — match the subject before drafting:

### AI / software / algorithms (Guidelines Part II Ch. 9 §2, §5.2, §6)

- **Four-part layout**: method + apparatus + computer-readable storage medium + computer
  program product. An apparatus claim whose steps mirror the program flow is read as a
  **program-module architecture** (not a hardware entity); the program product is read as a
  software product;
- **Subject-matter three-element self-check** (§2): solves a technical problem + technical means
  obeying natural laws + a technical effect obeying natural laws — all three for Art. 2.2.
  Three grant paths at a glance (§6.1.3): ① the algorithm processes data of definite technical
  meaning in a technical field; ② the algorithm is technically coupled to the computer system's
  internals (less storage/transmission, faster processing); ③ big data of a concrete field is
  mined for lawful inner correlations;
- **Algorithm features must bind to technical data**: at least one input parameter and its
  output must correspond to concrete technical data of the field — a floating algorithm feature
  risks both subject matter (Art. 25/2.2) and enablement (26.3);
- **Inventive-step credit** (§6.1.4): algorithm/business features that "support each other
  functionally and interact" are considered as a whole — credit when the algorithm is applied
  to a concrete technical problem, improves the computer's internal performance, or the business
  rule requires technical adjustment to implement;
- **Bitstreams** (§7): start from the coding-method independent claim and draft the storage
  method / transmission method / storage medium claims by reference to it;
- The zero-disclosure-atom discipline is unchanged: algorithm improvements also go into the
  feature-atom table and the support mapping table.

### Chemistry / compositions (Guidelines Part II Ch. 10 §4; expanded in [19](19-chemistry-practice.md))

- **Open vs. closed wording**: "containing / including / consisting essentially of" versus
  "consisting of" lead to opposite novelty outcomes — choose deliberately;
- content amounts must not use "approximately / about / nearly", and ">X" formulations are not
  allowed; the sum of all component percentages equals 100%;
- **medical use is drafted as a manufacturing-use**: "use of compound X in the manufacture of a
  medicament for treating disease Y" — administration features (subject / route / dosage /
  intervals) have no limiting effect; do not rely on them for scope.

### Biotechnology (Guidelines Part II Ch. 10 §9)

- sequence subjects: a nucleotide sequence of ≥10 nucleotides or a peptide of ≥4 L-amino acids
  requires a sequence listing (a separate part of the specification);
- six claim forms for genes: base sequence / encoded amino-acid sequence / reference to the
  listing / "substitution-deletion-addition + function" (derivative proteins must be exemplified) /
  hybridization under stringent conditions + function (conditions must be detailed) / function-only fallback;
- monoclonal antibodies: define by the SEQ ID NO of the six CDRs or by the hybridoma deposit
  number; a known antigen defined by the antigen alone lacks inventive step;
- **deposits**: biological material the public cannot obtain must be deposited; deposit and
  viability certificates within 4 months of the filing date at the latest (now preset as
  `biological_deposit` in `patentkit deadlines`).

## Boundaries

- No grant predictions; never write "this claim is solid" style promises;
- Functional limitations: before writing "a device for …", confirm the specification
  discloses the corresponding structure;
- every comparison document cited while drafting must come from the evidence ledger
  (`patentkit ledger`); V034 blocks invented citations.
