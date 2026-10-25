# 13 The multi-round revision loop

> Benchmark: PatentClaw's traceable multi-round revision (isolated issue → local patch →
> re-review → change record), integrated with this repository's existing `attest` sha256
> binding. **Core principle: revisions must be traceable, revertible, and must never touch
> unrelated content in passing.**

## The loop (identical every round)

```
Issue list (one issue — or one related group — per round)
   ↓ local patch: touch only the corresponding fields/paragraphs
Change log (one new row in revision_ledger.md)
   ↓
attest --apply (re-bind the sha256)
   ↓
Re-run the gates: validate --strict + gates + (provenance check when numbers are touched)
   ↓ (when confirmed near-prior-art is affected)
Re-assess → re-confirm by a human (the fingerprint changed; the old confirmation is
   invalidated by design — that is a feature, not a bug)
```

## The change-log format (`07_drafting/revision_ledger.md`)

```markdown
| Round | Date | Issue source | Change (field/paragraph level) | Re-verification triggered | Confirmation state |
|---|---|---|---|---|---|
| R3 | 2026-10-25 | OA-X2 | claim 2 range 0.33-0.45→0.35-0.42 | provenance + support_mapping | P-012 needs re-confirmation |
```

## Three hard rules

1. **One patch resolves exactly the logged issue.** Touching other places in passing
   destroys the traceability of the other changes — and silently invalidates human
   confirmations that were still valid;
2. **substantive changes invalidating confirmations is by design** (see the judgment
   eligibility section of [00](00-prerequisites.md)): changing scores / roles / axes /
   rationale / citations requires re-assessment and fresh human confirmation; unrelated
   metadata such as author spelling does not;
3. **no "patch first, log later"**: without a change-log row, an `attest --check` drift
   report cannot answer "who changed what, when, and why".

## Kernel hooks

```powershell
python -m patentkit attest --check        # drift detection (changed without logging → alarm)
python -m patentkit validate --strict     # structural consistency
python -m patentkit provenance check      # number-related changes
python -m patentkit review export --format json --axis N1 --out re.json   # re-assessment entry
```

## Round cap

The same issue still open after 3 consecutive rounds → stop and escalate to the
inventor / attorney; **do not** paper over missing material with endless revisions
(cf. the open_questions list in [09](09-disclosure-drafting.md)).
