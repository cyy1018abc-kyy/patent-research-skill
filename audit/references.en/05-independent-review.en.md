# 05 — Phase A5: independent review

> Corresponds to Independent record verification in the original. The review
> target is the **final record** (not the hunting narrative), checked item by item
> by a fresh role; this is the last gate that makes a confirmed trustworthy.

## 1. Scope and role

- One independent review per final `confirmed` and `needs_validation` record;
  the `quick` profile may merge A3+A5 into one pass (same verifier does both),
  but **a confirmed is never exempt from independent review**.
- The reviewer is neither the candidate's author nor the A3 verifier (single-agent
  mode = a new review round carrying only the final record and the evidence
  documents).

## 2. confirmed review checklist (all items)

1. **Quote verbatim**: every evidence quote matches the located paragraph in the
   ref document character for character (punctuation and full/half width too;
   paraphrase/abridgment/spliced fragments do not qualify);
2. **Locator hit**: the located paragraph actually supports the element; an
   adjacent paragraph posing as the locator is sent back;
3. **trace real**: every hop of element→disclosure(→effect) has a real ref with
   matching semantics;
4. **Element alignment**: the element reference matches the claims-map statement;
   the distinctions list is checked against the text (missing distinguishing
   features inflate disclosure_extent);
5. **Disclosure extent**: full/partial holds after feature-by-feature comparison;
6. **Impact category**: X requires the full element chain
   (element_coverage.all_elements true, mapped per element); partial permits only
   Y/A; reasons match the evidence;
7. **Fix direction** (if present): suggestions respect "do not move trust, do not
   fabricate evidence".

## 3. needs_validation review checklist

1. The trace supports only the claimed_rationale (nothing stronger);
2. Every blocker is a genuinely external fact that cannot be resolved locally;
3. The validation plan's local/external fields are executable and never require
   sending workspace data outward;
4. The fingerprint matches prior records (if any).

## 4. Review output

```json
{"decision": "verified", "fingerprint": "MAP:E-01:ZZ900011A1"}
```
or
```json
{"decision": "replace", "reason": "…", "record": {…}}
```

- **Non-material corrections** (wording, line-number typos): apply directly,
  re-run the validators.
- **Material corrections** (verdict promotion, root-cause change, changed
  trace/evidence/disclosure extent/impact category): a **fresh reviewer that did
  not touch this candidate** must re-verify; when the budget disallows, remove the
  record from findings.json, return its ledger unit to candidate, and mark the run
  `incomplete`.
- After every applied correction: re-run `validate_findings.py` +
  `validate_ledger.py` and append a check (agent_id=reviewer) to the linked unit.
- A review that uncovers a **new independent root cause**: new fingerprint, back
  through A3 as a candidate.

## 5. Metric accounting

After the review round, compute the verifier overturn rate
(`00-audit-protocol.md` §8) and put it into REPORT §1 and the run-metadata
completion summary. A non-zero rate is not bad news — it is why this methodology
exists. Record it plainly.
