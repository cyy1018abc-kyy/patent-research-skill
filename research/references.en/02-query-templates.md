# 02 Query templates

## Hard rules

1. **A primary query has at most 3 AND sub-queries** — with more, the hit count collapses to single digits.
2. **IPC is a post-filter**; do not write it into the query.
3. **Every sub-query must be narrow.** Because CNIPA returns only 3 records at a time, a broad query wastes an opportunity.
4. **Sub-queries must differ in angle**; do not pad the count with synonymous rewrites.

## What a valid sub-query looks like

```
{ label: short-name, abstract: keywordA and keywordB and keywordC }
```

The three-word combination principle: **domain term × object term × means term**, plus a fourth
angle — the **effect term** (Examination Guidelines 2025, Part II Ch. 7 §5.4.2: basic search
elements are extracted from four aspects — technical field, technical problem, technical means,
technical effect).

| Position | Role | Example (fuel cell / gas-liquid separation) |
|---|---|---|
| Domain term | Restricts the technical field | fuel cell |
| Object term | Restricts the object acted on | gas-liquid separation / water removal / discharge |
| Means term | Restricts the implementation | capillary / staged / dual-threshold |
| Effect term | Opens another batch of sub-queries from the technical effect | flood prevention / water-flood tolerance / water management |

Effect-term sub-queries and means-term sub-queries **differ in angle** (hard rule 4): means terms
look for "how it is done", effect terms for "what it achieves". In the examiner's search practice
these are two independent element groups; missing the effect angle is a hidden cause of
"pool fully judged yet the gate still fails".

**Three-layer keyword expansion** (Examination Guidelines 2025, Part II Ch. 7 §6.3): expand every
core concept along three layers before it enters a sub-query —

| Layer | What to expand | Example (gas-liquid separation) |
|---|---|---|
| Form | part of speech / singular-plural / misspelling variants | separation / separator / gas-liquid |
| Meaning | synonyms / near-synonyms / antonyms / broader-narrower | separation / discharge / dewatering / water blocking |
| Angle | problem wording vs. effect wording | "prevent flooding" vs. "improve drainage efficiency" |

**Two-layer technical field** (Examination Guidelines 2025, Part II Ch. 7 §5.3): search the
**field of origin** first (located by the claim's function/use and embodiments), then extend to
**functionally/application-similar fields** — by **essential function**, not by name: the essential
function of "fuel-cell water management" is "micro-scale two-phase flow control", and the most
dangerous prior art may hide in same-function fields (atomization, condensation, micro-channel
cooling). The application-scenario sub-queries (item 3 below) are a subset of this layer, not all of it.

## Bad vs. good examples

| Bad example | Problem | Good example |
|---|---|---|
| `fuel cell and control` | Too broad; all 3 records are irrelevant | `oxygen makeup and fuel cell and feedforward` |
| `fuel cell` | No object term, no means term | `dead-end and anode and fuel cell` |
| `fuel cell and fuel cell and fuel cell` | Repeated identical words | Meaningless; delete it |
| `(A or B) and C and D and E` | More than 3 AND terms | Split into multiple sub-queries |

## How to accumulate sub-queries

An axis usually needs **10–28** sub-queries to grow the pool to a judgeable size. Accumulate them by:

1. **Starting from each technical feature of the axis**, writing 1–2 sub-queries for each
2. **Starting from synonym families**: Chinese / English / abbreviations / former names
   (after the three-layer expansion: form / meaning / angle)
3. **Starting from application scenarios**: automotive / aviation / aerospace / marine / stationary
4. **Starting from technical effects**: treat effect wording as an independent angle
   (aligned with the four-element practice of the 2025 Guidelines)
5. **Starting from function-similar fields**: different fields sharing the essential function
   (the second layer of the two-layer technical field)
6. **Filling gaps**: turn terms that keep appearing in judged candidates into new sub-queries

## Judging "is the search sufficient?"

Don't go by gut feeling. Look at two numbers:

| Metric | Meaning | Target |
|---|---|---|
| **documents with relevance≥4 per axis** | Effective coverage of that axis | ≥10, and **buffer ≥+3** |
| **whether the pool is 100% judged** | Is there anything left to judge? | Only when fully judged can you say "the problem is not insufficient judging but insufficient searching" |

> **Why the buffer matters**: when the threshold sits exactly at 10, one re-judgment or one exclusion flips the
> gate red. There was once a case of "built a buffer, then had it overturned by our own review" — because the
> buffer had been built on misjudged items.

## Relation to the tools

```powershell
# Show the sub-query plan for one axis
python -m patentkit search-plan --axis N1

# Run only the newly added sub-queries (existing log names will not collide)
python -m patentkit fetch-cnipa --axis N1 --from-library --only 18,19,20
```

Sub-queries are registered under `cnipa_batches` in `01_search_plan/query_library.yml`;
**append them at the end and never renumber the existing entries** — otherwise historical logs will not match.

## Coverage planning (a tool exists since kernel 0.4.0)

"Have we searched enough" no longer needs a manual table check — `queryplan` turns the two
indicators above into per-axis numbers:

```powershell
python -m patentkit queryplan             # all axes: registered vs executed sub-queries, buffer, gaps
python -m patentkit queryplan --axis N1   # one axis
python -m patentkit queryplan --apply     # append suggested skeletons to the query library (append-only)
```

It answers three things:

1. **Registered but never executed**: sub-queries in `cnipa_batches` with no matching execution
   in the logs — run them before talking about supplementary searches;
2. **Buffer state**: per-axis G-S-02 verified counts and buffer (same criteria as
   [05](05-acceptance-gates.md)); zero/insufficient buffer directly yields the
   "supplementary search required" verdict;
3. **Wording drift**: concept groups of the target (topics concept table) where **none of the
   keywords** appear in any registered sub-query — the most common cause of "pool fully judged
   yet the gate still FAILs". For uncovered groups it emits deterministic skeletons
   (`label: auto-<group>`, first two CJK keywords of the group); after `--apply`, a **human
   words them properly** before running — the skeleton is navigation, not a finished query.
