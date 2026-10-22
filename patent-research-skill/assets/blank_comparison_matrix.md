# Blank comparison matrix (N axes × M closest prior-art documents)

> **How to use**: copy this table into `04_comparative_analysis/` and add or remove rows according to the workspace's actual number of axes.
> **Axis names are defined authoritatively only by the workspace's `00_methodology/glossary.yml`**; this template must not rename them or invent abbreviations.
> Legend: ● fully disclosed / ○ partially disclosed / — not disclosed / ? to be verified (no ●/○ without evidence from the original text).

| Dimension \ comparison document | D1 | D2 | D3 | D4 | D5 |
|---|---|---|---|---|---|
| **N1: <axis name>** |  |  |  |  |  |
| **N2: <axis name>** |  |  |  |  |  |
| **N3: <axis name>** |  |  |  |  |  |
| **N4: <axis name>** |  |  |  |  |  |
| **N5: <axis name>** |  |  |  |  |  |
| **N6: <axis name>** |  |  |  |  |  |
| **Overall closure** |  |  |  |  |  |

## Output per column (per comparison document)

```text
D1 — <title>  <publication number or URL>
- Applicant: <applicant>
- Publication year: <year>
- Hit axes: N<n>, N<m>
- Relationship: □ blocking (blocks novelty) / □ partial overlap / □ marginal
- Key passages: <cite 1–3 original paragraphs; must be traceable to raw/ or the original text>
- Distinguishing points: <our distinguishing features / what the other document does not disclose>
- Evidence level: verified (has raw/) / attested (has sha256 binding) / asserted (self-report only)
```

## Three-tier determination (fill in together with the table)

| Tier | Question | Conclusion | Basis (evidence level) |
|---|---|---|---|
| Tier 1: per-document novelty | Does a single document cover **all** core features? | holds / doubtful / does not hold |  |
| Tier 2: combination inventive step | Would a combination of 2–3 documents be "obvious"? Are there zero-disclosure atoms that cannot be assembled? | holds / doubtful / does not hold |  |
| Tier 3: technical effect | Is there a non-obvious effect that must presuppose the distinguishing features? | holds / doubtful / does not hold |  |

> Tier 2 must include a **self-attack**: list the examiner's most likely motivation to combine and objections, then write the responses.
> All three conclusions must carry an evidence level; a judgment without `raw/` support can only be `asserted`.

## Proposed amendments

- [ ] New claims / strengthened dependent claims (which axes need reinforcement)
- [ ] Additional supporting paragraphs in the specification
- [ ] Additional figures
- [ ] Risk level: high / medium / low — basis:
