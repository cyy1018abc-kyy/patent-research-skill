---
name: patent-research
description: >
  Patent prior-art searching, novelty/inventive-step self-checks, and management of the search
  evidence chain and acceptance gates (G-S).
  When tools are unavailable or not running, answers must begin with "⚠️ Unverified by tool checks".
  Use when the user wants to run a patent search, find prior art, assess novelty/inventive step,
  verify whether the search evidence is sufficient, judge whether the acceptance gates are PASS,
  check evidence levels (verified/attested/asserted), organize search records, or cross-check
  claims and specification before hand-off.
  Supports multi-target workspaces; prefer triggering on phrases such as "run a novelty check",
  "N1 axis query", "supplementary search", "are the five acceptance gates PASS",
  "can asserted be used as evidence", or "evidence level".
license: Apache-2.0
metadata:
  version: 3.11.0
---

# Patent Research

> **Companion**: `patentkit >= 0.10.0` with assessment protocol 1 (the single implementation of rules) + this package's `scripts/` (thin wrappers).
> **Note**: this file mirrors the authoritative Chinese `../SKILL.md` (Chinese-primary since 2.5.0;
> since 3.0.0 the drafting/OA references live in the sibling patent-drafting skill,
> mirrored under `../../drafting/references.en/`).
> You can still work from `references/` without the tools, but conclusions must be marked "⚠️ Unverified by tool checks".

## When to use

| Use | Do not use |
|---|---|
| Prior-art search over patents/papers; recall and precision | Drafting the body of claims/specification (run the 04 comparison first, then return to the manuscript) |
| **Preliminary** judgments of novelty and inventive step | Issuing legal opinions; standing in for a patent attorney or examiner |
| Organizing search records; checking the acceptance gates (G-S) | Answering isolated questions about statutes/procedure (consult official sources; not this workflow) |
| Evidence sufficiency before hand-off; cross-checking numerical support for claims | Editing the target patent text (this workflow only reports gaps and risks) |

## Execution order (follow the sequence; do not skip)

**First read [`references/04-evidence-level-system.md`](04-evidence-level-system.md)** — it is the prerequisite for understanding everything else:
if you cannot tell "self-report" from "evidence", every later step will produce false PASSes.

| # | Stage | Read | Do | Checkpoint |
|---|---|---|---|---|
| 0 | Locate and self-check | — | `python scripts/status.py` (`patentkit status` if scripts are unavailable) | Workspace and `active_target` correct; validation has no error |
| 1 | Broad search | [`01-search-framework.md`](01-search-framework.md) | `patentkit search-plan --axis N1` → `patentkit fetch-cnipa` / `fetch-crossref` → `patentkit ingest --apply` | **G-S-01**: patents ≥200 + literature ≥200 (verified column) |
| 2 | Deep search | [`02-query-templates.md`](02-query-templates.md), [`07-assessment-protocol.md`](07-assessment-protocol.md) | Export JSON → supported AI/human assessment → `patentkit review assess ... --apply` | **G-S-02**: ≥10 eligible documents per axis, buffer ≥+3; both dimensions need original-text support |
| 3 | Comparative analysis | [`03-three-tier-determination.md`](03-three-tier-determination.md) | AI recommends → human reviews explicit IDs/fingerprints → `patentkit review confirm ... --by <human> --apply` → report | **G-S-03** ≥5 documents with valid human confirmation; **G-S-04** families/citations complete |
| 4 | Gate checks | [`05-acceptance-gates.md`](05-acceptance-gates.md) | `python scripts/gates.py` (or `patentkit gates`) | All five gates PASS on the **verified column**; asserted does not count |
| 5 | Hand-off checks | [`06-drafting-and-polishing-rules.md`](06-drafting-and-polishing-rules.md) | `python scripts/check.py` + `patentkit attest --check` | validate 0 error/warn; no manuscript sha256 drift |

> **Where the scripts are**: `scripts/` lives under the skill's **install directory** (e.g.
> `~/.claude/skills/patent-research/scripts/` or `~/.agents/skills/patent-research/scripts/`),
> **not in the workspace**. Locate the skill directory before running them, or call the equivalent
> `patentkit <subcommand>`.
>
> Fix gaps only by looping between stages 1, 2, and 3: **a failed gate means the search is not
> sufficient**, not that the criteria should be changed.

## Hard constraints (must not be violated)

1. **Do not tag `verified` without the `raw/` original artifact** — validation rules V009/V013 block it.
2. **Gate PASS is only recognized on the strictest `verified` column**; `asserted` is historical record, not a basis for passing.
3. **Source provenance and judgment are separate.** Keep `evidence_level` unchanged when assessing. AI may score G-S-02 only with per-axis problem/means quotations, locators and rationales; abstract or body text is acceptable when sufficient. AI may recommend `near_prior_art`, but G-S-03 requires explicit human confirmation of named IDs and current fingerprints. Never impersonate a human reviewer or treat a vague reply as confirmation. AI conflicts are proposals and never overwrite human decisions. Substantive changes invalidate confirmation; unrelated metadata corrections do not.
4. **When tools are unavailable / not running**, **the answer must explicitly start with "⚠️ Unverified by tool checks"**, then give methodological advice; do not omit it, and do not disguise the result as verified.
5. **Hit count ≠ core-document count**: a database's `hits` is its whole-library hit surface, not "found N documents".
6. **A primary query has at most 3 AND sub-queries**; use IPC as a post-filter, not inside the primary query.
7. **A gate FAIL is not "think it over"** — it means "the search is insufficient": prioritize supplementary searching/determination, not loosening thresholds.
8. **Quantity thresholds live in `patentkit/gates.py`; shared judgment eligibility lives in `patentkit/assessment.py`, called by gates and validation.** This file, references and wrappers explain these rules and must not implement a second set.

## Result format (use this whenever you report research conclusions; nothing may be omitted)

| Item | Requirement |
|---|---|
| **Conclusion** | State explicitly "holds / doubtful / does not hold" (for novelty, inventive step, or evidence sufficiency); **do not conclude whether a patent can be granted** |
| **Evidence level** | Source provenance only: `verified` / `attested` / `asserted`; external hash-bound material may be attested; report the judgment actor separately |
| **Assessment status** | Show actor, per-axis original-text basis and valid/pending/stale human confirmation separately; source `verified` never guarantees judgment correctness |
| **Gate status** | Cite the actual value from the `verified` column (e.g. G-S-02 minimum axis 12 documents); do not write "should pass" |
| **Unverified annotation** | When tools have not run or data is incomplete, explicitly write "⚠️ Unverified by tool checks; the following is methodological advice" |

Example (values are placeholders; do not copy):

```text
Conclusion: per-document novelty — doubtful (D3 covers N2/N5, not N4)
Evidence level: verified (25 closest prior-art documents, raw/ complete)
Gates: G-S-01 ✅ 210P/205L ｜ G-S-02 ✅ minimum axis 12 ｜ G-S-03 ✅ 25 ｜ G-S-04 ✅ 25/25 ｜ G-S-05 ✅ 100%
Unverified: none
```

## References (load on demand; do not read everything at once)

| File | When to read |
|---|---|
| [`04-evidence-level-system.md`](04-evidence-level-system.md) | **Read first**; before judging PASS or tagging an evidence level |
| [`01-search-framework.md`](01-search-framework.md) | Building the domain, starting a new project, collection discipline |
| [`02-query-templates.md`](02-query-templates.md) | Constructing queries, rewriting them for each database's syntax |
| [`03-three-tier-determination.md`](03-three-tier-determination.md) | Judging relevance, writing the comparison matrix and three-tier conclusions |
| [`05-acceptance-gates.md`](05-acceptance-gates.md) | A gate fails, the buffer is insufficient, or `validate` reports errors |
| [`06-drafting-and-polishing-rules.md`](06-drafting-and-polishing-rules.md) | Cross-checking claim-specification values/support before hand-off |
| [`07-assessment-protocol.md`](07-assessment-protocol.md) | Assessment imports, explicit batch confirmation, conflicts, fingerprints and migration |
| [`08-figures.md`](08-figures.md) | Figure standards, mark cross-checks (V033), figure–text consistency |
| [`../references/glossary.md`](../references/glossary.md) | zh⇄en glossary (byte-identical copies across both skills) |
| 09–13 (disclosure / claims / OA / policy radar / revision loop) | moved to the patent-drafting skill; English mirrors in `../../drafting/references.en/` |

> See this package's [`README.md`](README.md) for `scripts/` and installation instructions. The scripts are only thin wrappers around `patentkit`;
> the rules are not implemented in them. If `patentkit` is not installed, the scripts print installation guidance (exit 3).
