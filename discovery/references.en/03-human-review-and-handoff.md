# 03 · Human Review and Research Handoff

> A4 stage: human confirmation of facts and candidates, confirmation invalidation, and the
> handoff draft for `patent-research`. Core rule: AI only proposes, the inventor confirms; the
> handoff is a draft, not a search conclusion.

## 1. Fact human confirmation (G-I prerequisite)

Facts behind essential features must be `human_review = confirmed`, otherwise the handoff blocks.

```powershell
python -m patentkit discovery facts review --ids FACT-001,FACT-002 --decision confirmed --by inventor --root .\workspace
python -m patentkit discovery facts review --ids FACT-001,FACT-002 --decision confirmed --by inventor --root .\workspace --apply
```

`--by` is an audit label, not identity proof. Rejected facts remain in the ledger (not deleted) but
block candidates that reference them. Repeating the same decision is idempotent.

## 2. Candidate human confirmation (content-fingerprint bound)

The inventor reviews `ideas/IDEA-xxx.json` and records a decision document:

```json
{
  "schema_version": "1.0",
  "decision_id": "DEC-001",
  "idea_id": "IDEA-001",
  "idea_fingerprint": "<current candidate content fingerprint>",
  "reviewer": "inventor",
  "decision": "confirmed",
  "reason": "complete and implementable",
  "timestamp": "2026-10-26T10:30:00+08:00",
  "source_snapshot_sha256": "<material snapshot hash at confirmation>"
}
```

```powershell
python -m patentkit discovery review .\decisions --root .\workspace            # preview
python -m patentkit discovery review .\decisions --root .\workspace --apply    # record + update status
```

Fingerprint rules: confirmation binds the **content** fingerprint (canonical JSON SHA-256,
excluding `review_status`). Status-only changes never invalidate it; any technical content change
(title, problem, features, effects, relations, uncertainties, scores) does. Stale confirmations are
kept in the ledger (`G-I-014` warn), block the handoff, and require re-review with a new decision id.
AI cannot self-confirm or overwrite decisions; a document whose fingerprint does not match the
current content is refused.

| decision | Effect |
|---|---|
| `confirmed` | candidate review_status=confirmed, eligible for handoff |
| `rejected` | candidate review_status=rejected, not eligible |
| `revision_requested` | candidate back to `proposed`; revise and review again |

## 3. Handoff draft

Preconditions: `discovery check` has no errors; the candidate confirmation is valid; every essential
feature references facts; the referenced facts are all confirmed; source registration and hashes all
match. Any missing condition blocks the handoff and lists every reason (no `--force`).

```powershell
python -m patentkit discovery check --root .\workspace
python -m patentkit discovery handoff --idea IDEA-001 --root .\workspace
python -m patentkit discovery handoff --idea IDEA-001 --root .\workspace --apply
```

Outputs (all under `10_discovery/handoff/`, never in the public package):

| File | Content |
|---|---|
| `IDEA-001.handoff.json` | contract `discovery_handoff`: target (existing/new_target_proposal), features/facts/sources, search axes, content fingerprint, query seed path |
| `IDEA-001.search_seed.md` | zh/en query seeds per axis; explicitly states no search has been run and no G-S is computed |
| `IDEA-001.target_draft.md` | proposed target/axes draft; does not modify `workspace.yml` or existing target data |

Audit: the ledger appends a `handoff` event (handoff_id/idea_id/idea_fingerprint/target_id/target_mode/timestamp).

## 4. What the handoff does NOT do

1. It does not write `01_search_plan/query_library.yml`, nor modify `workspace.yml`/target data;
2. It produces no G-S PASS/FAIL and no novelty/inventive-step assessment;
3. It does not replace the research `queryplan` / fetch / ingest / review / gates pipeline;
4. It never hands off unconfirmed content (G-I blocks);
5. It never puts real material into the public repo, samples or logs.

## 5. After handoff (patent-research)

1. Use `patentkit queryplan` to close uncovered concept groups (query seeds are only a start);
2. Fetch/ingest through the existing pipeline, then `review` (AI assessment + human confirmation);
3. `patentkit validate` / `gates` produce the formal result — only the research-side G-S and
   evidence levels are acceptance evidence;
4. Drafting follows with `patent-drafting` once the research gates are ready.

## 6. Audit ledger events

| Event | Trigger | Key fields |
|---|---|---|
| `fact_review` | `discovery facts review --apply` | fact_id / decision / reviewer / timestamp |
| `decision` (idea_decision) | `discovery review --apply` | decision_id / idea_id / idea_fingerprint / decision / reviewer / timestamp |
| `content_changed` | `ideas import --force` with changed content | idea_id / old_fingerprint / new_fingerprint / timestamp |
| `handoff` | `discovery handoff --apply` | handoff_id / idea_id / idea_fingerprint / target_id / target_mode / timestamp |

The ledger is append-only; rewriting history is never acceptable.
