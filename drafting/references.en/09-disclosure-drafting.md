# 09 Disclosure and application documents (draft-grade)

> Position: convert the search results into **disclosure / application-document drafts**.
> Benchmark: the patent-disclosure / patent-application skills of the public
> patent-disclosure-skill, and drafting-spec of cnipa-patent-kit.
> **This skill produces drafts and flags gaps; it does not replace a patent attorney and
> is not legal advice.**

## Preconditions (do not start without them)

- **G-S-01 through G-S-03 met** (otherwise the disclosure is built on insufficient search);
- the comparison matrix is filled; every column-D document carries an evidence level and
  judgment state;
- the numerical-claim provenance registry (A/B/C) is in place (see
  [00](00-prerequisites.md) and `patentkit provenance check`).

## The five-part disclosure skeleton (invention / utility model)

1. **Title**: ≤25 characters, subject type explicit (apparatus / method / system);
2. **Technical field**: one paragraph — superordinate field + subdivision;
3. **Background**: **only real retrieved documents** — cite column-D IDs (P-xxx) + document
   numbers + defects. Every defect must map to a difference in the comparison matrix;
   **never fabricate "the prior art suffers from …" statements**;
4. **Summary of the invention**: the technical problem (from the tier-2 distinguishing
   features) + the technical solution (per N axis; reuse the feature-atom table) +
   beneficial effects (each mapped to a column-D difference, quantified where possible);
5. **Brief description of the drawings + detailed embodiments**: meet the embodiment bar of
   the 2025 Guidelines (Part II Ch. 2 §2.2.6) — at least **two different embodiments** for a
   broad generalization (a single embodiment cannot carry it); a numerical range needs at
   least its **two endpoints**, and a wide range adds at least one intermediate value; numbers
   come from grade-A/C sources of the provenance registry, and grade C (illustrative example)
   must be declared explicitly.

## From disclosure to application documents (Implementing Regulations 20–23)

| Document | Basis | Self-check |
|---|---|---|
| Claims | Reg. 20–22: independent/dependent structure, unity | Layered self-check in [10](10-claim-drafting.md) |
| Specification | Reg. 20: five-part structure (field / background / summary / drawings / embodiments) | Every claim has a supporting paragraph (support mapping table) |
| Abstract | ≤300 characters, subject and effect | Length and range declarations |
| Drawings | see `patentkit figures` (full spec in the research skill's reference 08) | Bidirectional mark consistency (V033) |

Everything lands under `07_drafting/` (manuscript bodies stay outside the repo; only the
registry and ledgers live here).

## Disclosure thresholds and subject-specific addenda (2025 Guidelines practice)

- **Effect/use data**: effects that cannot be predicted — e.g., a new medical use of a known
  compound — require experimental evidence; a stated goal without the means, or "needs
  experimental proof but none provided", is an "enabling" defect under Art. 26.3
  (Guidelines Part II Ch. 2 §2.1.3). Without data, log it in the open-questions list;
  do not promise effects in the disclosure.
- **AI/algorithm subjects — additional elements** (Guidelines Part II Ch. 9 §6.3.1; claim
  forms in [10](10-claim-drafting.md)):
  - model construction/training: the required **modules, layers or connections** of the model
    and the **concrete steps and parameters** needed for training;
  - model application: how it **combines with the field/scenario** and the **correspondence**
    between input/output data and concrete technical data;
  - effect wording: improved quality, precision, efficiency, or internal system performance
    (less storage/transmission, faster processing); user-experience gains must be attributed
    jointly to technical and algorithm features;
  - counter-example (Guidelines example 21): a cancer-prediction model with no key biomarkers
    named, no verified causality and no validation data fails enablement. For any disclosure
    containing algorithm features, ask three questions first: which concrete technical data
    are the inputs/outputs bound to? are the training parameters complete? is each claimed
    effect verifiable?
- **Clarity wording bans** (Guidelines Part II Ch. 2 §3.2.2): avoid "approximately / close to /
  etc. / and the like" and "for example / preferably / in particular / when necessary" in both
  the specification and the claims — avoid them at draft stage, do not leave them for the OA.

## Say it clearly, or log it

Where the drafting stalls, **do not invent**: record it in
`07_drafting/open_questions.md` (the question, what material is missing, who can supply it).
The open-questions list is part of the deliverable — hand it to the attorney together with
the draft instead of hiding it in the body.

## Kernel hooks

```powershell
patentkit ledger                 # reconcile before writing the background: cite ledger IDs only (V034)
patentkit export-docx <TGT>     # search report docx (disclosure attachment)
patentkit provenance check      # all-green provenance before the embodiments
```

## Boundaries (hard)

- This workflow **does not judge patentability and never predicts grant**;
- run the comparison before drafting prose (see [00](00-prerequisites.md)): skipping the
  comparison means writing the risk into the claims;
- infringement analysis and the software-copyright module are **not done by default**
  (decision records: `docs/scope-decisions.md`).
