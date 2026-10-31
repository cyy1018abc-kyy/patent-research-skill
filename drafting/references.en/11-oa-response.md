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
3. **Amendment strategy** (when necessary): clear the amendment boundary below first —
   - merge dependent-claim features into the independent claim (check the support mapping
     table first);
   - narrow the numerical range (must stay inside grade-A provenance);
   - any amendment → follow the loop in [13](13-revision-loop.md): re-run
     `attest --apply` and the gates.

### Amendment boundary (2025 practice, Guidelines Part II Ch. 8 §5.2)

Art. 33's "recorded range" = the literal original record + what is **directly and unambiguously
derivable** from the text and drawings; foreign-language texts and priority documents are not the
basis. Two red lines:

- **"directed at the defects pointed out"** (Reg. 57.3) — five "not directed at" situations are
  rejected even without new matter: deleting features to broaden, altering features to broaden,
  introducing a subject lacking unity, adding an independent claim, adding a dependent claim;
- **allowed**: narrowing a numerical range within the originally recorded endpoints; a specific
  "disclaimer" only with proof that the disclaimed segment is uninhabitable or that novelty/
  inventive step returns after the disclaimer. **Not allowed**: submitting new experimental
  data/embodiments, turning the vague into the concrete with new content
  ("elevated temperature" → "above 40 °C"), joining two discrete values into a range
  ("10 °C or 300 °C" → "10–300 °C"), new combinations of previously separate features,
  dimensions measured off a drawing.

**Voluntary amendments have exactly two windows** (Reg. 57.2): when filing the examination
request, or within 3 months of the notice of entry into substantive examination; no voluntary
amendments while answering an OA.

## Step 3: the response draft structure

```
I. Overview (agree / partially disagree / observations)
II. Statement of amendments (if any: what changed; no new matter)
III. Response to each clause (one subsection per X: allegation → fact chart → argument → conclusion)
IV. Conclusion (current status of each claim)
```

## Appeal chain after a rejection (2025 practice)

If the OA stage is lost, three stations remain (deadlines are presets in `patentkit deadlines`):

```
rejection decision → reexamination request + fee within 3 months → preliminary review
    (original examining division) → collegial review / reexamination notice
    (1 month to answer) → reexamination decision → appeal within 3 months
```

- **Amendments in reexamination** (Reg. 66): limited to curing the defects cited in the
  rejection or raised by the collegial panel; the scope must not widen — reexamination is a
  correction window, not a second layout opportunity;
- **The preliminary review is winnable**: the original division may withdraw the rejection as
  is, or on the amended text; when drafting, anticipate which "already-notified defect" paths
  the preliminary review would accept and aim the amendments at already-notified facts and
  reasons;
- amendments in reexamination also go through the loop in [13](13-revision-loop.md).

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
