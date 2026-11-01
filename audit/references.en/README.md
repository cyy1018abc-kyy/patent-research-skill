# patent-audit · English references

This directory mirrors the Chinese-primary runtime of the `patent-audit` skill (v4.1.0).
The Chinese edition under `../references/` is authoritative; English is maintained for
non-Chinese reviewers. Audit artifacts are named in English by design (findings.json,
audit-ledger.json, REPORT.md, NEEDS-VALIDATION.md).

| File | What it covers |
|---|---|
| `00-audit-protocol.en.md` | Modes (guidance / full audit), roles, ledger state machine, profiles, budget, terminal states |
| `01-recon-claims-map.en.md` | Phase A1: element decomposition, claims-map.md, ledger seeding, coverage_id derivation |
| `02-coverage-hunting.en.md` | Phase A2: hunter prompt, waves, coverage critic, search-strategy facets |
| `03-adversarial-validation.en.md` | Phase A3: disproof-first verifier prompt, decision rules, consolidation |
| `04-findings-contract.en.md` | Phase A4: findings.json three-verdict contract, validator usage |
| `05-independent-review.en.md` | Phase A5: review checklists, material-correction re-verification |
| `06-neutral-report.en.md` | Phase A6: REPORT.md / NEEDS-VALIDATION.md structure and neutrality rules |
| `07-anti-patterns.en.md` | Twelve anti-patterns with their hard gates |
| `SKILL.en.md` | English mirror of the skill entry point |

Methodology adapted from Cloudflare `security-audit-skill` (MIT); the harness
skeleton is reused, attack-surface content is not. The deterministic validators in
`../scripts/` re-implement the key rules in Python and say so in their file headers.
