# Search report template

> Copy as `<date>_<target-ID>_search_report.md`, to accompany the comparison run under `04_comparative_analysis/runs/`.
> Every number must be recomputable by `patentkit gates` / `validate`; where handwritten numbers disagree with the tools, the tools win.

## 1. Target and scope

| Item | Content |
|---|---|
| Target ID | `<TGT-xxxx>` |
| Invention title | `<title>` |
| Search purpose | Novelty self-check / inventive-step self-check / infringement-risk screening / pre-hand-off verification |
| Time window | last 10 years (or state the exception) |
| Databases | CNIPA / Espacenet / WIPO / Google Patents / Crossref / arXiv / others |

## 2. Queries and execution record

| Axis/combination | Query (reproducible verbatim) | Database | Hit count (site) | Captured count | raw/ artifact | Log |
|---|---|---|---|---|---|---|
| N1 |  |  |  |  |  |  |

> Rule: every search must leave the `raw/` raw response + a log; incomplete collection must be declared with `result.complete=false`.
> If either is missing → `validate` V009/V013 blocks it, and `verified` may not be tagged.

## 3. Candidate statistics

| Dimension | Value |
|---|---|
| Total candidates |  |
| Patents / literature |  |
| Evidence-level distribution | verified:  / attested:  / asserted:  |
| Supported per-axis judgments with both dimensions ≥4 (G-S-02) |  |
| Judgment state distribution | unknown / needs_review / ai_assessed / human_assessed / human_confirmed |
| Closest prior-art documents (role=near_prior_art) |  |

## 4. Gate status (verified column only)

| Gate | Criterion | verified actual | Status |
|---|---|---|---|
| G-S-01 | patents ≥200 + literature ≥200 |  |  |
| G-S-02 | ≥10 documents with relevance≥4 per axis | minimum axis:  documents |  |
| G-S-03 | ≥5 closest-prior-art documents with valid human confirmation |  |  |
| G-S-04 | families/citations complete |  |  |
| G-S-05 | replayability 100% |  |  |

> Recompute with: `python scripts/gates.py` (or `patentkit gates`). PASS is based on the `verified` column only.

## 5. Three-tier determination conclusions

### 5.1 Per-document novelty

- Conclusion: holds / doubtful / does not hold
- Key comparison documents and coverage:
- Evidence level:

### 5.2 Combination inventive step

- Conclusion: holds / doubtful / does not hold
- Combination (D_a + D_b + …) and motivation to combine:
- Zero-disclosure atoms (features that no combination of the comparison documents can assemble):
- Self-attack (the examiner's most likely objections and responses):
- Evidence level:

### 5.3 Technical effect

- Conclusion: holds / doubtful / does not hold
- Non-obvious technical effects and supporting data:
- Evidence level:

## 6. Risks and recommendations

| Risk | Level | Treatment |
|---|---|---|
|  | high/medium/low |  |

## 7. Unverified items and notes

- [ ] Have all tools been run? List every part that was not run, item by item
- [ ] Are there any conclusions supported only by `asserted`?
- [ ] Are source grades and judgment actors reported separately, without downgrading genuine sources because AI participated?
- [ ] Does each G-S-02 axis have problem/means quotations, locators and rationale?
- [ ] Do G-S-03 rows have explicit human confirmation for the current fingerprint, with stale records excluded?

> Any statement of an unverified conclusion must carry "⚠️ Unverified by tool checks".
