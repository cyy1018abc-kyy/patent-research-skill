# 14 · Structured Drafting Pipeline (P2)

> Defines the structured flow **plan → claim atom → claim → support mapping → dual-state gate**.
> The kernel owns structure and audit; the AI/inventor owns prose and confirmation. The single
> entry point is `patentkit draft`. This pipeline produces **no deliverable files** (DOCX/PDF are
> P4) and never changes the research-side G-S semantics.

## 1. Workspace files (`07_drafting/`)

| File | Content | Written by |
|---|---|---|
| `drafting_plan.yml` | contract `drafting_plan`: target, candidate, protected subject, essential features, drawing needs, open questions, research snapshot, candidate fingerprint | `draft plan --apply` |
| `claim_atoms.json` | `claim_atom` list (claim-feature atoms with fact references) | `draft atoms import --apply` |
| `atom_review.json` | fingerprint-bound human confirmation records for atoms | `draft atoms review --apply` |
| `claims_structured.json` | `claim` list (numbering/type/parent/atoms) | `draft claims import --apply` |
| `support_mapping.json` | `support_mapping`: claim/atom → paragraphs/facts/figures | `draft support import --apply` |
| `support_review.json` | human semantic-review status of support rows | `draft support review --apply` |
| `drafting_state.json` | dual-state writing gate (`concept` / `review_draft`) + model bundle fingerprint | `draft gate --apply` |
| `drafting_audit.jsonl` | append-only audit (plan/atom/claim/support/state events) | automatic |

The existing `manuscript_registry.yml` / `revision_ledger.yml` / `numerical_provenance.yml` stay
unchanged; manuscript prose stays outside the repository — only the structured model lives here.

## 2. Commands

```powershell
python -m patentkit draft plan --idea IDEA-001 --target TGT-0002 --apply
python -m patentkit draft atoms import .\atoms --apply
python -m patentkit draft atoms review --ids ATOM-001,ATOM-002 --decision confirmed --by inventor --apply
python -m patentkit draft claims import .\claims --apply
python -m patentkit draft support import .\support --apply
python -m patentkit draft support review --claim-no 1 --atom-id ATOM-001 --decision confirmed --by inventor --apply
python -m patentkit draft audit --root .\workspace
python -m patentkit draft status --root .\workspace
python -m patentkit draft gate --to review_draft --by inventor --apply
python -m patentkit draft impact --claim-no 1
```

## 3. Dual-state writing gate

| State | Meaning | Entry condition |
|---|---|---|
| `concept` | early technical memo; the only legal state while gates are not ready | default; any model change reverts to it |
| `review_draft` | formal application draft (ready for attorney review) | audit has no errors; **G-S-01/02/03 all PASS**; all atoms human-confirmed with current fingerprints; claims structurally valid; every claim atom has paragraph support and support review confirmed; candidate fingerprint current |

- The state records a `bundle_fingerprint`: any substantive change to plan/atoms/claims/support
  automatically invalidates it (`draft status` shows stale; back to `concept`) — re-gate after edits.
- **`release_ready` is not implemented**: the delivery gate (DOCX/PDF/manifest) lands in P4; until
  then nothing may be called a deliverable.

## 4. G-D audit codes (`draft audit`)

| Code | Level | Meaning |
|---|---|---|
| D-001 | error/warn | no plan (warn); plan schema violation (error) |
| D-002 | error | plan references a missing or unconfirmed candidate |
| D-003 | error | plan is stale (candidate fingerprint changed) |
| D-004/D-005 | error | atom schema violation / unknown facts |
| D-006 | warn | atom facts not human-confirmed |
| D-007 | warn | atom not human-confirmed (missing/stale review) |
| D-008 | warn | atom contains numerical statements; register in provenance |
| D-009 | error | essential feature facts not covered by any claim atom |
| D-010 | error | claim schema / numbering gap / invalid parent / unknown atoms / no independent claim |
| D-011 | warn | claim atom lacks paragraph support |
| D-012 | warn | support mapping not human-reviewed |
| D-013 | error | claim references unknown atoms |
| D-014 | warn | open questions remain (blocks formal delivery) |
| D-015 | error/warn | provenance registry problems (reuses the existing check) |
| D-016 | error/warn | revision-ledger problems (reuses the existing `revise` check) |
| D-017 | error | atom claims confirmed but the fingerprint-bound review record is missing/stale |

## 5. Relationship to existing mechanisms

- **provenance**: numerical statements in atoms are scanned/registered by the existing registry;
  the audit calls the existing check instead of re-implementing it.
- **attest / revise**: manuscript hashing and the revision loop keep using the existing commands;
  this pipeline only adds the structured model and change-impact propagation.
- **discovery**: the plan only accepts a human-confirmed candidate; candidate changes make the
  plan stale (D-003).
- **research G-S**: the `review_draft` gate reads the real `gates` result; it never recomputes or
  loosens thresholds.
