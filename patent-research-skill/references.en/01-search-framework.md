# 01 Search framework: a three-stage progression

## Stage 1: Broad search (domain building)

- **Goal**: build a panoramic map of the target technical field
- **Databases**
  - Patents: CNIPA / Espacenet / WIPO PATENTSCOPE / Google Patents
  - Literature: Crossref (covers Elsevier/Springer/Wiley/IEEE, free, no key) / arXiv / DOAJ
  - Chinese: CNKI / Wanfang / VIP
- **Queries**: Chinese A1–A3 + English B1–B3
- **IPC scope**: determined by the target field (e.g. PEMFC: `H01M8`, `H02J3`, `B64G1`)
- **Time window**: the last 10 years
- **Deliverables**: candidate list (200–500 patents + 200–500 literature) + topic clustering + ranking of main applicants

## Stage 2: Deep search (axis-by-axis expansion)

- **Goal**: design a dedicated query for each independent technical feature of the main axes
- **Axis names are defined authoritatively only by `00_methodology/glossary.yml`** — never introduce a separate abbreviation in another file
- **Combination search**: pairwise combinations of key technical features (C1 = N1+N2, etc.)
- **Citation-chain expansion**: forward + backward citations; family members and cited-by lists
- **Deliverables**: 20–50 core documents per axis + Top 10 closest prior-art documents

## Stage 3: Comparative analysis (verifying novelty + inventive step)

- **Goal**: compare item by item against candidate closest prior art to verify novelty and inventive step
- **Matrix**: N axes × M comparison documents
- **Three-tier determination**: see `03-three-tier-determination.md`
- **Deliverables**: search report + comparison matrix + list of proposed amendments + risk level

## Measured reachability (measured 2026-10; for reference)

| Source | Status | Notes |
|---|---|---|
| CNIPA | ✅ | **Returns at most 3 records per query**; programmatic paging is blocked, so hits can only be accumulated through many sub-queries |
| Crossref | ✅ | 150M+ DOIs, free, no key; `filter=type:journal-article` is mandatory |
| arXiv / DOAJ | ✅ | Preprints / open-access journals |
| Google Patents | ✅ | Can supplement abstracts; occasional rate limiting |
| OpenAlex | ⚠️ | Per-DOI queries work; **the search endpoint returns 429** |
| Semantic Scholar | ⚠️ | Per-DOI queries work but continuously return 429; the search endpoint is unusable |

> **CNIPA's 3-record cap** is the easiest trap to fall into: a query returning 3 records does not mean that
> only 3 documents exist; it must be split into many narrow sub-queries that accumulate (this project used up
> to 28 sub-queries on a single axis).

## Collection discipline

1. **Every search must persist two things**: the `raw/` raw response + `02_search_logs/*.log.json`.
   If either is missing, `validate` blocks it (V009/V013).
2. **Logs must truthfully declare whether collection was complete**: `result.complete = false` + explanation.
   Declaring incomplete collection → `validate` downgrades it to info; **leaving it undeclared while collection
   was actually incomplete → warn** (V026).
3. **Long batch jobs must persist incrementally**. A job once ran over two hundred items before being killed,
   and all 166 fetches were lost.
