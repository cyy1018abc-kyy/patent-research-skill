# 01 — Phase A1: overview, claim-element decomposition, coverage ledger

> Corresponds to Reconnaissance + coverage-ledger in the original
> (security-audit-skill); coverage dimensions change from
> "entry surface × trust boundary × subsystem × attack class" to
> "element × data source × classification symbol".

## 1. Overview agents (four questions; parallel in multi-agent, sequential rounds in single-agent)

Read-only access to the audited workspace and the skill's method documents; no
network, no new searches. Every answer carries workspace-relative locations
(path + paragraph/line) and returns to the planner.

- **1a Target and claims**: what is the technical solution? Independent-claim
  elements one by one, dependent-claim added features, claimed technical effects.
  Extract from `07_drafting/claims.md` (or target_claims) and `00_methodology`,
  with a locator per element.
- **1b Existing evidence inventory**: what do `02_search_logs/` (incl. raw/ and
  query logs), `03_candidates/`, `04_comparative_analysis/`,
  `05_novelty_conclusions/` contain? Per log: source, query, hit count,
  capture_mode. Which candidates have citations, which are narrative only?
- **1c Sources and classification map**: which data sources were used
  (CNIPA/OPS/EPO/other)? Which IPC/CPC symbols and time windows? What did the
  declared search protocol (`01_search_plan`) promise?
- **1d Baseline comparison**: what is the conventional search baseline for this
  domain (typical source classes, classification faces, NPL coverage)? Calibration
  only — never a coverage exemption.

## 2. claims-map.md (≤1000 words)

The planner synthesizes into `claims-map.md`:

1. One-sentence target + claimed subject-matter type;
2. **Element table**: one row per element — element ID (`E-01`… or aligned with
   existing F numbers), statement, source locator, linked technical effect;
3. Data-source list (scope and known limits per source);
4. Classification list (initial relevant faces, with certainty flags);
5. Prior-run gaps / changed-source revalidation targets (when older runs exist).

Element IDs anchor every later finding and ledger unit; never rename within a run.

## 3. Seeding audit-ledger.json

Seed one unit per material combination of "element × source × classification
group" (profile coarsening in `00-audit-protocol.md` §7). Out-of-scope
combinations are recorded `out_of_scope` — never `covered`.

```json
{
  "schema_version": "patent-audit-ledger/1",
  "run_id": "…",
  "target": "…",
  "profile": "standard",
  "mode": "single",
  "units": [
    {
      "coverage_id": "E-01::cnipa-fulltext::G06F",
      "canonical_refs": {
        "element": "claims-map.md#E-01",
        "source": "02_search_logs/queries.jsonl#cnipa-fulltext",
        "klass": "claims-map.md#klass/G06F"
      },
      "element": "send-time estimate corrected by queue-depth prediction",
      "source": "cnipa-fulltext",
      "klass": "G06F",
      "starting_paths": ["02_search_logs/raw/"],
      "query_plan_block": null,
      "prior_status": "none",
      "attempts": [],
      "wave": 1,
      "status": "planned",
      "agent_id": null,
      "reviewed_paths": [],
      "checks": [],
      "result_fingerprints": [],
      "unresolved": []
    }
  ]
}
```

## 4. coverage_id derivation (deterministic; the validator recomputes it)

1. All three canonical references must be Unicode NFC, without control/format/
   separator code points, without surrounding whitespace;
2. Percent-encode each reference's UTF-8 bytes per RFC 3986 (only
   `A-Z a-z 0-9 - . _ ~` unescaped; uppercase `%HH` otherwise);
3. Join as `element::source::klass`.
4. Two different canonical references for one semantic combination = canonical
   identity collision, never silently merged; duplicate coverage_id is an error.

## 5. Check records (append-only within a unit)

| Field | Requirement |
|---|---|
| `agent_id` | Executor (single-agent mode uses phase IDs such as `a2-hunter`) |
| `method` | `search` (a search ran, log artifact attached) / `source` (document review, no artifact) / `local` (local verification, promoted artifact attached) |
| `description` | Query or review target and the judgment |
| `reviewed_paths` | Workspace paths actually read this time (non-empty) |
| `artifact` | For `search`/`local`: relative path under `agents/<agent_id>/artifacts/`; null for `source` |

Unit-level `reviewed_paths` always equals the union of all checks. Run
`python audit/scripts/validate_ledger.py <ledger>` after seeding and after every
ledger update; fix every error before assigning hunting work.

## 6. Prior-run intake

With older runs, read their ledgers and findings one by one: same-source
confirmed → carry (`prior_status: "prior_confirmed_same_source"`) but re-pass
current independent validation; changed source → build a revalidation unit; prior
needs_validation/deferred/blocked/out_of_scope → all become current `planned`.
A prior ledger's gaps are not evidence that anything was searched.
