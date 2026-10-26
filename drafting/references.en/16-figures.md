# 16 · Professional Figures (figure plan / render / validate)

> The P3 figure engine: a structured **figure plan**, deterministic rendering and figure-text
> consistency checks. Principle: **layout never decides technical facts** — the renderer can only
> draw what the plan says (it must not create or delete parts/edges); automated checks are
> mechanical bookkeeping and **never replace human visual review**; formal drawings must not rely
> on text-to-image generation alone.

## 1. Figure plan (`07_drafting/figures/*.figure.yml`)

```yaml
figure_id: FIG-1
type: block_diagram          # block_diagram | flowchart | connection | state_machine
title: 图1 system block diagram
parts:                        # flowcharts use steps; state machines use states
  - id: S1
    label: detection unit
    source_refs: [FACT-001]
  - id: S2
    label: control unit
connections:
  - { from: S1, to: S2, label: load-ramp signal }
mark_mapping: { S1: "10", S2: "20" }   # reference signs (1–3 digits; same sign across figures = same part)
layout_options: { direction: LR, columns: 3 }
spec_refs: ["0005"]          # specification paragraphs citing this figure
```

Legacy specs are normalized (`figure:` = figure_id, `name:` = label, numeric ids keep their sign).
Type requirements: `block_diagram`/`connection` need `parts`; `flowchart` needs `steps`;
`state_machine` needs `states`. Flowchart nodes may carry `kind: terminal|decision|process|data`
(shape only, never a technical fact).

## 2. Commands

```powershell
python -m patentkit figures plan --root .\workspace            # dry-run
python -m patentkit figures plan --root .\workspace --apply
python -m patentkit figures render FIG-1 --root .\workspace
python -m patentkit figures render FIG-1 --root .\workspace --format png   # optional 300 DPI
python -m patentkit figures validate --root .\workspace
python -m patentkit figures check --root .\workspace          # existing V033 mark check
python -m patentkit figures draw FIG-1 --root .\workspace     # existing simple renderer
```

## 3. Validation codes (`figures validate`)

| Code | Level | Meaning |
|---|---|---|
| F-001 | error | invalid YAML / contract schema violation |
| F-002 | error | duplicate figure_id across files |
| F-003 | error | duplicate node id |
| F-004 | error | dangling connection endpoint (invalid edge) |
| F-005 | warn | isolated node (not connected) |
| F-006 | error/warn | mark mapping references unknown nodes / missing marks / duplicate mark in one figure (error) / same sign across figures (warn: confirm it is the same part) / non-numeric mark (error) |
| F-007 | error | type-required content empty (e.g. flowchart without steps) |
| F-008 | error/warn | manuscript cites a missing figure (error) / figure never cited (warn) |
| F-009 | error/warn | support mapping references an unknown figure (error when plans exist; warn while no figures exist yet) |
| F-010 | warn | drafting-plan drawing requirement not covered by any figure plan |
| F-011 | error | invalid layout options (direction/columns) |
| F-012 | warn | duplicate edge |
| F-013 | warn | self-loop edge |
| F-014 | warn | `source_refs` is not a FACT id |
| V033 | warn | existing bidirectional reference-sign check (heuristic; warns only) |

## 4. Deterministic rendering contract

- Same plan → **byte-identical** SVG; no timestamps, no scripts, no external links (xmlns only).
- Geometry follows plan order and `layout_options`; orthogonal edges with fixed arrowheads;
  black lines on white, no gradients.
- SVG is the canonical output. PNG (300 DPI) is optional via Pillow; cross-platform fonts may
  differ slightly, so PNG is not byte-regressed. A missing converter is reported as not generated
  — never faked.
- The renderer **cannot invent or drop** parts/edges: what the plan has is drawn, nothing more.

## 5. Discipline and human review

1. The plan is written by humans/AI from **confirmed facts**; the renderer makes no technical judgment.
2. Automated checks prove mechanical consistency only — **the technical structure must be reviewed visually by a human**.
3. After revisions: re-run `figures validate`, re-render, and check `draft impact` for affected
   paragraphs/figures.
4. Submitted drawings are black-white line art; complex engineering drawings may import verified
   CAD originals instead of auto-layout.
5. Before P4 implements `release_ready`, figures are draft material only — never call them
   "ready to submit".
