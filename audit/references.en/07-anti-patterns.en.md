# 07 — Anti-patterns (full audit and guidance alike)

> Adapted from the original Anti-patterns (10 items), rewritten for the patent
> domain with 2 domain-specific additions. Each maps to a hard gate in the
> validator or the protocol.

1. **Checklists presented as audits**: running a fixed routine is not coverage;
   an "I searched it" without ledger units and checks is no coverage evidence.
   (Hard gate: the ledger is the coverage claim)
2. **Narrative coverage claims**: prose like "the main sources are covered" or
   "classification is mostly scanned" never enters REPORT; coverage counts unit
   states only.
3. **Adjacent paragraphs posing as locators**: the quote sits in [0005] while the
   element's basis sits in [0004]; citing [0005] is locator drift, and A5 sends it
   back. (Hard gate: locator hit + verbatim quote)
4. **Paraphrase passed as quote**: altering a few characters and keeping the
   quotation marks, or splicing half-sentences from two paragraphs.
   (Hard gate: verbatim quote check)
5. **needs_validation used as low-confidence confirmed**: a "to be validated"
   without an exact missing fact and an executable plan is a disguised conclusion.
   (Hard gate: blockers ≥1 + validation_plan)
6. **Impact categories on unvalidated records**: X/Y/A belong to confirmed only.
   (Hard gate: forbidden-field sets)
7. **Trading destructiveness against certainty**: "I am sure it destroys novelty"
   is not an X reason; "it is only background art" does not automatically lower
   certainty. Two axes, scored separately, reasons written separately.
8. **Authors self-confirming**: a confirmed without independent disproof/review
   rounds is a protocol violation. (Hard gate: independent_review required; A3/A5
   role isolation)
9. **Partial disclosure reported as full**: missing distinguishing features
   inflate disclosure_extent and then X. (Hard gate: partial forbids X;
   distinctions checked against the text)
10. **Prior audit results as current coverage**: carrying old confirmed without
    revalidation; old needs_validation left unconverted into current work.
    (Hard gate: prior_status rules + carried records re-pass independent
    validation)
11. **Prose candidates**: hunting output without the four items (document /
    locator / verbatim quote / disclosure extent) registered as a candidate.
    (Hard gate: candidate requires fingerprints + check evidence)
12. **Audit overreach**: the audit quietly adds searches, edits candidates, runs
    --apply, or poses as legal advice. The audit reads the workspace, writes only
    12_audit/, and suggests only through the report. (Hard gate: write isolation +
    neutrality rules)
