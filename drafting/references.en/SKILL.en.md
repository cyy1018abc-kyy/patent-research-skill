---
name: patent-drafting
description: >
  Patent drafting (draft-grade): disclosures (invention / utility model), claims and
  specification skeletons, office-action (OA) response drafts, the multi-round revision
  loop, and drafting-time numerical provenance, figure-mark and policy-practice checks.
  The precondition is a ready evidence chain on the search side (the patent-research
  skill); this skill produces **drafts and flags gaps** — it does not replace a patent
  attorney and never predicts grant. When tools are unavailable or not running, answers
  must begin with "⚠️ Unverified by tool checks".
  Use when the user wants to write a disclosure, draft claims, write the specification,
  turn invention points into application documents, respond to an office action / OA,
  revise with a change trail, or check whether a number may be written into a claim.
  Prefer triggering on phrases such as "write a disclosure", "how to write the claims",
  "specification support", "how to answer the OA", "revision loop",
  "can this number be written in".
license: Apache-2.0
metadata:
  version: 3.0.1
---

# Patent Drafting (draft-grade)

> **Companions**: `patentkit >= 0.3.0` (the single implementation of the rules) and the
> sibling skill `patent-research` (evidence chain and acceptance gates).
> **Position**: convert the search results into deliverable drafts — disclosure, claims /
> specification skeleton, OA response. The output is always "draft + gap list"; it is not
> legal advice and never predicts grant.
>
> This file mirrors the authoritative Chinese `../SKILL.md`.

## When to use

| Use | Do not use |
|---|---|
| Five-part disclosure drafting (invention / utility model) | Search / novelty / acceptance gates (use the patent-research skill) |
| Claim layering and numerical-range self-checks | Issuing legal opinions or replacing a patent attorney |
| Specification support mapping, embodiment organization | Predicting grant probability (nobody may promise it) |
| OA clause-splitting, back-linking, response drafts | Infringement analysis (not done by default, see docs/scope-decisions.md) |
| Multi-round revision: patch → change log → re-run gates | Editing search data / candidate lists (that is the research domain) |

## Preconditions (if unmet, go back to the research skill first)

1. **G-S-01 through G-S-03 met** (`patentkit gates`, verified column) — drafting a
   disclosure on insufficient search writes the risk into the claims;
2. the comparison matrix is filled; every column-D document carries an evidence level and
   judgment state (`patentkit ledger`);
3. the numerical-claim provenance registry exists (`patentkit provenance scan`).

A self-contained summary of the preconditions is in
[`references/00-prerequisites.md`](references/00-prerequisites.md).

## Execution order (per line, on demand; do not expand everything)

### Line A: disclosure / application documents

| # | Step | Read | Do |
|---|---|---|---|
| A1 | Reconcile | [00](references/00-prerequisites.md) | `patentkit ledger`: the background cites ledger IDs only (V034 discipline) |
| A2 | Skeleton | [09](references/09-disclosure-drafting.md) | five-part drafting; unclear points go to open_questions, **no fabrication** |
| A3 | Claims | [10](references/10-claim-drafting.md) | zero-disclosure atoms into the independent claim; numerical layers inside grade-A provenance |
| A4 | Self-check | [10](references/10-claim-drafting.md) | `patentkit provenance check` + per-atom support mapping table |

### Line B: OA response

| # | Step | Read | Do |
|---|---|---|---|
| B1 | Deadlines | [11](references/11-oa-response.md) | `patentkit deadlines list` (official mailing date prevails) |
| B2 | Split clauses | [11](references/11-oa-response.md) | one row per objection; examiner's documents enter the candidates first |
| B3 | Back-link | [11](references/11-oa-response.md) | feature chart reusing the matrix format; arguments via the three-tier determination in reverse |
| B4 | Amendments | [13](references/13-revision-loop.md) | any claim amendment follows the loop: patch → log → attest → re-run gates |

### Line C: policy practice (sweep at start / before hand-off)

Read [12](references/12-policy-radar.md); log practice changes in `docs/policy-log.md`;
the hand-off may not proceed with "pending" rows uncleared.

## Hard constraints (must not be violated)

1. **Search before drafting**: when the preconditions fail, go back to the research skill
   instead of writing on insufficient evidence.
2. **Conclusions and citations come from the ledger only**: citing a document ID outside
   `patentkit ledger` = fabrication; V034 blocks it.
3. **Numbers must be sourced**: every number in claims / specification needs an A/B/C
   source (V031/V032); grade C (illustrative example) must be declared explicitly and
   never disguised as measured data.
4. **Log what you cannot say**: material shortfalls go into open_questions; **never invent
   parameters, steps or experimental results**.
5. **Revisions follow the loop**: one patch per logged issue; substantive changes
   invalidate the related human confirmations and require re-confirmation (by design);
   never touch unrelated content in passing.
6. **No grant promises, never "will certainly be granted"**; mark uncertain statute
   classification as "attorney to confirm".
7. **When tools are unavailable / not running**, answers must begin with "⚠️ Unverified by
   tool checks"; never disguise results as verified.
8. **Manuscripts stay outside the repo**: only registry / ledgers / mapping tables live
   inside; manuscript bodies never enter the repository (confidentiality red line).

## Result format (use it for every draft delivery; nothing may be omitted)

| Field | Requirement |
|---|---|
| **Draft state** | explicitly "first draft / reviewed draft / awaiting inventor input", with version and date |
| **Gap list** | every unclear point listed: what material is missing, who supplies it, which section it blocks |
| **Evidence citations** | every cited document = ledger ID + evidence level + judgment state |
| **Numerical provenance** | count of numerical statements in this draft and the A/B/C distribution; unsourced numbers must not appear |
| **Unverified annotation** | when tools did not run or data is incomplete, state "⚠️ Unverified by tool checks" explicitly |

## References (load on demand)

| File | When to read |
|---|---|
| [`00-prerequisites.md`](references/00-prerequisites.md) | **Read first**; self-contained summary of evidence levels / gates / judgment eligibility |
| [`09-disclosure-drafting.md`](references/09-disclosure-drafting.md) | five-part disclosure, Reg. 20–23 mapping, application-document list |
| [`10-claim-drafting.md`](references/10-claim-drafting.md) | independent/dependent layering, numerical-range self-check, support mapping |
| [`11-oa-response.md`](references/11-oa-response.md) | OA clause table, three-tier reverse argumentation, response structure |
| [`12-policy-radar.md`](references/12-policy-radar.md) | tracking examination-practice / form / drawing-requirement changes |
| [`13-revision-loop.md`](references/13-revision-loop.md) | multi-round revision: patch → log → re-run gates |
| [`glossary.md`](references/glossary.md) | zh⇄en glossary (shared with patent-research; CI keeps the copies identical) |

> Commands go straight through `python -m patentkit <subcommand>` (provenance / figures /
> deadlines / attest / ledger / gates / validate); this skill ships no script wrappers —
> the rules live in the kernel, and the drafting lines need no second entry point.
> The full search-side workflow is the sibling skill `patent-research`.
