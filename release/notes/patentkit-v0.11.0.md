# patentkit 0.11.0

Companion kernel for Patent Research Skill 4.3.0; Python 3.11+. Assessment protocol 1,
G-S-01…05 semantics, the evidence three-tier system and rules V001–V038 are unchanged.
Additive release: the utility-model drafting line (4.3 / M1) the manuscript consistency lint (M2) and the manuscript skeleton renderer (M3).

## What changed

- **Contracts (schema_version stays 1.0, all fields optional)**: `drafting_plan.application_type`
  (`invention` | `utility_model`; absent = invention), `drafting_plan.abstract_figure` (`FIG-n`),
  `claim.claim_category` (`product` | `method` | `use`; dependent claims inherit),
  figure type `external_drawing` with `source_file` / `source_sha256` / `human_review`, and the
  document-model fields `application_type` / `working_title` / `abstract_figure` plus
  `kind: external` + `source_sha256` for frozen external figures.
- **`draft plan --type utility_model`**: structure-drawing requirements instead of a method
  flowchart; embodiment requirements stress shape, structure and connection.
- **Audit codes** (`draft audit`): D-020 method/use claim in a utility model, D-021 utility-model
  independent claim without `product`, D-022 utility-model drawings (none planned / only
  flowcharts / none yet), D-023 method/material/software wording (warn only), D-024 dependent
  claim category mismatch (all types), D-025 abstract figure without a figure plan (all types).
- **External drawings**: `figures import FIG-n file.png --parts "1=…,2=…"` (PNG only, pinned by
  SHA-256, copied to `07_drafting/figures/external/`), `figures review FIG-n --by … --apply`
  (confirmation bound to file hash + reference-sign list); F-015/F-016; `figures render` refuses
  external drawings; `figures plan` lists structure views under `needs_import` instead of
  generating a block diagram.
- **Delivery**: E-013 utility model without drawings, E-014 missing/undelivered abstract drawing
  (W-003 for typed inventions), E-015 external drawing changed/unconfirmed after delivery;
  unconfirmed external drawings make `deliver build` fail; DOCX gets the title line and an
  abstract-drawing section.
- **Manuscript lint** (`draft lint`, new module `patentkit/manuscript_lint.py`): M-001…M-015 check the
  manuscript text against the structured model and formal requirements (claim numbering, dependent
  reference wording vs `parent_claim_no`, paragraph numbers, the five description parts, abstract
  ≤ 300 characters, title length, vague wording, antecedent-basis heuristic, reference signs in
  parentheses and sign conflicts, subject wording vs application type, drawing descriptions, full
  stops). Heuristics only warn. Errors make `deliver build` refuse and `deliver check` report **E-016**.
  The pure core `lint_texts()` is what the repository's drafting benchmark scores. M-016 (error)
  reports unfilled `【待补：…】` slots left by the renderer.
- **Manuscript skeleton** (`draft render`, new module `patentkit/manuscript_render.py`): generates
  claims (numbering, dependency wording from `parent_claim_no`, atom texts verbatim), the description
  (five part headings by application type, consecutive paragraphs, one technical-solution paragraph per
  claim, drawing descriptions from figure plans, per-figure parts and reference signs) and the abstract;
  everything the model lacks is an explicit slot — no technical content is invented. Dry-run by default,
  never overwrites an existing manuscript without `--force`, writes a support-mapping suggestion to
  `07_drafting/render/support_suggestion.json` (still imported and human-reviewed). A filled skeleton
  lints clean (kernel-tested for both application types).
- **No migration**: plans without `application_type` rebuild a byte-identical document model
  (same `model_fingerprint` as 0.10.0 on the same workspace; regression-tested).

## Install

```bash
python -m pip install ./patentkit-0.11.0-py3-none-any.whl
```

Drafting output stays draft-grade; `release_ready` is an internal gate, not a filing-readiness claim.
