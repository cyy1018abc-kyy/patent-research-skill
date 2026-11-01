---
name: patent-discovery
description: >
  Patent point mining from R&D material: source material intake, technical fact extraction,
  patent candidate generation and ranking, inventor human confirmation (content-fingerprint
  bound), and a research handoff draft for the patent-research skill.
  This skill only produces candidates plus a gap list; it never replaces the search evidence
  chain and never predicts novelty, inventive step or grant. When tools are unavailable or not
  running, answers must begin with "⚠️ 未经验证工具校验".
  Use when the user wants to organize R&D material, find patent points in design documents,
  code or simulation data, extract technical facts, propose or review patent candidates,
  confirm an invention point, or hand a candidate over to prior-art search.
license: Apache-2.0
metadata:
  version: 4.1.0
---

# Patent Discovery

> **Companion**: `patentkit >= 0.10.0` (single implementation of rules and data contracts) and the
> sibling skills `patent-research` (search, evidence chain, acceptance gates) and
> `patent-drafting` (drafting).
> **Position**: turn private R&D material into traceable, human-confirmed, handoff-ready patent
> candidates. Output always carries a gap list; only the inventor confirms, model output is
> always proposed.

## When to use

| Use | Do not use |
|---|---|
| Source material intake (Word/PDF/Markdown/code/CSV/controlled Simulink export) | Search, novelty check, acceptance gates (use patent-research) |
| Extract technical facts with per-fact source locator and quote | Draft disclosure/claims/specification (use patent-drafting) |
| Propose 3–5 patent candidates and rank search priority | Judge novelty/inventive step/grant probability (nobody does) |
| Inventor human confirmation of facts and candidates (fingerprint-bound) | Edit search candidates or evidence levels (research domain) |
| Generate a handoff draft (target/axes/query seeds) for search | Treat candidates as search results or G-S conclusions |

## Execution order (four stages; dry-run every step first)

| # | Stage | Read | Do |
|---|---|---|---|
| A1 | Material intake | [`01-material-intake`](01-material-intake.md) | `python -m patentkit intake register <files…> [--apply]` |
| A2 | Technical facts | [`02-facts-and-ideas`](02-facts-and-ideas.md) | AI extraction → FACT JSON → `patentkit discovery facts import <JSON…> --apply` |
| A3 | Candidates | [`02-facts-and-ideas`](02-facts-and-ideas.md) | Propose 3–5 IDEA → `discovery ideas import … --apply` → `discovery ideas rank` |
| A4 | Confirm & handoff | [`03-human-review-and-handoff`](03-human-review-and-handoff.md) | `discovery facts review` → `discovery review <decisions…> --apply` → `discovery handoff --idea IDEA-001 --apply` |

Full protocol and the G-I check table: [`00-discovery-protocol`](00-discovery-protocol.md).

## Hard constraints (non-negotiable)

1. **Raw material stays in the private workspace**: never upload or export it; never execute
   code/macros/models from it (binary `.slx/.mdl` models are rejected — export controlled text first).
2. **No source, no fact**: every technical fact carries a registered source id, a locator
   (line/paragraph/page) and a quote whose hash matches `source_manifest`; anything else goes to uncertainties.
3. **Model output is always proposed**: AI may propose facts and candidates but can never
   self-confirm; confirmation comes only from an inventor's human decision.
4. **Confirmation binds the content fingerprint**: any substantive technical change invalidates
   the old confirmation (the audit record is kept); re-confirmation is required.
5. **Never invent effects**: unverified technical effects stay `to_be_verified`; inference is
   never presented as experimental proof.
6. **Never pre-judge the search**: novelty/inventive step/grant are computed only by
   patent-research on real search evidence; this skill produces no G-S PASS/FAIL.
7. **G-I must PASS before handoff**: unconfirmed candidates/facts, unknown sources or hash
   mismatches block the handoff with no bypass switch.
8. When tools are unavailable or not running, answers must begin with
   "⚠️ 未经验证工具校验" (unverified by tool checks) and must not pretend otherwise.

## Result format (always include every row)

| Item | Requirement |
|---|---|
| **Candidate status** | Per-IDEA review_status (proposed/confirmed/rejected) and whether the confirmation fingerprint is valid |
| **Source trace** | Each essential feature → FACT → source id + locator + hash verification result |
| **Gap list** | Unverified effects, missing material, items pending inventor confirmation |
| **Handoff summary** | G-I result (error/warn counts) + handoff file paths + next search commands |
| **Unverified note** | When tools/data are missing, state "⚠️ 未经验证工具校验" explicitly |

## References (load on demand)

| File | When |
|---|---|
| [`00-discovery-protocol.md`](00-discovery-protocol.md) | Read first: four stages, contracts, G-I table, command index |
| [`01-material-intake.md`](01-material-intake.md) | Material intake, supported formats, locators, security boundaries |
| [`02-facts-and-ideas.md`](02-facts-and-ideas.md) | FACT/IDEA fields, state machine, ranking, good/bad examples |
| [`03-human-review-and-handoff.md`](03-human-review-and-handoff.md) | Human confirmation, invalidation, handoff gating and outputs |
| `references/glossary.md` (shared glossary, CI-locked across the three skills) | zh↔en terminology (same copy across the three skills, CI-locked) |

> Commands are `python -m patentkit <subcommand>` (intake / discovery); this skill ships no
> scripts — rules and data contracts live in the kernel. Installed payloads must not rely on
> `../` links between skills; use the documented skill handoff instead.
