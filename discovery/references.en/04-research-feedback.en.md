# 04 · Research Feedback Loop (optional `patent_intel` extension)

> **Boundary first**: this loop comes from the optional `patent_intel` extension
> (4.0). Discovery remains the sole authority for features and inventive points;
> the extension only feeds "which features still lack search support" back to the
> retrieval side. Without the extension, skip this page.

## The loop

```text
Discovery confirms inventive points / technical axes (glossary, kernel truth)
        │
        ▼
research side: recall report (offline coverage diagnostic)
        │   · axes with zero hits → suggest follow-up search
        │   · which query produced independent new families → yield reference
        ▼
evidence build (evidence projections)
        │   · feature × candidate matrix: supported / linked / no_evidence, explicit
        ▼
gap list (gap analysis)
        │   · no_evidence features → follow-up retrieval suggestions (back to WP-A)
        ▼
human judgement: search more or accept coverage → back to Discovery refinement
```

## Discipline

1. **Inputs never auto-leave the machine**: Discovery material is processed locally
   by default; any online retrieval requires explicit consent and a recorded
   data-egress scope (interface rule 1).
2. **Experimental effects / comparison conditions**: the coverage matrix only sees
   *documentary* evidence, not experimental design; unsupported effect assertions
   are flagged for humans — the extension never invents comparison conditions.
3. **Feedback is advice**: zero hits ≠ no technique exists; gap wording is fixed to
   "the current sample contains no anchored evidence; further search recommended".
4. When the inventive-point wording changes, glossary changes go through the kernel
   flow; the extension's views simply rebuild from the new axes.
