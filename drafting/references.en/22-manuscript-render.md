# 22 · Manuscript skeleton (`draft render`, 4.3 / M3)

> The structured model (plan → atoms → claims → support mapping → figure plans) exists, yet the
> manuscript used to be typed from scratch — and numbering, dependency wording, paragraph numbers
> and drawing descriptions drift most easily while re-typing. `draft render` generates the
> **manuscript skeleton** straight from the model: what the model holds is copied, what it does not
> hold is left as an explicit `【待补：…】` slot. The renderer **never invents technical content**;
> unfilled slots are reported by `draft lint` as M-016 (error) and block delivery.

## 1. Commands

```powershell
python -m patentkit draft render --root .\workspace            # dry-run: print the three skeletons + slot counts
python -m patentkit draft render --root .\workspace --apply    # write 07_drafting/manuscript/
python -m patentkit draft render --root .\workspace --apply --force   # overwrite an existing manuscript (back it up!)
```

- With an existing manuscript, `--apply` **refuses to overwrite** (it holds human-written prose);
  pass `--force` explicitly.
- A support-mapping **suggestion** is written to `07_drafting/render/support_suggestion.json`
  (claim atom → paragraph). It is only a proposal: after
  `draft support import 07_drafting/render/support_suggestion.json --apply` it still needs the human
  semantic review `draft support review` (D-012).

## 2. What is generated, what is left open

| Part | Generated from the model | Left as a `【待补：…】` slot |
|---|---|---|
| Claims | numbering, independent/dependent structure, the reference wording "根据权利要求N所述的…" (from `parent_claim_no`), subject name, characterising part (atom texts verbatim) | the preamble of independent claims (features shared with the closest prior art); a subject name for method/use claims that do not match the plan's subject |
| Description | five part headings (by application type: 发明内容 / 实用新型内容, 本发明 / 本实用新型), consecutive paragraph numbers, one technical-solution paragraph per claim (for support mapping), the description of drawings (one line per figure from its plan title), and per figure the parts with reference signs in the detailed description | technical field, background (ledger documents only), technical problem, beneficial effects, shape/structure/connection of the parts, embodiments |
| Abstract | subject + the features of claim 1 | main use and beneficial effects |

- **A utility model protects a product**: when the plan's subject looks like a method (ends with
  方法 / 工艺), the claim subject is rendered as "一种【待补：产品名称…】" — a method subject is never
  written into utility-model claims.
- Reference signs: the description says "壳体1"; when filling the claims, write "壳体(1)" (lint M-010 reminds).

## 3. Recommended flow (before D8)

1. Model ready (`draft audit` without errors), figures planned/imported;
2. `draft render --apply` → fill every `【待补：…】` (AI drafts + human checks; anything unclear goes to
   open_questions — **never invent**);
3. `draft support import 07_drafting/render/support_suggestion.json --apply` → `draft support review`;
4. `draft lint` with zero errors (M-016 cleared) → `draft gate --to review_draft` → `deliver build`.

## 4. Guarantees and limits

- A skeleton whose slots are filled (structure untouched) lints with zero findings — locked by kernel
  tests for both utility models and inventions;
- after changing the model (atoms/claims/figures), re-rendering overwrites the manuscript: it needs
  `--force` and a manual merge of what was already written; this version has no incremental merge;
- the skeleton is a starting point for format and consistency, **not a filing-ready draft**; technical
  content and legal wording remain a human responsibility.
