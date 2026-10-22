# 04 Evidence-level system

> **This is the prerequisite for understanding everything else.** Without understanding this file, you will mistake "self-report" for "evidence".

## Why this system is needed

The most common failure in a patent research project is not "too little searching" but **being unable to tell which conclusions are supported and which are merely asserted**.

History has an example: the project once self-assessed "all five gates PASS" on the basis of `asserted` (memory injected from recall), while the `verified` side was actually **0**. Under the current system that result is retained in the `≥asserted` column, but it **does not constitute a basis for PASS**.

## Three levels

| Level | Meaning | Criterion | Usable for PASS |
|---|---|---|---|
| **`verified`** | A **replayable raw artifact** exists in the repo | `raw/` file exists, is non-empty, `capture_mode=live` | ✅ **only this one** |
| `attested` | External data + in-repo sha256 binding | Has `evidence_ref` and `evidence_sha256` | ❌ |
| `asserted` | Pure self-report (written by a person, written by a model, recalled from memory) | No other requirement | ❌ |

**Key point**: `attested` proves "which file we looked at", not "the file's content is correct".

## Three columns, monotonic

Each gate is computed once per level:

```
verified (strictest)  ≤  ≥attested  ≤  ≥asserted (all)
```

The columns are **monotonic**, stricter to the left. **Determination (PASS/FAIL) looks only at the strictest `verified` column.**

Why it is designed this way: historical results need not be deleted and can stay in the wider columns for traceability; but they must not let anyone fake a pass.

## A few concrete rules

1. **A candidate's `evidence_level`** is determined by its source:
   - from a `raw/` raw response → `verified`
   - from an out-of-repo document (manuscript) + sha256 → `attested`
   - manually entered / model-generated / from memory → `asserted`
2. **Model determinations are always recorded as `asserted`**, and must state "[Model-determined]" + rationale in `review_note`.
3. **`capture_mode` determines the evidence level of a run**:
   - `live` → data comes from a live DB and may qualify as `verified`
   - `retrospective` / `memory` → **can only be `asserted`**
4. **Real data ≠ real judgment**.
   The D column comes from live searching (`verified`), but "these 5 are closest prior art" is a judgment (`asserted`).
   The two must be tagged separately and never conflated.

## Self-check questions

Before writing down any conclusion, ask yourself:

- Is there a `raw/` file behind this conclusion? What is its path?
- If not, what is its evidence level? Did I tag it correctly?
- Am I treating "I remember" as "supported"?

If you cannot answer, do not write PASS.
