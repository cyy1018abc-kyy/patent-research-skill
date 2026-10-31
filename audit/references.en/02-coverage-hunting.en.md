# 02 — Phase A2: coverage-led hunting and the critic

> Corresponds to HUNTING in the original; "attack classes" become "search-strategy
> facets", and the hunt produces element-to-prior-art mapping candidates plus
> coverage facts instead of vulnerability candidates.

## 1. Hunter prompt (used verbatim per claimed unit; fill `<…>`)

```text
You are the audit's search hunter. Claim ledger unit <coverage_id>:
element <element>, source <source>, classification <klass>.
Allowed: read workspace <starting_paths> and the corpus they reference; execute
the search/review this unit promises.
Not allowed: jumping to other units; modifying the workspace; writing "no hits"
as "no relevant literature exists".
Steps:
1. Execute the promised search (or review existing logs), recording checks;
2. For each hit, decide which features of the element it discloses
   (full/partial/absent); a candidate mapping must carry: document identifier +
   paragraph locator + verbatim quote + a first-pass disclosure extent;
3. Mark covered once the unit's full promise is discharged; mark candidate when a
   potential mapping exists and register result_fingerprints; mark blocked with
   the exact blocker when sources/permissions are missing.
Return a structured result (no prose wrapper): unit update + checks + candidate
mappings.
```

**Candidate gate**: a hit without all four items (document + locator + verbatim
quote + disclosure extent) is a log line, not a candidate. Prefer covered with zero
candidates over prose candidates.

## 2. Waves and the critic

1. Assign units in ledger priority order (changed-source revalidation > prior gaps
   > new units); one round is one wave;
2. After every wave, **run the critic**, which answers three questions —
   - Which units are only formally covered (generic checks, no concrete
     queries/documents)?
   - Which cells of the element×source×classification matrix are still unseeded?
   - Which candidates contradict each other or existing conclusions?
3. Critic-proposed reassignment: archive attempts first (with
   `reassignment_reason`), then wave+1 with a new claim; quick profile allows
   exactly 1 wave + 1 critic, and discovered reassignments become `deferred`.

## 3. Search-strategy facets (the hunting lenses; attach per unit)

- **Lexical**: synonyms/broader terms/competitor terminology; both languages tried?
- **Classification**: neighboring groups of the initial symbols (parent group,
  adjacent subgroups)?
- **Citation**: forward/backward citation chains of hits walked?
- **Family**: family/priority chains of key hits checked (dates and content may
  differ)?
- **Negative**: has the query been validated in reverse — "if this document
  disclosed the element, which query would have found it?" No answer means a
  blind spot.

Attachment rule: each unit attaches the applicable facets in its checks'
descriptions; inapplicable facets are recorded as excluded with the source reason
(same discipline as the original's companion/excluded blocks).

## 4. Consolidation and ledger update

The planner is the sole writer: update units per the §6 state machine in
`00-audit-protocol.md`; pre-assign each candidate mapping the fingerprint
`MAP:<element-ref>:<document id>` (stable across states for the same root cause).
Re-run `validate_ledger.py` after every update.

## 5. Round accounting in single-agent mode

Each round = one unit claim or one critic run. Reserve and spend the budget per
`00-audit-protocol.md` §7; record spent/planned in `run-metadata.json`'s `budget`.
