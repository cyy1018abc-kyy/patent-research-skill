# 20 · Utility-model drafting and delivery (4.3 / kernel 0.11.0)

> Defines the **utility model** rules inside the structured drafting pipeline (D1–D8):
> application type, claim category, structure drawing import with human confirmation, and the
> utility-model audit codes and delivery gate. This skill produces drafts and flags gaps — it
> **never judges grantability and does not replace a patent attorney**; heuristic checks only
> warn, and a human decides.

## 1. Legal basis (only rules with a citable source)

| Rule | Source | Implementation |
|---|---|---|
| A utility model is a new technical solution relating to the **shape, structure, or their combination, of a product**, fit for practical use | Patent Law Art. 2(3) | product claims only (D-020/D-021); improvements to a method, material or software as such are not utility-model subject matter (D-023 warning) |
| Preliminary examination of utility-model applications (subject matter, drawings of the description, abstract drawing, obvious substantive defects) | Patent Examination Guidelines Part I Chapter 2 | drawings are mandatory (D-022 / E-013); an application with drawings designates an abstract drawing (E-014) |

> The Implementing Regulations were renumbered in the 2023 revision: this file **never invents
> article numbers**; check the current official text before citing a rule and record the check
> in `docs/policy-log.md`.

## 2. Application type and claim category

```powershell
# Utility-model drafting plan (structure drawings required, no method flowchart planned)
python -m patentkit draft plan --idea IDEA-001 --type utility_model --apply
```

- `drafting_plan.application_type`: `invention` (default) | `utility_model`. Old plans without
  the field are inventions — **no migration needed**.
- `claim.claim_category`: `product` | `method` | `use` (optional). A dependent claim that does
  not declare one **inherits** the category of the claim it refers to.
- In a utility model **every independent claim must declare** `claim_category: product` (D-021).
- Abstract drawing: set `abstract_figure: FIG-1` in the plan (it must exist before delivery).

## 3. Structure drawings: human-drawn → import → human visual confirmation

Utility-model drawings show the product's shape, structure, or their combination. The
deterministic renderer only draws block diagrams and flowcharts — it **cannot draw mechanical
structure** — so structure drawings are drawn by a human (black-and-white line drawings exported
from CAD, PNG) and then imported:

```powershell
# Import (dry-run by default): copied into 07_drafting/figures/external/, pinned by SHA-256
python -m patentkit figures import FIG-1 .\drawings\fig1.png --title "Fig. 1 overall structure" --parts "1=housing,2=lid,3=latch" --apply

# Human visual confirmation (bound to the file hash + the reference-sign list)
python -m patentkit figures review FIG-1 --by inventor --apply
```

- `--parts` must list **every reference sign** in the drawing with its part name (`sign=name`,
  1–3 digits); it is the basis of the figure-mark ↔ specification consistency check.
- `figures plan` **never auto-generates** "structure / sectional / perspective / front view"
  requirements; they are listed under `needs_import` — a block diagram posing as a structure
  drawing would mislead reviewers.
- Replacing the file or changing the reference signs invalidates the confirmation (F-016);
  run `figures review` again.

## 4. Audit and delivery codes (utility model)

| Code | Level | Applies to | Meaning |
|---|---|---|---|
| D-020 | error | utility model | a method/use claim (including a category inherited by a dependent claim) is not utility-model subject matter |
| D-021 | error | utility model | an independent claim does not declare `claim_category: product` |
| D-022 | error/warn | utility model | no drawing requirements (error); every figure is a flowchart/state machine (error); some flowcharts (warn); no figure yet (warn — E-013 blocks delivery) |
| D-023 | warn | utility model | atom wording such as method/step/process/formulation/program/algorithm suggests a method, material or software feature — **a human decides** (a known method name that merely qualifies a product is acceptable) |
| D-024 | error | all types | a dependent claim declares a category different from the claim it refers to |
| D-025 | error/warn | all types | `abstract_figure` points to a missing figure (warn while no figure exists at all) |
| F-015 | error | external drawing | file missing, not a PNG, or changed after import (hash mismatch) |
| F-016 | warn | external drawing | not human-confirmed, or the confirmation is stale; delivery build refuses it |
| E-013 | error | utility model | the delivery has no drawings |
| E-014 | error | utility model | drawings without a designated abstract drawing, or the abstract drawing is not delivered (W-003 warn for inventions) |
| E-015 | error | external drawing | an external drawing was replaced/changed or lost its human confirmation after delivery |

## 5. Utility-model delivery (differences on the D line)

1. `draft plan --type utility_model` → add `abstract_figure` to the plan;
2. atoms describe **shape, structure, position and connection** only; all claims are `product`;
3. structure drawings follow §3 (import → confirm); the "description of drawings" cites every
   figure (Fig. 1, Fig. 2…);
4. `draft audit` with zero errors → `draft gate --to review_draft`;
5. `deliver build` → `deliver check` (E-013/E-014/E-015 must be zero) → human `deliver sign`
   → `draft gate --to release_ready`. The DOCX opens with the utility-model title line and has a
   separate abstract-drawing section.

## 6. Boundaries

- The tool does not decide whether something *is* utility-model subject matter: D-020/D-021 rely
  on the declared category and D-023 is only a wording reminder; the attorney confirms.
- `release_ready` is still an internal delivery gate; CNIPA XML is not implemented, so never claim
  "ready to file".
- Drawing clarity, line conventions and sign placement need human per-figure review; the import
  only pins the file and its reference-sign list.
