---
name: patent-audit
description: >
  Structured audit of a prior-art search evidence chain: claim-element
  decomposition, a coverage ledger (element × data source × classification
  symbol), adversarial validation of every "element ↔ prior art" mapping,
  independent verification of every verbatim quote and locator, and three-verdict
  conclusions (confirmed / needs_validation / rejected) with a neutral report.
  This skill audits the quality and coverage gaps of an existing workspace's
  evidence; it produces no new search conclusions and predicts no grant outcome.
  Guidance mode is the default and offers method and spot checks only; a full
  audit runs only with explicit authorization. When tools are unavailable or not
  running, answers must begin with "⚠️ 未经验证工具校验".
  Use when the user wants to audit search coverage, review an evidence chain,
  adversarially validate prior-art mappings, check that citations trace verbatim,
  produce a neutral audit report, or locate search blind spots.
  Trigger phrases include "full audit", "audit", "audit the search chain",
  "coverage", "adversarial validation", "independent review", "evidence chain
  quality", "search blind spots".
license: Apache-2.0
metadata:
  version: 4.0.0
---

# Prior-Art Search Evidence Audit (Audit)

> **Companion**: `patentkit >= 0.10.0` (workspace contract and validation
> commands) and the sibling skill `patent-research` (the producer of the audited
> chain). The methodology is adapted from Cloudflare `security-audit-skill` (MIT,
> see the repository README Credits): coverage ledger, adversarial validation,
> independent review, three-verdict structured findings.
> **Position**: answer "can this search evidence chain be trusted" — re-walk
> coverage and evidence in roles independent of the searcher, so that every
> conclusion either carries a complete citation chain or honestly marks its gap.

## When to trigger

| Use it | Don't use it |
|---|---|
| Full audit of a finished search workspace (six phases after explicit authorization) | First search, prior-art location, supplementary searches (patent-research skill) |
| Verify one "element ↔ prior art" mapping's quote and locator | Draft the comparison matrix (research's domain) |
| Locate search blind spots (element × source × classification gaps) | Predict novelty / inventive step / grant (nobody may promise) |
| Adversarially disprove candidate mappings (assume wrong, find counterevidence) | Modify the candidate list or queries (suggest only, never execute) |
| Produce a neutral audit report (REPORT / NEEDS-VALIDATION) | Make legal decisions for the right holder; the report is not legal advice |

## Two modes (clarify first, then act)

- **guidance (default)**: method explanation, spot checks, partial coverage
  review. No audit run directory, no ledger/findings files; reading the workspace
  to answer specific questions is fine.
- **full audit (explicit authorization)**: only when the user explicitly asks for
  a full/comprehensive audit or an audit report, run the six phases and write all
  artifacts under `12_audit/run-<N>/`.

If the request could mean either mode, ask one focused question before creating
files.

## Execution order (six phases, full-audit mode)

| # | Phase | Read | Do |
|---|---|---|---|
| A1 | Overview and ledger | [`01-recon-claims-map`](01-recon-claims-map.en.md) | Decompose claim elements → `claims-map.md`; seed `audit-ledger.json` over element × source × classification |
| A2 | Coverage hunting | [`02-coverage-hunting`](02-coverage-hunting.en.md) | Search/review per ledger unit with checks; the critic finds blind spots |
| A3 | Adversarial validation | [`03-adversarial-validation`](03-adversarial-validation.en.md) | A dedicated verifier tries to disprove every candidate mapping |
| A4 | Structured findings | [`04-findings-contract`](04-findings-contract.en.md) | Write three-verdict `findings.json`; validate with `python audit/scripts/validate_findings.py` |
| A5 | Independent review | [`05-independent-review`](05-independent-review.en.md) | Fresh reviewer checks every verbatim quote and locator per record |
| A6 | Neutral report | [`06-neutral-report`](06-neutral-report.en.md) | Derive `REPORT.md` / `NEEDS-VALIDATION.md` after both validators pass |

**Single-agent sequential mode is the default**: one session runs the six phases
in order and emulates role isolation with separate rounds; parallel isolated
agents run only on an explicit `--multi-agent` request.
The full protocol (state machine, terminal states, profiles, budget) is in
[`00-audit-protocol`](00-audit-protocol.en.md).

## Hard constraints (non-negotiable)

1. **Authorization before volume**: guidance mode writes no audit artifacts; full
   audit requires an explicit user request.
2. **Verbatim quote or demotion**: every confirmed mapping carries a verbatim
   quote + paragraph locator, re-checked by the validator; otherwise it degrades
   to needs_validation — never paraphrased to fit.
3. **Destructiveness and certainty are separate axes**: impact categories (X/Y/A)
   belong to confirmed records only and never exceed the demonstrated disclosure
   extent; needs_validation/rejected never carry an impact category. Confidence
   is scored separately; the two axes are never traded against each other.
4. **Verifier/author isolation**: every candidate mapping is reviewed by a role
   whose job is disproof; a mapping's author never self-confirms it (single-agent
   mode emulates isolation with independent review rounds).
5. **The ledger is the coverage claim**: coverage is counted only from unit
   states and checks in `audit-ledger.json`; "I looked at it" is not evidence.
6. **All three verdicts leave a trace**: needs_validation names the missing
   decisive facts and an executable plan; rejected records the refutation reason;
   neither enters the REPORT conclusions table.
7. **Never rewrite the audited workspace**: the audit reads the workspace and
   writes only `12_audit/`; fix suggestions go into the report, never into
   `--apply` executions.
8. **When tools are unavailable or not running**, answers begin with
   "⚠️ 未经验证工具校验"; never pretend verification happened.

## Result format (use for every audit conclusion; no missing fields)

| Item | Requirement |
|---|---|
| **Three verdicts** | Every conclusion labeled confirmed / needs_validation / rejected with its fingerprint |
| **Evidence chain** | confirmed: element reference + prior art + verbatim quote + locator + independent-review mark |
| **Impact category** | confirmed only: X/Y/A + reason, stated separately from evidence certainty |
| **Gap list** | Uncovered ledger units, blocked/deferred reasons, needs_validation facts |
| **Unverified marking** | Explicit "⚠️ 未经验证工具校验" whenever tools did not run or data is incomplete |

## Reference documents (load on demand)

| File | When to read |
|---|---|
| [`00-audit-protocol.en.md`](00-audit-protocol.en.md) | **Before every full audit**; modes, roles, state machine, terminal states, profiles and budget |
| [`01-recon-claims-map.en.md`](01-recon-claims-map.en.md) | Phase A1: element decomposition, claims-map, ledger seeding rules, coverage_id |
| [`02-coverage-hunting.en.md`](02-coverage-hunting.en.md) | Phase A2: hunting waves, check records, coverage critic |
| [`03-adversarial-validation.en.md`](03-adversarial-validation.en.md) | Phase A3: disproof-first verifier prompt and decision rules |
| [`04-findings-contract.en.md`](04-findings-contract.en.md) | Phase A4: findings.json verdict fields, impact/certainty axes, validator usage |
| [`05-independent-review.en.md`](05-independent-review.en.md) | Phase A5: review checklist, material-correction re-verification rules |
| [`06-neutral-report.en.md`](06-neutral-report.en.md) | Phase A6: REPORT/NEEDS-VALIDATION structure and neutrality rules |
| [`07-anti-patterns.en.md`](07-anti-patterns.en.md) | Twelve anti-patterns (checklists≠audits, self-assessment inflation, locator drift…) |

> The validator scripts ship with the skill payload (`audit/scripts/validate_findings.py`
> and `validate_ledger.py`, pure Python stdlib, zero third-party dependencies); usage
> is in reference 04. Cross-skill navigation uses the in-text "companion" notes —
> never `../` relative links after installation.
