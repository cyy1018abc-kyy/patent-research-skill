# patentkit 0.7.0

Companion kernel for Patent Research Skill 3.5.0; Python 3.11+. Assessment protocol 1,
G-S-01…05 semantics and the V001–V037 rule set are unchanged; 0.7.0 is additive.

Feature release: the P0–P4 upgrade — versioned data contracts and a non-destructive
workspace upgrade, the discovery/technical-fact control layer, the structured drafting
pipeline with a two-state writing gate, the professional figure engine, and the complete
delivery pipeline. It ships as `patentkit-0.1.2-to-0.7.0.patch` applied to the public
`patentkit-0.1.2.tar.gz`.

## New modules

- `patentkit/contracts.py` — 12 versioned JSON Schemas (`source_manifest`, `technical_fact`,
  `idea`, `idea_decision`, `drafting_plan`, `claim_atom`, `claim`, `support_mapping`,
  `figure_plan`, `delivery_manifest`, `discovery_handoff`, `patent_document_model`),
  canonical-JSON SHA-256 fingerprints, idea content fingerprint that excludes status,
  confined-path resolution (Windows absolute/drive/UNC locators are rejected on every
  platform, POSIX included). Schema version 1.0 (additive).
- `patentkit/workspace_upgrade.py` — `upgrade check/apply`: deterministic, non-destructive
  layout upgrade adding `10_discovery/` (with `ideas/`, `materials/`, `parsed/`...) and
  `11_delivery/`; dry-run by default, legacy workspaces keep working.
- `patentkit/source_intake.py` — private material registration (`intake`): SHA-256, size,
  locator, parsed-text cache; refuses executables/archives; no material execution.
- `patentkit/discovery.py` — technical facts, patent candidates (ideas), decision ledger,
  G-I-001…025 review checks, G-I-gated `discovery handoff` drafts (handoff never touches
  `01_search_plan/` and never produces G-S results).
- `patentkit/draft.py` — DraftingPlan, claim atoms (confirmation bound to the atom content
  fingerprint, D-017), structured claims (numbering/parent/cycle/known-atom checks),
  support mapping + human review, G-D audit D-001…D-018, `concept`/`review_draft` gate,
  change-impact propagation.
- `patentkit/figure_plan.py` — `figures plan/render/validate`: deterministic black-white SVG
  (same plan → identical bytes; optional 300-DPI PNG via Pillow), F-001…F-014 figure-text
  consistency checks reusing V033, render-from-spec only (never invents parts).
- `patentkit/delivery.py` — frozen `PatentDocumentModel` (claims/specification/abstract/
  figures + input hashes + gates snapshot + fingerprint), DOCX review copy, optional PDF
  preview via a local converter (missing converter reported, never faked), delivery manifest
  with artifact SHA-256, human sign-off bound to the manifest fingerprint, `deliver check`
  E-001…E-012. CNIPA XML is not implemented (`not_attempted`; export fails closed).

## CLI additions

`upgrade`, `intake`, `discovery`, `draft`, `figures plan/validate/render`, and `deliver`
join the existing commands; `figures check/draw` and all pre-0.7.0 commands are unchanged.
`draft gate --to release_ready` extends the P2 writing gate.

## Tests

Kernel suite: **737 passed / 11 skipped / 0 failed** (dev tree, Windows, Python 3.12; the
11 skips are POSIX/optional-dependency cases). New suites: `test_contracts.py`,
`test_workspace_upgrade.py`, `test_source_intake.py`, `test_discovery.py`,
`test_discovery_handoff.py`, `test_draft.py`, `test_figure_plan.py`, `test_delivery.py`
(including deliberate-failure cases and deterministic golden SVGs). Golden pipeline
snapshots are unchanged: G-S semantics did not move.

## Version single source

`patentkit.__version__ = "0.7.0"`. Assets: `patentkit-0.7.0-py3-none-any.whl`,
`patentkit-0.7.0.tar.gz`, `SHA256SUMS-patentkit-v0.7.0.txt`. CI reconstructs the kernel from
the public 0.1.2 sdist plus `release/patches/patentkit-0.1.2-to-0.7.0.patch`.
