# 12 Policy radar: tracking examination-practice and form changes

> Benchmark: patent-exam-policy of patent-disclosure-skill. **The tool does not sniff the
> web automatically** (confidentiality boundary); this is a **manual checklist**: sweep it
> before starting / before hand-off, and translate "the practice changed" into "which step
> of this workflow is affected".

## Sources to check (officials prevail)

| Source | What to look at | What it affects |
|---|---|---|
| CNIPA "Examination Guidelines" **2025 edition** | full-text comparison completed 2026-10-31; 15 change points and their dispositions are logged in the first row of `docs/policy-log.md`; only watch for the next revision notice from here | research references 02/03/04, drafting references 09/10/11, deadline PRESETS (aligned in the skill 3.10.0 round) |
| CNIPA "Examination Guidelines" revision notices | inventive-step practice, claim forms for computer programs / algorithms | three-tier determination summary in [00](00-prerequisites.md), claim forms in [10](10-claim-drafting.md) |
| CNIPA forms / book-style pages | request / abstract / fee-reduction form versions | the application-document list in [09](09-disclosure-drafting.md) |
| cponline upload requirements | drawing resolution / format / size limits | `patentkit figures` (full spec in the research skill's reference 08) |
| Patent Law / Implementing Regulations amendments | deadlines (application fee / examination request / OA responses), grace periods | the PRESETS of `patentkit deadlines` and [11](11-oa-response.md) |
| Abnormal-application identification practice | claim stacking, same-day filing strategy | the 1+N portfolio advice (`patentkit layout`) in [09](09-disclosure-drafting.md) |

## The change-log format

When a practice change is found, add one row to the repository's `docs/policy-log.md`:

```markdown
- 2026-XX-XX | Source: official notice URL | Change: one sentence | Affects: references/XX §X | Status: fixed / pending + owner
```

**A logged-but-unfixed change counts as unresolved** — the hand-off checklist must clear
the "pending" rows of policy-log.

## Practices already frozen into tools (changing them means changing the kernel)

- deadline presets: `patentkit/deadlines.py` PRESETS (application fee 2 months /
  examination request 3 years / OA 4+2 months / registration 2 months / reexamination 3 months /
  drug-PTE and delayed-grant compensation 3 months each / deposit certificates 4 months /
  annuities by anniversary — expanded after the 2025-practice reconciliation);
- drawing requirements: `patentkit figures` (black-white line drawings, mark consistency);
- the five gates: `patentkit/gates.py` (changes go through CHANGELOG + regression tests,
  never a verbal loosening).

> **Statutory deadlines follow the official documents**: the deadline tool is a reminder
> ledger, not legal advice; rules such as the 15-day presumption for electronic service
> follow the current regulations.

## Suggested cadence

- At the start of every new project: full sweep (within half an hour);
- Before hand-off: only the two rows that affect the hand-off artifacts (forms + drawings);
- Quarterly: diff against the Examination Guidelines revision index once.
