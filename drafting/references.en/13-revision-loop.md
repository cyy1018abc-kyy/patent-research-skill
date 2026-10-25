# 13 The multi-round revision loop

> Benchmark: PatentClaw's traceable multi-round revision (isolated issue → local patch →
> re-review → change record), integrated with this repository's existing `attest` sha256
> binding. **Core principle: revisions must be traceable, revertible, and must never touch
> unrelated content in passing.** Since kernel 0.4.0 the loop is *enforced* by
> `patentkit revise` — patch, ledger and re-binding happen in one transaction, and an
> unlogged edit becomes a detectable error instead of a matter of discipline.

## The loop (identical every round)

```
Issue list (one issue — or one related group — per round)
   ↓ write a patch file (YAML: round / issue / source / changes[], each with a field-level locator)
revise apply patch-R4.yml   ←  file edits + revision_ledger.yml entry + registry re-bind, one transaction
   ↓
Re-run what the ledger's revalidate list calls for: validate --strict + gates (always)
   + provenance check (numbers) / figures check (figure marks) / fresh human confirmation
   ↓
revise close --round R4     ←  close the round once re-verification passes (close re-runs the
                               integrity check first and refuses on a broken chain)
   ↓ (when confirmed near-prior-art is affected)
Re-assess → re-confirm by a human (the fingerprint changed; the old confirmation is
   invalidated by design — that is a feature, not a bug)
```

## Patch file format (the only write path, via `revise apply`)

```yaml
schema: 1
round: R4                      # must not duplicate a round already in the ledger
issue: OA-X2                   # problem identifier
source: office action          # where the issue came from
changes:
  - file: 07_drafting/claims.md  # must be registered in manuscript_registry.yml
    field: claim 2 numeric range # human-readable field/paragraph locator
    find: "0.33-0.45"            # must appear **exactly once** in the target file
    replace: "0.35-0.42"
    revalidate: [provenance, confirmations]  # optional; validate+gates are always required
```

The three hard rules thereby become structural properties:

1. **One patch resolves exactly the logged issue.** The tool applies only the declared
   find→replace pairs; touching other places "in passing" has no patch entry and cannot
   reach the file;
2. **Substantive changes invalidating confirmations is by design** (see the judgment
   eligibility section of [00](00-prerequisites.md)): a change declaring
   `revalidate: [confirmations]` makes the apply output state the re-assessment and
   re-confirmation requirement explicitly;
3. **No "patch first, log later"**: `revise status` and validate's V036 flag "current file
   sha256 ≠ the ledger's post-round sha256" (status exits 1; validate warns, and `--strict`
   escalates). An `attest --check` drift report now has an answer to "who changed what, when,
   and why": every ledger change records the sha256 before and after. A structurally broken
   ledger is a V035 error.

## Round cap

The same issue reaching 3 rounds → `revise status` says so explicitly: stop and escalate to
the inventor / attorney; **do not** paper over missing material with endless revisions
(cf. the open_questions list in [09](09-disclosure-drafting.md)). Close a round with
`revise close --round R4 --note "one-line re-verification evidence"`; close refuses while the
chain-integrity check fails.

## Command quick reference

```powershell
python -m patentkit revise apply patch-R4.yml   # atomic apply (any find hit-count ≠ 1 → refuse, zero writes)
python -m patentkit revise status               # round table + chain integrity (unlogged edit → exit 1)
python -m patentkit revise close --round R4     # close once re-verification passed
python -m patentkit attest --check              # drift detection (registry view; cross-checks the ledger)
python -m patentkit validate --strict           # structural consistency (V035/V036)
python -m patentkit review export --format json --axis N1 --out re.json   # re-assessment entry
```
