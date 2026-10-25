# 11 Office-action (OA) response skeleton

> Benchmark: patent-oa of patent-disclosure-skill (clause-by-clause Q&A + response draft)
> and the "read claims like an examiner" idea of Claude-Patent-Creator.
> **This workflow produces a response draft and evidence back-links; it is not legal
> advice. Deadlines are set by the official document — check `patentkit deadlines` before
> discussing content.**

## Step 1: split the action into clauses (one row per objection)

After receiving the OA (first office actions are usually answered within 4 months, later
ones within 2 — counted from the mailing date), split each objection into:

| Clause | Type | Claims affected | Citations used | Alleged defect |
|---|---|---|---|---|
| X1 | Novelty (A22.2-type allegation) | claim 1 | D_oa1 (examiner's document number) | single document covers all features |
| X2 | Inventive step (A22.3-type allegation) | claims 2–5 | D_oa1+D_oa2 | combination obvious |
| X3 | Clarity/support (A26.4-type allegation) | claim 3 | — | term / number unsupported |

**Ledger first**: if the examiner's documents are not yet candidates, add them to
`03_candidates/` first (one targeted sub-query per the research skill's query discipline,
with raw/ archived), then bring them into the comparison. **Documents outside the evidence
ledger do not participate in the argumentation (V034 discipline).**

## Step 2: link every clause back (reusing the search assets)

The response skeleton for each X is the three-tier determination applied in reverse:

1. **Feature chart**: claim features × examiner's documents, one cell per
   "disclosed / not disclosed" — reuse the format of `assets/blank_comparison_matrix.md`,
   quoting the original text in every cell;
2. **Choice of argument** (per the three-tier framework):
   - no single document covers all features → novelty holds (find the zero-disclosure atoms);
   - the combination lacks a motivation to combine / teaches away → inventive step holds;
   - the technical effect presupposes the distinguishing features → effect argument
     (cite the quantified column-D data);
3. **Amendment strategy** (when necessary):
   - merge dependent-claim features into the independent claim (check the support mapping
     table first);
   - narrow the numerical range (must stay inside grade-A provenance);
   - any amendment → follow the loop in [13](13-revision-loop.md): re-run
     `attest --apply` and the gates.

## Step 3: the response draft structure

```
I. Overview (agree / partially disagree / observations)
II. Statement of amendments (if any: what changed; no new matter)
III. Response to each clause (one subsection per X: allegation → fact chart → argument → conclusion)
IV. Conclusion (current status of each claim)
```

## Kernel hooks

```powershell
patentkit deadlines list             # deadlines first (official mailing date prevails)
patentkit ledger                     # cite only evidence inside the ledger
patentkit map <TGT>                 # coverage overview (for the attorney)
python -m patentkit provenance check # if the amendments touch numbers
```

## Boundaries (hard)

- **No grant predictions, never "will certainly be granted"**;
- when unsure how a clause is classified, mark it "attorney to confirm" instead of
  interpreting the statute for the examiner;
- desensitized historical cases may live in `04_comparative_analysis/runs/` as reference,
  but **never** paste pending case content into any public cloud client
  (confidentiality boundary, see the research skill's README).
