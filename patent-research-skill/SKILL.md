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
  version: 2.3.3
---

# Patent Research

> **Companion**: `patentkit` (the Python core where the rules are implemented) + this package's `scripts/` (thin wrappers).
> You can still work from `references/` without the tools, but conclusions must be marked "⚠️ Unverified by tool checks".

## When to use

| Use | Do not use |
|---|---|
| Prior-art search over patents/papers; recall and precision | Drafting the body of claims/specification (run the 04 comparison first, then return to the manuscript) |
| **Preliminary** judgments of novelty and inventive step | Issuing legal opinions; standing in for a patent attorney or examiner |
| Organizing search records; checking the acceptance gates (G-S) | Answering isolated questions about statutes/procedure (consult official sources; not this workflow) |
| Evidence sufficiency before hand-off; cross-checking numerical support for claims | Editing the target patent text (this workflow only reports gaps and risks) |

## Execution order (follow the sequence; do not skip)

**First read [`references/04-evidence-level-system.md`](references/04-evidence-level-system.md)** — it is the prerequisite for understanding everything else:
if you cannot tell "self-report" from "evidence", every later step will produce false PASSes.

| # | Stage | Read | Do | Checkpoint |
|---|---|---|---|---|
| 0 | Locate and self-check | — | `python scripts/status.py` (`patentkit status` if scripts are unavailable) | Workspace and `active_target` correct; validation has no error |
| 1 | Broad search | [`01-search-framework.md`](references/01-search-framework.md) | `patentkit search-plan --axis N1` → `patentkit fetch-cnipa` / `fetch-crossref` → `patentkit ingest --apply` | **G-S-01**: patents ≥200 + literature ≥200 (verified column) |
| 2 | Deep search | [`02-query-templates.md`](references/02-query-templates.md) | `patentkit review export --with-abstract` → **human determination** → `patentkit review apply --apply` | **G-S-02**: ≥10 documents with relevance≥4 per axis, plus buffer ≥+3 |
| 3 | Comparative analysis | [`03-three-tier-determination.md`](references/03-three-tier-determination.md) | `patentkit report <TGT-ID>` → fill in per-document / combination / technical-effect layers | **G-S-03** ≥5 closest prior-art documents; **G-S-04** families/citations complete |
| 4 | Gate checks | [`05-acceptance-gates.md`](references/05-acceptance-gates.md) | `python scripts/gates.py` (or `patentkit gates`) | All five gates PASS on the **verified column**; asserted does not count |
| 5 | Hand-off checks | [`06-drafting-and-polishing-rules.md`](references/06-drafting-and-polishing-rules.md) | `python scripts/check.py` + `patentkit attest --check` | validate 0 error/warn; no manuscript sha256 drift |

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
3. **Do not decide `relevance` / `role` for the user.** When the model makes a determination, it must write "[Model-determined]" + rationale in `review_note`, and the conclusion is downgraded to `asserted`.
4. **When tools are unavailable / not running**, **the answer must explicitly start with "⚠️ Unverified by tool checks"**, then give methodological advice; do not omit it, and do not disguise the result as verified.
5. **Hit count ≠ core-document count**: a database's `hits` is its whole-library hit surface, not "found N documents".
6. **A primary query has at most 3 AND sub-queries**; use IPC as a post-filter, not inside the primary query.
7. **A gate FAIL is not "think it over"** — it means "the search is insufficient": prioritize supplementary searching/determination, not loosening thresholds.
8. **Thresholds and determination criteria live only in `patentkit/validate.py` and `patentkit/gates.py`**; this file and `references/` only explain them and must not introduce a second set of criteria.

## Result format (use this whenever you report research conclusions; nothing may be omitted)

| Item | Requirement |
|---|---|
| **Conclusion** | State explicitly "holds / doubtful / does not hold" (for novelty, inventive step, or evidence sufficiency); **do not conclude whether a patent can be granted** |
| **Evidence level** | `verified` / `attested` / `asserted`; anything whose source is not `raw/` is `asserted` |
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
| [`04-evidence-level-system.md`](references/04-evidence-level-system.md) | **Read first**; before judging PASS or tagging an evidence level |
| [`01-search-framework.md`](references/01-search-framework.md) | Building the domain, starting a new project, collection discipline |
| [`02-query-templates.md`](references/02-query-templates.md) | Constructing queries, rewriting them for each database's syntax |
| [`03-three-tier-determination.md`](references/03-three-tier-determination.md) | Judging relevance, writing the comparison matrix and three-tier conclusions |
| [`05-acceptance-gates.md`](references/05-acceptance-gates.md) | A gate fails, the buffer is insufficient, or `validate` reports errors |
| [`06-drafting-and-polishing-rules.md`](references/06-drafting-and-polishing-rules.md) | Cross-checking claim-specification values/support before hand-off |

> See this package's [`README.md`](README.md) for `scripts/` and installation instructions. The scripts are only thin wrappers around `patentkit`;
> the rules are not implemented in them. If `patentkit` is not installed, the scripts print installation guidance (exit 3).
