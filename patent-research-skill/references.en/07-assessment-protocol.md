# 07 Assessment protocol 1

Requires patentkit ≥0.2.0. Old kernels are rejected by skill wrappers. The authoritative implementation is `patentkit/assessment.py`, shared by gates, validation, CLI and API; quantity thresholds remain in `patentkit/gates.py`.

## Upgrade a workspace

```bash
patentkit review migrate-assessments --root /path/to/workspace
patentkit review migrate-assessments --root /path/to/workspace --apply
```

Migration extends the candidate schema and marks missing assessment provenance as `actor=unknown`. It preserves scores, roles, source grades, artifacts and history. It invents no human identity or confirmation. Unknown-origin scores stop qualifying for G-S-02/G-S-03 until re-assessed; their sources remain available for G-S-01.

## Assess

```bash
patentkit review export --format json --axis N1 --out assessment.json
patentkit review assess assessment.json --actor ai --by model-name
patentkit review assess assessment.json --actor ai --by model-name --apply
```

The exported rows carry `candidate_id` and current `expected_fingerprint`. Fill both relevance scores, role, novelty_check, review_note and basis. Basis is keyed by target-qualified axes. Each included axis requires problem and means citations:

```json
{
  "N1@TGT-0002": {
    "problem": {
      "ref": "02_search_logs/raw/source.json",
      "locator": "/hits/0/abstract",
      "quote": "exact words from the located original text",
      "rationale": "why these words support the technical-problem score"
    },
    "means": {
      "ref": "02_search_logs/raw/source.json",
      "locator": "/hits/0/abstract",
      "quote": "exact words describing the implementation",
      "rationale": "why these words support the technical-means score"
    }
  }
}
```

Replace the example with the actual candidate's references and text. References are workspace-relative UTF-8 files, restricted to that workspace. JSON uses JSON Pointer; text uses `L12-L16` line ranges. Quote matching verifies presence, not semantic correctness. An axis without full basis does not count. Two scores are mandatory; relevance is their minimum.

AI conflicts with existing human judgments are saved to `assessment_proposals` without changing active values. Legacy review traces and exclusions are conservatively protected too. After actual review, a human accepts a proposal by importing the chosen assessment with `--actor human --by reviewer-name`. This creates a new judgment and history, but does not automatically confirm G-S-03.

## Confirm a reviewed list

Export again after applying assessments to obtain fresh fingerprints. From reviewed rows, create a UTF-8 JSON array containing **only** the accepted `candidate_id` and `expected_fingerprint` fields. Then:

```bash
patentkit review confirm confirm.json --by reviewer-name
patentkit review confirm confirm.json --by reviewer-name --apply
patentkit gates
```

Only actual human authorization can establish the confirmations. Each candidate must currently have a supported `near_prior_art` assessment. Unknown/duplicate/cross-target IDs, missing fingerprints and stale fingerprints reject the entire batch before writes. For multiple targets, use `--target TGT-xxxx` consistently.

Scores, roles, target/axes, feature mapping, rationale, locators and located original passages are bound into the fingerprint. Substantive changes invalidate confirmation; unrelated author spelling and display metadata do not. History retains prior judgments and captured passages. A stale confirmation never authorizes AI to overwrite a human decision.

## Compatibility and limits

All write commands default to dry-run. Files are staged before replacement; ordinary write errors roll back completed replacements. This is not a database transaction across sudden power loss: retain immutable raw artifacts and workspace backups.

CSV remains available. New CSV exports carry `expected_fingerprint`; keep it unchanged. `review apply sheet.csv --by reviewer-name --apply` records an explicit human actor. Unsigned legacy sheets retain unknown provenance; a timestamp alone cannot establish a reviewer. CSV never creates G-S-03 confirmation or makes an unsupported judgment eligible.

`review progress` uses shared eligibility rules; `status --json` exposes `candidates.by_assessment_state`. V029 reports missing/unsupported/stale judgments; V030 reports stale human confirmation. Re-assess changed material, then obtain confirmation again.

The tool checks quotation matches, score consistency and fingerprint freshness. It cannot prove semantic correctness or authenticate the natural person behind a command. Agents must not impersonate human reviewers.
