# 04 — Phase A4: the findings.json three-verdict contract

> Corresponds to Structured output in the original (report-schema.json +
> validate-findings.cjs); fields are rewritten for the patent domain and the
> validator is pure Python (`audit/scripts/validate_findings.py`, stdlib only;
> its header says derived from Cloudflare security-audit-skill, MIT).

## 1. What each verdict means

| Verdict | Meaning | Requires | Forbids |
|---|---|---|---|
| `confirmed` | Complete evidence chain, survived independent disproof | Mapping rationale, verbatim-quote evidence, disclosure extent, impact category, confidence, independent-review mark | claimed_rationale, blockers, validation_plan, refutation |
| `needs_validation` | Path holds but one decisive fact is missing | claimed_rationale, blockers (≥1), validation_plan (local/external, ≥1) | impact, disclosure_extent, confidence, distinctions, independent_review, mapping_rationale, refutation |
| `rejected` | Refuted by counterevidence (retained to prevent repeats) | claimed_rationale, refutation | impact, confidence, independent_review, blockers, validation_plan, mapping_rationale |

Common to all three: `verdict`, `fingerprint`, `title`, `description`,
`element` (claims-map element reference), `trace` (element→disclosure→effect
chain), `evidence` (verbatim-quote array).

## 2. Key field rules (enforced by the validator)

- **fingerprint**: `^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$`, source-derived, stable
  across verdicts (convention `MAP:<element-id>:<document id>`); unique
  document-wide and sorted lexicographically.
- **trace**: `kind` enum `element|disclosure|effect`; first item must be
  `element`, last must be `disclosure` or `effect`, middles only `disclosure`;
  every item carries `ref` (workspace-relative path #paragraph/line) and
  `description`.
- **evidence**: each item `{ref, locator, quote, description}` — `ref` is a safe
  relative path (no backslash/drive/`..`/absolute), `locator` non-empty (e.g.
  `[0004]` or `L12`), `quote` is **verbatim**. confirmed requires evidence ≥1.
- **impact (destructiveness axis)**: confirmed only. `category` aligns with
  search-report categories — `X` (novelty-destroying alone) / `Y` (inventive-step
  relevant in combination) / `A` (background); `X` additionally requires
  `element_coverage.all_elements == true` (full element-chain declaration) or
  validation fails. **Overall never exceeds the demonstrated disclosure extent**:
  `disclosure_extent: "partial"` permits only `Y` or `A`.
- **confidence (certainty axis)**: confirmed only, `low|medium|high` + reason;
  separate from impact, never traded against it (high certainty does not raise
  destructiveness; high destructiveness does not raise certainty).
- **independent_review**: confirmed only, `{status: "verified", reviewer: <id>}`;
  a confirmed without phase A5 is a protocol violation.
- **needs_validation.validation_plan**: `local` (verifiable locally: family
  search, official registers, re-acquiring the document) and `external` (human or
  authorized external sources: prosecution history, right-holder confirmation);
  at least one.
- **rejected.refutation**: the refutation type (quote mismatch, locator posing,
  undisclosed features, adverse date, relevance failure) + counterevidence
  locator.

## 3. Document-level rules

Top-level array; ≤1000 findings; input ≤5 MiB, nesting ≤64; sorted by
fingerprint; duplicate fingerprints are errors. Field sets are **closed**
(additionalProperties forbidden): hunter wrapper fields never leak into records.

## 4. Running the validator

```bash
# Structural validation (any time)
python audit/scripts/validate_findings.py findings.json

# With evidence verification: checks ref existence, locator hit, verbatim quote
python audit/scripts/validate_findings.py findings.json --workspace <workspace root>

# Machine-readable result
python audit/scripts/validate_findings.py findings.json --json
```

Exit codes: `0` pass / `1` validation failure (problems list everything, capped at
100) / `2` usage or environment error. `--json` emits a single JSON document
(`{"ok":…, "errors":[…]}`). Passing proves format and field discipline only;
semantic correctness remains the A3/A5 roles' responsibility.

## 5. Verbatim branch copies for producers

Generators (verifier/reviewer) copy the matching verdict branch of
`findings-schema.json` verbatim (including `additionalProperties: false`); no
invented field names. Changing the contract requires a synchronized change to:
this file, `findings-schema.json`, `audit/scripts/validate_findings.py`,
`tools/score_audit_findings.py`, and the tests on both sides.
