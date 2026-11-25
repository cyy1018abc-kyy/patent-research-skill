# 21 · Manuscript consistency lint (`draft lint`, 4.3 / M2)

> The structured pipeline (14/15) checks the **model** (atoms, claims, support mapping); this file
> defines the machine checks on the **manuscript text**
> (`07_drafting/manuscript/{claims,specification,abstract}.md`): does the text agree with the
> structured model, and does it meet the formal drafting requirements? Error-level findings block
> delivery (`deliver build` refuses, `deliver check` reports E-016); heuristic checks only warn and a
> human decides. The tool never judges grantability and does not replace attorney review.

## 1. Commands

```powershell
python -m patentkit draft lint --root .\workspace          # human-readable report
python -m patentkit draft lint --root .\workspace --json   # machine-readable
```

Before any manuscript exists, only one M-001 warning is reported; no gate is blocked.

## 2. Codes

| Code | Level | Meaning | Basis |
|---|---|---|---|
| M-001 | error | manuscript file missing, no numbered claims/paragraphs, empty abstract | delivery inputs (17) |
| M-002 | error | `claims.md` numbers duplicated/not consecutive, or different from the structured claims | structured model (15) |
| M-003 | error/warn | a dependent claim has no reference wording, refers to a claim other than its structured parent, or to a missing/later claim (error); multiple dependency where the structure records one parent (warn) | references must match the structure |
| M-004 | error/warn | duplicate paragraph numbers (error); numbering not consecutive from `[0001]` (warn) | paragraph numbering convention |
| M-005 | warn | the five description parts (technical field / background / summary of the invention or utility model / description of drawings / detailed description) are missing or out of order; no drawings → no drawing-description part required | Implementing Regulations, description clause (check the current official text for article numbers) |
| M-006 | error | abstract longer than 300 characters (whitespace excluded) | Implementing Regulations, abstract clause |
| M-007 | warn | title longer than 25 characters (general requirement) | Examination Guidelines Part II Chapter 2 |
| M-008 | warn | vague wording in claims: about/approximately/close to + number, number + "or so", for example, preferably, especially, when necessary, analogues, "etc." | Examination Guidelines Part II Chapter 2 (claims must be clear) |
| M-009 | warn | antecedent-basis heuristic: "said X" with no earlier mention of X in the claim or the claims it refers to | drafting practice; heuristic, may misfire |
| M-010 | warn | reference signs in claims are not in parentheses ("housing 1" should be "housing (1)") | Implementing Regulations, claims clause |
| M-011 | error | a part name is used with a reference sign that the figure plans (`mark_mapping`) do not assign to it (claims or description) | consistent reference signs |
| M-012 | warn | subject wording or summary heading of the wrong application type ("the invention" in a utility model, or vice versa) | reference 20 |
| M-013 | error | a figure plan is not described in the description (restricted to the drawing-description part when present), or the text cites a figure without a plan | Implementing Regulations, description clause |
| M-014 | warn | claims say "as shown in Fig. …" / "as described in the description" | Implementing Regulations, claims clause (only when absolutely necessary) |
| M-015 | error/warn | a claim uses a full stop other than at its end (error); a claim does not end with one (warn) | Examination Guidelines Part II Chapter 2 (one full stop, at the end) |
| M-016 | error | the manuscript still contains `【待补：…】` slots left by `draft render` | [22](22-manuscript-render.md): an unfilled skeleton cannot be delivered |

> Legal anchors are cited only to the level that can be checked (named clauses, guideline
> chapters); the 2023 revision renumbered the Implementing Regulations, so this file **never
> invents article numbers** — check the current official text and record it in `docs/policy-log.md`.

## 3. Writing conventions (so the lint can read the text)

- Claims: one paragraph per claim starting with `1. `; a dependent claim says "根据权利要求N所述的……"
  with N equal to the structured `parent_claim_no`; reference signs in parentheses: `壳体(1)`.
- Description: the five part headings **on their own lines** (a leading `#` is fine); paragraphs start
  with `[0001]` and are numbered consecutively; the drawing-description part describes each figure ("图N为……").
- Abstract: at most 300 characters; utility models say "本实用新型", inventions "本发明".

## 4. Relation to the delivery gate

- `deliver build`: structural refusals from the frozen model come first (missing files, numbering,
  paragraphs, figure ids), then the lint; any error refuses the build.
- `deliver check`: lint errors are listed as **E-016**; editing the manuscript after sign-off so that
  the lint fails demotes the delivery as well.
- Warnings do not block, but review each before delivery (especially M-009 antecedent basis and
  M-008 vague wording).

## 5. Accuracy evidence

The drafting benchmark (`benchmarks/drafting/`, synthetic): one clean manuscript (must yield zero
findings) and one seeded-defect manuscript each for utility models and inventions; CI locks
"every seeded defect detected, zero false positives" with `tools/score_drafting.py --gate perfect`.
The benchmark only shows the rules work as designed on synthetic drafts — it is not a promise of
zero false positives on real manuscripts; heuristic results still need human judgement.
