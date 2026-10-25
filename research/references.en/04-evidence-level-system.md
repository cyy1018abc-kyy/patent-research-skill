# 04 Source provenance and judgment

Read this before interpreting gate status. Source traceability and approval of a judgment are separate properties.

## Source provenance: retain the three levels

| evidence_level | Meaning | Eligible for strict PASS |
|---|---|---|
| verified | Replayable raw artifact from live collection, retained in the workspace | Yes, subject to the gate-specific judgment requirements |
| attested | External material with an in-workspace SHA-256 binding | No |
| asserted | Source provenance is not verified | No |

AI scoring never downgrades a verified source. Human confirmation never upgrades an asserted or attested source. A hash identifies a file, not the correctness of its contents.

The columns remain monotonic: verified ≤ ≥attested ≤ ≥asserted. PASS uses verified only. For G-S-02/G-S-03, each column additionally applies the same judgment eligibility requirement; an unsupported or legacy judgment is not an eligible count merely because its source qualifies.

## Judgment: record it independently

- `assessment` records actor (`ai`, `human`, or `unknown`), identity, time, per-axis problem/means quotations, locators, rationales, captured passages and a fingerprint.
- G-S-02 accepts supported AI or human assessments. Both dimensions are scored; relevance is their minimum. Abstract or body text is acceptable when sufficient. Missing support means no eligible count for that axis.
- `human_confirmation` records the human, time and exact judgment fingerprint accepted for G-S-03. A role recommendation alone does not count.
- `review_history` retains prior judgments and confirmations; `assessment_proposals` retains AI suggestions conflicting with human decisions.
- Old reviewed_at, a high score, a D-column reference or role=near_prior_art does not establish human confirmation.

## Confirmation and change

Humans may confirm multiple explicit IDs after reviewing their comparison material. Each confirmation binds that candidate's current fingerprint. Never infer confirmation from “continue”, “looks good”, or a general workspace acknowledgment.

Changes to scores, roles, target/axes, feature mapping, rationale, original-text locators or located passages invalidate confirmation. Preserve the record but stop counting it for G-S-03 until re-assessed and re-confirmed. Author spelling and unrelated display metadata do not invalidate confirmation.

Human scores or exclusions take precedence. AI may save new evidence and a proposed revision, but the active human decision governs counting until a human accepts a revision. An expired confirmation does not authorize AI to overwrite it.

## Tool boundary

The kernel checks locators, quotation matches, score consistency and fingerprint freshness. It cannot prove that a quotation entails the score or authenticate the natural person behind a command. The agent must not impersonate a reviewer.

See [07-assessment-protocol.md](07-assessment-protocol.md) for commands and migration. Research conclusions without running tools still require the unverified annotation.
