# 10 · Technology Landscape Report (optional `patent_intel` extension)

> **Usage boundary (most important)**: the landscape report is **descriptive
> statistics over the retrieved sample**. Sparse clusters, a quiet year, or an
> absent applicant only describe the sample — they **do not prove a technology
> blank** and never support an allowability conclusion. Proving a blank requires a
> responsible full-corpus census (e.g. the kernel's G-S-04 citation/family census
> chain), not this report.

## Generate

```bash
python -m patent_intel landscape report --root <ws>   # writes to sidecar reports/
```

Local CSV + Markdown, no JS, no external services, reproducible (same input →
same output).

## How to read it

| Output | Meaning | Do NOT read it as |
|---|---|---|
| Applicant table | family vs document counts within the sample (kept separate) | "who leads the field" |
| Yearly trend | publication-year distribution within the sample (missing years explicit) | industry momentum |
| Axis distribution | where our searches produced hits | a panorama of hot topics |

## Sampling-bias disclosure

The report header always states: sample size, unknown-family share, missing-year
share. When the sample is sparse, conclusions must keep the "within the sample"
qualifier; before quoting this report in any formal document, have a human review
the search coverage (together with the recall report's gap list).
