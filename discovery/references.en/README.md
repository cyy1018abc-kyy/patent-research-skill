# patent-discovery · English references

This directory mirrors the Chinese-primary runtime of the `patent-discovery` skill (v3.4.0).
Terms follow the shared glossary at `../references/glossary.md`; CI checks the pairing.

| File | What it covers |
|---|---|
| `00-discovery-protocol.md` | Four stages (A1–A4), data contracts, G-I control layer, command index, boundaries |
| `01-material-intake.md` | Supported sources, locator schemes, security rules, common intake failures |
| `02-facts-and-ideas.md` | FACT / IDEA schemas, state machine, search-priority ranking, good/bad examples |
| `03-human-review-and-handoff.md` | Fact review, fingerprint-bound candidate confirmation, handoff gating and outputs |
| `SKILL.en.md` | English mirror of the skill entry point |

The Chinese edition under `../references/` is authoritative. English is maintained for
non-Chinese reviewers; both sides must pass `evals/check_terminology.py`.
