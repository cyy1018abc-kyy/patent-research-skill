# 15 · Claim Atoms and Support Mapping

> Defines **ClaimAtom**, **Claim** and **SupportMapping**: how to write them, the structural rules
> the kernel enforces, and the human-confirmation discipline. Field-level authority is
> `patentkit.contracts` (schema_version 1.0).

## 1. Claim atom

```json
{
  "schema_version": "1.0",
  "atom_id": "ATOM-001",
  "idea_id": "IDEA-001",
  "text": "detect the load ramp of the energy equipment",
  "fact_refs": ["FACT-001"],
  "importance": "essential",
  "depends_on": [],
  "review_status": "pending"
}
```

Rules: `atom_id` increasing; `text` is one independently citable feature (no effects, no
unverified parameters); `fact_refs` ≥1 pointing at confirmed facts (**no fact, no atom**);
`importance` essential/optional; `depends_on` for change propagation; `review_status` is owned
by the kernel (imports are pending, `draft atoms review` confirms).

**Fingerprint rule**: confirmation binds the atom *content* fingerprint (excluding
`review_status`). Changing `text`/`fact_refs`/dependencies after confirmation invalidates the old
confirmation (D-017) and requires re-review.

## 2. Structured claim

```json
{
  "schema_version": "1.0",
  "claim_no": 1,
  "claim_type": "independent",
  "parent_claim_no": null,
  "atom_ids": ["ATOM-001"],
  "supported_paragraphs": ["0005"]
}
```

Kernel checks (`draft claims import`):

1. `claim_no` unique and **contiguous from 1** (no gaps);
2. at least one **independent** claim; independent claims have no parent; dependent claims
   reference an **earlier** claim;
3. no cycles (the parent chain strictly decreases);
4. `atom_ids` must exist; every claim feature must trace to facts (atoms carry `fact_refs`);
5. the `review_draft` gate additionally requires paragraph support per claim atom plus confirmed
   human review.

Term **antecedent basis**: every term first used in a claim must be introduced in the independent
claim or an earlier claim; this pipeline enforces it through the glossary plus human review, and
never rewrites prose automatically.

## 3. Support mapping

```json
{
  "schema_version": "1.0",
  "rows": [
    {
      "claim_no": 1,
      "atom_id": "ATOM-001",
      "paragraphs": ["0005"],
      "fact_refs": ["FACT-001"],
      "figures": ["FIG-1"],
      "prior_art_diff": "D1 does not disclose the load-ramp trigger"
    }
  ],
  "review_status": "pending"
}
```

Row key `(claim_no, atom_id)` is unique and the atom must belong to that claim; `paragraphs` must
be non-empty (empty mapping is not coverage); `fact_refs`/`figures` must reference known
identifiers; `prior_art_diff` cites ledger document numbers; human review is recorded separately
and the gate requires all confirmed.

`citations` (optional, kernel 0.8.0, audit rule D-019): structured support citations. `source`
must be a workspace-relative path (unresolvable, `..`-escaping or missing → error); `locator`
must be an `L<n>[-L<m>]` line range or a `[NNNN]` paragraph tag (out of range / tag absent →
error). Once present, a citation has to resolve — support is no longer free text only.

## 4. Review checklist (before `review_draft`)

- [ ] every essential feature has claim atoms whose `fact_refs` point at confirmed facts;
- [ ] every claim atom has ≥1 paragraph support row, human-reviewed;
- [ ] claim numbering contiguous, dependents reference earlier claims, no cycles, ≥1 independent claim;
- [ ] atom confirmation fingerprints are current (re-confirm after text edits);
- [ ] the plan's candidate fingerprint is current (otherwise re-run `draft plan`);
- [ ] G-S-01/02/03 are all PASS (the gate re-checks);
- [ ] numerical statements are registered in `provenance`; manuscript hashing uses `attest`/`revise`.

## 5. Anti-patterns (rejected or gated)

| Practice | Result |
|---|---|
| atom without `fact_refs` | schema rejected (minItems 1) |
| atom references unknown facts | D-005 error |
| editing atom text and keeping the old confirmation | D-017 error, gate blocked |
| claim numbering gaps / dependent referencing a later claim | structural rejection |
| empty support paragraphs | import rejected; gate blocked |
| marking `review_draft` while G-S is not PASS | `draft gate` blocks and lists the failing gates |
| putting unverified effects into claims | violates drafting hard constraints (no fabrication) |
