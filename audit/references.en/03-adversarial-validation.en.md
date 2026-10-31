# 03 — Phase A3: adversarial validation (disproof first)

> Corresponds to Candidate validation in the original. The stance flips: the
> verifier's first assumption is "this mapping is wrong"; the job is to find
> counterevidence. Only an unrefuted candidate passes.

## 1. Verifier prompt (used verbatim; fill `<…>`)

```text
You did not author this candidate mapping. Try to disprove it:
element <element_ref> ↔ prior art <prior_art_ref>, first-pass disclosure
<full/partial>.
Allowed: read the workspace (raw full texts under 02_search_logs/raw,
03_candidates, existing logs).
Not allowed: network searches; modifying the workspace; inheriting the proposer's
reasoning.
Disproof checklist (all items):
1. Quote check: does the verbatim quote actually appear in the located paragraph?
   One changed character disproves;
2. Locator check: does the paragraph support the element? An adjacent paragraph
   posing as the locator disproves;
3. Feature check: are all technical features (including implied limitations)
   disclosed? List the distinguishing features; one undisclosed feature demotes
   full→partial;
4. Date check: is the document's publication date earlier than the target's
   filing/priority date? Where is the evidence?
5. Relevance check: is the disclosure in a mainstream embodiment or a
   marginal/degraded one?
6. Category check: per contract 04, does the proposed impact category exceed the
   evidence-supported disclosure extent?
Output (exactly one JSON object, no prose):
{"decision": "confirmed|needs_validation|rejected", "record": {…}}
record must match the corresponding verdict branch of 04-findings-contract.md;
the proposer's wording may be wholly replaced. Fingerprint: unchanged for the
same root cause.
```

## 2. Decision rules

| Scenario | Disposition |
|---|---|
| Any hard defect in quote/locator/features/date | `rejected`, with the refutation reason and counterevidence locator |
| Path holds but a decisive external fact is missing (family legal status, priority verification, full text unavailable) | `needs_validation`, naming the missing fact + verification plan |
| Disproof fails and the evidence chain is complete | `confirmed`, record rewritten field by field |

- needs_validation is **never** a parking place for a low-confidence confirmed:
  name the missing fact and who can verify it where; otherwise reject.
- Demotions (confirmed→needs_validation) and rejections (→rejected) each append a
  check (agent_id=verifier) to the linked ledger unit.
- Budget exhausted: unvalidated candidates stay in the ledger only (candidate
  state), **never enter findings.json**; run is `incomplete` with
  `validation_budget_exhausted`.

## 3. Consolidation

The planner merges by fingerprint: one final record per root cause; a verifier
returning a different fingerprint is allowed only for a genuinely different root
cause (which re-enters the candidate flow). Malformed or prose-wrapped verifier
output is **discarded and re-run**, never hand-repaired.

## 4. Single-agent mode

When the same session executes A3: first emit the disproof-checklist execution
record for all candidates (the separate round's intermediate artifact), then
produce the three-verdict JSON per candidate. The disproof round may cite only
workspace evidence, never its own A2 judgments.
