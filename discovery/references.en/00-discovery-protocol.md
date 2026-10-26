# 00 · Discovery Protocol

> Full protocol of the patent-discovery skill: four stages, data contracts, the G-I control
> layer, the command index, and boundaries with the sibling skills.

## 1. Four stages (A1–A4)

| Stage | Name | Input | Kernel action | Output |
|---|---|---|---|---|
| A1 | Material intake | private R&D material | `intake register`: hash, locator scheme, parsed cache | `10_discovery/source_manifest.json` |
| A2 | Technical facts | parsed cache + AI reading | `discovery facts import`: schema + source hash binding | `technical_facts.jsonl` |
| A3 | Candidates | fact base + AI synthesis | `discovery ideas import` / `ideas rank` | `ideas/IDEA-xxx.json` |
| A4 | Confirm & handoff | candidates + inventor decisions | `facts review` / `review` / `handoff` | decision ledger + `handoff/` drafts |

Every stage is **dry-run by default**; only an explicit `--apply` writes. The AI may run a command
as a dry-run first to show the inventor what would change.

## 2. Workspace layout

```
10_discovery/
├── source_manifest.json     # contract source_manifest (schema_version 1.0)
├── materials/SRC-xxx/       # copied material (--copy); the original stays authoritative
├── parsed/SRC-xxx.txt       # parsed cache for locator resolution (not authoritative)
├── technical_facts.jsonl    # one technical_fact per line
├── ideas/IDEA-xxx.json      # one candidate per file
├── decision_ledger.jsonl    # immutable audit ledger (decisions / content changes / handoffs)
└── handoff/                 # handoff drafts (JSON + query seed + target draft)
```

The directory is created by `python -m patentkit upgrade apply`; `10_discovery` is only a default
number and can be pinned through `upgrade_layout` in `workspace.yml` (P0 upgrade layout).

## 3. Data contracts (schema_version = 1.0)

| Contract | Writer | Key fields |
|---|---|---|
| `source_manifest` | `intake register` | `source_id` (SRC-xxx), `kind`, `path`, `sha256`, `locator_scheme`, `extraction_status`, `confidentiality=private` |
| `technical_fact` | `discovery facts import` | `fact_id` (FACT-xxx), `statement`, `source_refs[]` (source_id/locator/quote/source_sha256), `support_status`, `human_review`, `uncertainties` |
| `idea` | `discovery ideas import` | `idea_id` (IDEA-xxx), `working_title`, `technical_problem`, `essential_features[]` (F-xxx + fact_refs), `technical_effects[]`, `review_status` |
| `idea_decision` | `discovery review` | `decision_id`, `idea_id`, `idea_fingerprint`, `reviewer`, `decision`, `timestamp`, `source_snapshot_sha256` |
| `discovery_handoff` | `discovery handoff` | `handoff_id` (HO-xxx), `idea_fingerprint`, `target_id`, `target_mode`, `essential_features[]`, `fact_refs[]`, `source_refs[]`, `query_seed_path` |

The single implementation is the kernel module `patentkit.contracts`; this document is only a guide.

## 4. G-I control layer (technical-fact confirmation gate)

| Group | Codes | Meaning |
|---|---|---|
| Source | G-I-001 … G-I-006 | unreadable manifest / nothing registered / unusable path / missing file / hash mismatch / missing parsed cache |
| Facts | G-I-007 … G-I-010, G-I-023 | no facts / schema violation / duplicate id / unregistered or mismatched source / unreadable ledger |
| Decisions | G-I-011 … G-I-014, G-I-025 | decision schema/duplicate/unknown idea/stale confirmation (warn)/unreadable ledger |
| Candidates | G-I-015 … G-I-018, G-I-022, G-I-024 | schema/unknown fact/no supporting fact/unconfirmed fact (warn)/duplicate idea files/unreadable dir |
| Handoff | G-I-019 … G-I-021 | invalid or missing handoff draft / stale handoff (warn) / unknown idea |

`discovery check` returns `{ok, errors, warnings}`; **handoff proceeds only with errors=0 and all
required facts confirmed**.

## 5. Command index

| Command | Purpose | Writes |
|---|---|---|
| `patentkit intake register <files…> [--apply] [--no-copy] [--kind K] [--max-bytes N]` | material intake | only with `--apply` |
| `patentkit discovery facts import <JSON/dir…> [--apply]` | fact import + validation | only with `--apply` |
| `patentkit discovery facts review --ids F1[,F2] --decision confirmed --by <label> [--apply]` | fact human confirmation | only with `--apply` |
| `patentkit discovery ideas import <JSON/dir…> [--apply] [--force]` | candidate import (forced proposed) | only with `--apply` |
| `patentkit discovery ideas rank [--json]` | search-priority ranking (never a grant probability) | read-only |
| `patentkit discovery review <decision JSON/dir…> [--apply]` | fingerprint-bound candidate confirmation | only with `--apply` |
| `patentkit discovery status / check [--json]` | overview / G-I check | read-only |
| `patentkit discovery handoff --idea IDEA-001 [--target TGT-0002] [--apply]` | research handoff draft | only with `--apply` |

## 6. State machine and audit

```
proposed ──confirm──> confirmed ──(content change)──> stale (old decision kept, re-review needed)
    │
    └──reject──> rejected
```

- Ledger events: `fact_review`, `decision` (idea_decision), `content_changed`, `handoff` — append-only.
- Confirmation binds the *content* fingerprint (excluding `review_status`); status changes never
  invalidate it, technical content changes do.

## 7. Boundaries with the other skills

| This skill | Goes to |
|---|---|
| Material intake / facts / candidates / confirmation / handoff draft | — |
| Search, novelty, evidence levels, G-S acceptance gates | `patent-research` |
| Disclosure, claims, specification, office action response, revision loop | `patent-drafting` |
| Novelty / inventive step / grant prediction | **nobody**; this skill produces no legal conclusion |

## 8. Failure modes (report, never bypass)

1. Material outside the workspace without `--copy` → explicit error;
2. Material changed (hash mismatch) → conflict; re-register, never silently overwrite;
3. PDF without text layer / encrypted / scanned → recorded as unsupported/failed;
4. Binary `.slx/.mdl` model → rejected; export controlled text/CSV first;
5. Contract violation in FACT/IDEA JSON → refuse to write with field-level issues;
6. Handoff before confirmation → blocked by G-I with all reasons listed (no force);
7. Tools unavailable → start the answer with "⚠️ 未经验证工具校验".
