# patentkit 0.10.0

Companion kernel for Patent Research Skill 3.10.0; Python 3.11+. Assessment protocol 1,
G-S-01…05 semantics, the evidence three-tier system and rules V001–V038 are unchanged;
no rule changes. Purely additive release.

## What changed

- **Deadline presets expanded to the 2025 Examination Guidelines practice**
  (`patentkit/deadlines.py`). The ledger previously carried four presets (application fee
  2 months / examination request 3 years / first OA response 4 months / annuity by
  anniversary). Six new presets, each citing its guideline anchor in the note field:

  | preset | base event | period |
  |---|---|---|
  | `oa_response_subsequent` | subsequent OA mailing date | 2 months |
  | `registration` | grant-and-registration notice mailing date | 2 months (divisional window ends with it) |
  | `reexamination` | rejection decision mailing date | 3 months (appeal within 3 months of the reexamination decision) |
  | `pte_drug` | China marketing-approval date | 3 months to request drug patent-term extension |
  | `pte_delay` | grant announcement date | 3 months to request compensation for unreasonable delay |
  | `biological_deposit` | filing date | 4 months for deposit/viability certificates |

- **No workspace migration**: unknown ledger types keep the custom fallback
  (`months` given explicitly or `unknown-period`), so existing
  `09_deadlines/deadlines.yml` files parse unchanged. `deadlines init` templates list
  the new types.
- Everything else is byte-identical to 0.9.0 (explicit-LF discipline intact; the patch
  rebuild was verified byte-identical against the dev-tree mirror).

## Install

```bash
python -m pip install ./patentkit-0.10.0-py3-none-any.whl
```

Deadlines remain a reminder ledger, not legal advice; the official notice prevails.
