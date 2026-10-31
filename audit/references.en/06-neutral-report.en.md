# 06 — Phase A6: the neutral report

> Corresponds to Target-neutral reporting in the original. The report is
> **derived** from the final records and never changes a verdict, impact
> category, blocker, or disclosure extent; records that did not pass A5 never
> appear as conclusions.

## 1. REPORT.md structure (in order)

1. **Run summary**: profile, scope, mode (single/multi), budget spent/planned,
   audit baseline (workspace snapshot id), prior-run intake; quick/scoped/
   budget-limited/incomplete runs declare "partial coverage" in their first
   sentence. Two mandatory metrics: **ledger coverage** and **verifier overturn
   rate**.
2. **Overall judgment** (≤5 sentences): can this evidence chain be trusted, and
   what is the largest risk.
3. **Confirmed table**: impact category (X/Y/A), title, element, prior-art
   document, one-line disclosure note. **No** rejected records.
4. **Per-finding sections** (each confirmed): element reference, document and
   locator, verbatim quote, distinguishing features, disclosure extent, impact
   rationale, confidence (stated separately), independent-review mark.
5. **NEEDS VALIDATION table**: title, trace summary, exact missing fact,
   local/external next step. **No impact category, no "novelty-destroying"
   wording.**
6. **Suggestions**: extra-search / re-citation suggestions for patent-research
   (suggest only, never execute).
7. **Coverage summary**: covered/candidate/blocked/deferred/not_applicable
   counts + coverage rate + final critic result + material exclusions
   (out_of_scope with reasons).
8. **Completeness statement**: when incomplete, list every unvalidated
   fingerprint and ledger unit; never present them as conclusions.

## 2. NEEDS-VALIDATION.md

One section per unresolved record: trace, verified evidence (quotes verbatim),
the exact blocker, the affected boundary (which element / which claim), and the
local/external verification plan. Order by evidence strength × element
importance — this is a **leads list**, not a defect list.

## 3. Neutrality rules

- Report wording matches verdicts strictly: needs_validation is always
  "to be validated"; rejected records do not appear (unless explaining a historical
  disagreement).
- No invented LOW findings to fill the page: a clean run may have zero confirmed —
  say "no confirmable mapping found" and state the coverage/validation limits.
- No legal conclusions: the report is not an invalidity/infringement opinion;
  grant-prospect semantics belong to the G-S flow.
- No workspace data leaves the environment: quoted examples come from the audited
  workspace and the report stays in the run directory; external sharing requires
  the right-holder's consent.

## 4. Artifact self-check

After writing the report: re-run both validators (findings + ledger) to confirm
report and JSON agree; every fingerprint in REPORT exists in findings.json; every
confirmed carries the independent-review mark; no unvalidated candidate ever speaks
in a conclusion's voice.
