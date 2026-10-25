# 05 Acceptance-gate criteria

> **The criteria are codified in code**: `patentkit/gates.py`, computed with `python -m patentkit gates`.
> Each gate is computed once per evidence level; **PASS is recognized only on the strictest `verified` column** (see `04-evidence-level-system.md`).

## Criteria of the five gates

| Gate | Criterion | Threshold |
|---|---|---|
| **G-S-01** | Stage 1 candidate list | **≥200 patents + ≥200 literature** (counted by `kind`) |
| **G-S-02** | Stage 2 main-axis coverage | **≥10 documents per axis** with a current supported AI/human assessment, both dimensions ≥4 and per-axis original-text citations; excluded does not count |
| **G-S-03** | Stage 3 closest prior art | **≥5 documents** with `role=near_prior_art` and a valid explicit human confirmation bound to the current judgment fingerprint |
| **G-S-04** | Families and citations complete | For `role ∈ {near_prior_art, family}`, both `family` and `cited_by` are **arrays and non-empty** |
| **G-S-05** | Replayability | `capture_mode=live` and `raw/` artifact exists and is non-empty **100%** |

## Two historical criteria corrections (the original criteria were wrong)

1. **G-S-03** originally said "count of `novelty_check = blocking` ≥ 5" — **wrong**.
   `blocking` (whether novelty is blocked) and "the number of closest prior-art documents" are two different
   semantics. It now counts `role=near_prior_art`, decoupling the two.

2. **G-S-04** originally hard-coded "existing patent 1, patent 2" — **not generalizable**.
   It now references the comparison-document set of the target patent itself.

## Buffer discipline for G-S-02

`G-S-02` is the gate most likely to "just pass and then flip red".

| State | Meaning | Action |
|---|---|---|
| documents with ≥4 on an axis = 10 | zero buffer; one re-judgment causes FAIL | **must run supplementary searches** |
| an axis = 11–12 | buffer +1 to +2; still fragile | recommend topping up to +3 |
| an axis ≥ 13 | buffer +3 or more | safe |

**How to top it up**: first check whether that axis's pool is 100% judged — if it is, the problem is not
"insufficient judging" but "insufficient searching", and only new sub-queries can help. Run
`python -m patentkit queryplan --axis <axis>`: it reports registered-but-unexecuted sub-queries,
concept-group coverage gaps, and deterministic supplementary-query skeletons (see [02](02-query-templates.md)).

## Difference between validate and gates

| | What it governs | Consequence of failure |
|---|---|---|
| `validate` | **Data-structure consistency** (V001–V036) | any `error` → exit 1 |
| `gates` | **Acceptance gates** (5 gates × 3 columns) | any gate not PASS → exit 2 |

V029 checks assessment provenance/support; V030 reports stale human confirmation. V031/V032 govern
numerical-claim provenance, V033 figure marks (warn only), V034 blocks conclusions citing IDs outside
the evidence ledger, V035/V036 govern the revision ledger (invalid structure / unlogged edit).
Source provenance and judgment eligibility are independent. See [07-assessment-protocol.md](07-assessment-protocol.md).

Both must pass. The CI entry point is `python -m patentkit check` (= `validate --strict` + `gates --quiet`).

## Common FAIL causes and fixes

| Symptom | Cause | Fix |
|---|---|---|
| G-S-01 literature side 0 | Only patent searching was done | Use `fetch-crossref` to add literature |
| G-S-02 one axis has 9 documents | The pool is fully judged | Add sub-queries; do not re-judge |
| G-S-03 N/A | All `role` values are `pool` | Obtain supported recommendations, then human-confirm explicit candidate IDs and current fingerprints |
| G-S-04 N/A | Same as above (no `near_prior_art`) | Same as above |
| G-S-05 <100% | Some logs lack `raw/` | Re-run that search |
| `validate` reports V018 | `near_prior_art` did not enter any run | Run `patentkit report <TGT-ID>` |
