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
5. **Brief description of the drawings + detailed embodiments**: at least one complete
   embodiment; numbers come from grade-A/C sources of the provenance registry, and grade C
   (illustrative example) must be declared explicitly.

## From disclosure to application documents (Implementing Regulations 20–23)

| Document | Basis | Self-check |
|---|---|---|
| Claims | Reg. 20–22: independent/dependent structure, unity | Layered self-check in [10](10-claim-drafting.md) |
| Specification | Reg. 20: five-part structure (field / background / summary / drawings / embodiments) | Every claim has a supporting paragraph (support mapping table) |
| Abstract | ≤300 characters, subject and effect | Length and range declarations |
| Drawings | see `patentkit figures` (full spec in the research skill's reference 08) | Bidirectional mark consistency (V033) |

Everything lands under `07_drafting/` (manuscript bodies stay outside the repo; only the
registry and ledgers live here).

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
