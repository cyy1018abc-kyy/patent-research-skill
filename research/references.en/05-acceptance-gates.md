# 05 Acceptance-gate criteria

> **The criteria are codified in code**: `patentkit/gates.py`, computed with `python -m patentkit gates`.
> Each gate is computed once per evidence level; **PASS is recognized only on the strictest `verified` column** (see `04-evidence-level-system.md`).

## Criteria of the five gates

| Gate | Criterion | Threshold |
|---|---|---|
| **G-S-01** | Stage 1 candidate list | **≥200 patents + ≥200 literature** (counted by `kind`) |
| **G-S-02** | Stage 2 main-axis coverage | **≥10 documents per axis** with a current supported AI/human assessment, both dimensions ≥4 and per-axis original-text citations; excluded does not count |
| **G-S-03** | Stage 3 closest prior art | **≥5 documents** with `role=near_prior_art` and a valid explicit human confirmation bound to the current judgment fingerprint |
| **G-S-04** | Families and citations censused | For `role ∈ {near_prior_art, family}`, one **valid census record** per dimension (queried + raw artifact archived and hash-bound); **zero hits count as queried** |
| **G-S-05** | Replayability | `capture_mode=live` and `raw/` artifact exists and is non-empty **100%** |

## Three historical criteria corrections (the original criteria were wrong)

1. **G-S-03** originally said "count of `novelty_check = blocking` ≥ 5" — **wrong**.
   `blocking` (whether novelty is blocked) and "the number of closest prior-art documents" are two different
   semantics. It now counts `role=near_prior_art`, decoupling the two.

2. **G-S-04** originally hard-coded "existing patent 1, patent 2" — **not generalizable**.
   It now references the comparison-document set of the target patent itself.

3. **G-S-04** later only checked that `family`/`cited_by` were arrays — two empty arrays could PASS,
   leaving **"not queried" and "queried, zero hits" indistinguishable**; the literal "non-empty arrays"
   wording also made a genuine zero-hit lookup permanently incomplete. Since 0.6.0 the gate verifies a
   **census record** (see below).

## The G-S-04 census record

Each census subject carries a `census` field in its candidate JSON, recorded **separately per dimension**:

| Field | Meaning |
|---|---|
| `doc_number` | The queried publication number (matches the candidate's `url_or_doc_number` after normalization) |
| `source` / `query_id` | Source database and query family (e.g. `BQ` / `GS04`; hand lookups record the actual source) |
| `at` | Query time (ISO 8601 with timezone) |
| `status` | `complete` (queried, hits) / `zero_hits` (queried, no hits) / `partial` / `failed` (query did not finish) |
| `artifact` + `artifact_sha256` | Raw artifact (workspace-relative, usually under `02_search_logs/raw/`) and its hash |

Gate decision (implemented in `patentkit/census.py`; the gate only calls it):

| Situation | G-S-04 |
|---|---|
| Not queried (no record) | ❌ incomplete |
| Queried, zero hits, artifact archived and hash matches (`zero_hits`) | ✅ counts as complete |
| Queried, hits, artifact archived and hash matches (`complete`) | ✅ counts as complete |
| `partial` / `failed` / artifact missing / artifact modified (hash mismatch) / record points at another query's artifact | ❌ must not masquerade as complete |

How records are written: `python -m patentkit fetch-bigquery --fill <raw.jsonl> --apply` — the artifact
archived by `fetch-bigquery --run` carries **one row per queried doc** (zero hits included), and the fill
generates the records automatically. Other sources (OPS, manual epub lookups): add the `census` fields by
hand per the table above (artifact = the actually archived raw file; hash = the same sha256 as
`patentkit ledger`), and run `patentkit migrate` first on older workspaces to refresh the candidate schema.

A record that **exists but is broken** (missing fields / hash mismatch / status contradicting the artifact)
is blocked by validate **V037**; an honest `partial`/`failed` is not data corruption — validate stays quiet,
but the gate refuses to count it as complete. "Not queried" and "queried but unfinished" both mean the
search is insufficient: fix it by searching, not by loosening the criteria.

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
| `validate` | **Data-structure consistency** (V001–V037) | any `error` → exit 1 |
| `gates` | **Acceptance gates** (5 gates × 3 columns) | any gate not PASS → exit 2 |

V029 checks assessment provenance/support; V030 reports stale human confirmation. V031/V032 govern
numerical-claim provenance, V033 figure marks (warn only), V034 blocks conclusions citing IDs outside
the evidence ledger, V035/V036 govern the revision ledger (invalid structure / unlogged edit), and V037
governs census-record integrity (a broken `census` → error; honest incompleteness → the gate's domain).
Source provenance and judgment eligibility are independent. See [07-assessment-protocol.md](07-assessment-protocol.md).

Both must pass. The CI entry point is `python -m patentkit check` (= `validate --strict` + `gates --quiet`).

## Common FAIL causes and fixes

| Symptom | Cause | Fix |
|---|---|---|
| G-S-01 literature side 0 | Only patent searching was done | Use `fetch-crossref` to add literature |
| G-S-02 one axis has 9 documents | The pool is fully judged | Add sub-queries; do not re-judge |
| G-S-03 N/A | All `role` values are `pool` | Obtain supported recommendations, then human-confirm explicit candidate IDs and current fingerprints |
| G-S-04 N/A | Same as above (no `near_prior_art`) | Same as above |
| G-S-04 FAIL "not queried" | A census subject has no census record | Run `fetch-bigquery --fill <artifact> --apply`, or add the record by hand per the census table |
| G-S-04 FAIL "hash mismatch" | Artifact modified / record stale | Re-run the census for a fresh artifact and `--fill` again; never hand-edit the hash |
| G-S-05 <100% | Some logs lack `raw/` | Re-run that search |
| `validate` reports V018 | `near_prior_art` did not enter any run | Run `patentkit report <TGT-ID>` |
| V037 error | Census record exists but is broken | Re-run `fetch-bigquery --fill` (the artifact is the only authority); hand-written records are repaired per the table |
