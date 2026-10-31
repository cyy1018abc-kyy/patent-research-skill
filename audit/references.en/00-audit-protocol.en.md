# 00 — Audit protocol (modes, roles, state machine, terminal states)

> Authoritative protocol for full-audit mode. Guidance mode only needs §1 and §8.
> The harness skeleton is adapted from Cloudflare `security-audit-skill` (MIT);
> attack-surface content is not ported — coverage units, verdict semantics and the
> artifact contracts are rewritten for the patent-search domain.

## 1. Two modes

| | guidance (default) | full audit (explicit authorization) |
|---|---|---|
| Allowed actions | Method explanation, single-point checks, partial coverage review | Six phases end to end + writing `12_audit/run-<N>/` |
| Files written | No audit artifacts | Only the contract files inside the run directory |
| Trigger phrasing | "check this citation", "is coverage enough" | "full audit", "comprehensive audit", "produce an audit report" |

Ask one focused question before creating files when the request is ambiguous.
**Loading this skill does not authorize a full audit.**

## 2. Roles and isolation

| Role | Duty | Isolation requirement |
|---|---|---|
| **Planner (parent)** | Seeds the ledger, assigns work, consolidates, writes shared files | Sole writer of ledger and findings |
| **Hunter** | Claims ledger units, executes searches/reviews, records checks | One claim per unit; never judges other units |
| **Critic** | Reviews ledger and checks for blind spots, proposes reassignment | Runs after every wave; never fills gaps itself |
| **Verifier** | Tries to disprove each candidate mapping (phase A3) | Never the candidate's author |
| **Reviewer** | Verifies final records' quotes/locators/categories (phase A5) | Fresh context; no verifier memory carried over |

**Single-agent sequential mode (default)**: one session executes the six phases in
order; role switches reset task state (only the inputs §4 allows) and use separate
rounds to emulate isolation. `--multi-agent` (explicit user request) enables
parallel isolated agents; write-isolation rules in §5 then apply.

## 3. Artifact contract (run-metadata.json)

Before a full audit starts, the planner writes the run directory
`12_audit/run-<N>/` (N is the next unused integer; `--output` may point outside the
workspace but never inside another directory of the audited workspace):

```json
{
  "run_id": "audit-<target>-run-<N>",
  "target": "TGT-xxxx (or patent number / project code)",
  "workspace": "audited workspace root (read-only)",
  "source_ref": "audit baseline: git commit or file-hash snapshot of key workspace artifacts",
  "profile": "quick | standard | deep",
  "mode": "single | multi",
  "scope_paths": ["02_search_logs", "03_candidates", "..."],
  "budget": {"rounds": 12, "note": "single-agent mode uses a round budget"},
  "claims_map": "claims-map.md",
  "ledger": "audit-ledger.json",
  "findings": "findings.json",
  "run_status": "in_progress | complete | incomplete",
  "incomplete_reason": "non-empty only when incomplete"
}
```

Update metadata only when facts change; candidate state lives only in the ledger
and findings.json.

## 4. Minimal-input principle (the substance of isolation)

Each role receives only the minimum input its duty requires:

- Hunter: the claimed unit's coverage_id, starting_paths, applicable search-strategy
  blocks; **not** other units' results or other roles' conclusions.
- Verifier: the candidate record itself + the unit's check paths + the matching
  verdict branch of `04-findings-contract.md`; **not** the proposer's reasoning or
  another verifier's conclusion.
- Reviewer: the final record + the evidence documents themselves; **not** any A3
  verdict memory.

## 5. Write isolation

`run-metadata.json`, `claims-map.md`, `audit-ledger.json`, `findings.json`,
`REPORT.md`, `NEEDS-VALIDATION.md` are planner-only. In multi-agent mode each agent
gets `agents/<agent-id>/` (lowercase, `^[a-z0-9][a-z0-9_-]{0,63}$`, no Windows device
names) with `scratch/` (agent-writable) and `artifacts/` (retained only after
parent-side promotion); agents never modify shared files, the audited workspace, or
each other's directories. In single-agent mode the session writes all artifacts
directly — equivalent to "the planner writes everything".

## 6. Coverage-ledger state machine

Ledger unit states (`audit-ledger.json`, schema in `01-recon-claims-map.md` §4):

| Status | agent_id | reviewed_paths / checks | result_fingerprints | unresolved |
|---|---|---|---|---|
| `planned` | null | empty | empty | empty |
| `not_applicable` / `out_of_scope` / `deferred` | null | empty | empty | reason required |
| `in_progress` | claimer | empty | empty | empty |
| `blocked` | claimer | both non-empty (partial evidence) | empty | blocker required |
| `covered` | claimer | both non-empty | empty | empty |
| `candidate` | claimer | both non-empty | non-empty | optional |

Rules:

1. **The ledger is the coverage claim.** No narrative "I searched it" counts as
   coverage; only checks in the unit (one per search/review: executor, method,
   query or review target, documents hit) count.
2. `attempts` is an append-only archive: before the critic reassigns a unit, append
   the prior state, owner, checks, fingerprints and `reassignment_reason`; then
   wave+1, new owner, empty live evidence. Only blocked/covered/candidate states
   may be archived.
3. Multiple runs are additive: read prior ledgers and findings; **same-source
   confirmed** records may be carried but must pass current independent validation
   again; **changed-source units** must be re-hunted; prior
   needs_validation/deferred/blocked all become current work. No prior state
   suppresses current coverage.

## 7. Profiles and budget

| profile | Use | Hunting | Critic | Validation/review |
|---|---|---|---|---|
| `quick` | Small targets, re-checks, fast look | Coarsen units to element×source (klass merged), exactly 1 wave | Exactly 1 (post-wave) | A3 and A5 merged into one independent review |
| `standard` | Default | Full ledger hunting, waves to a clean pass | Per wave + one distinct final | A3, A5 separate |
| `deep` | High-stakes targets | Units split per element, waves to a clean pass | Per wave + one distinct final | A3, A5 separate; sampled second pass on covered units |

Budget = a **round budget** in single-agent mode (derive a default from target size
and record it in metadata). Reserve first: the A1 overview round, one critic round
per wave, the final critic round, and at least one verification/review round. When
the remainder cannot fund the reserves: launch no hunting, mark affected units
`deferred` (reason `budget_cannot_reserve_critics_and_validation`), set
`run_status` to `incomplete`, and disclose in the report. **Never exceed a set
budget silently, and never skip independent review.**

## 8. Coverage computation and the two mandatory metrics

- **Ledger coverage** = covered units ÷ actionable units (total − not_applicable −
  out_of_scope). Goes into REPORT §7; quick/scoped runs must call themselves partial.
- **Verifier overturn rate** = candidates demoted or refuted in A3/A5 ÷ candidates
  entering independent validation. A non-zero rate is direct evidence of
  single-agent self-assessment inflation; record it plainly in REPORT.

## 9. Terminal states (exactly two, never stop mid-phase)

1. **complete**: all A6 artifacts written, both validators pass, and every ledger
   candidate has an independent disposition (confirmed/needs_validation/rejected
   or an explicit incomplete reason).
2. **incomplete**: `run_status: "incomplete"` + an exact `incomplete_reason`
   (e.g. `validation_budget_exhausted`,
   `budget_cannot_reserve_critics_and_validation`), with the gap disclosed on the
   report's first page; unvalidated candidates stay in the ledger only and **never
   enter findings.json**.

## 10. Boundary with the audited workspace

- Read-only workspace; never run `--apply`/`--run`/`--force`/`--fill`.
- Fix suggestions (extra queries, re-citations) go into the REPORT suggestions
  section and are executed only through the normal `patent-research` flow.
- Deployment-side facts absent from the workspace (family legal status, prosecution
  history) must not be guessed — handle as needs_validation with the missing fact
  and a verification plan.
