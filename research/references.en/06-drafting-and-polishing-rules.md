# 06 Drafting and polishing rules

## Manuscripts live outside the repo (hard requirement)

**Manuscript text does not enter the repository**. The repository holds only:

- the path + `sha256` (`07_drafting/manuscript_registry.yml`)
- the revision ledger (`07_drafting/revision_ledger.md`)
- the feature atom table and support mapping table (structured analysis products)

**Why**: the manuscript is the most leak-prone asset, while the repository must remain distributable (see "core and data separation" in `04-evidence-level-system.md`).

## Fixed actions for every revision

```powershell
# 1. After editing the manuscript, rebind the sha256
python -m patentkit attest --apply

# 2. Add a line to 07_drafting/revision_ledger.md (version / date / what changed)

# 3. Validate the registry structure
python -m patentkit validate --strict
```

> If you forget `attest --apply`, `attest --check` reports a sha256 drift (exit 1) — that is a good thing:
> it means "the file the registry points to" and "the actual file" disagree, and reviewers may be looking at
> an old version.

## Three self-checks for claims

### 1. Numerical ranges must be supported by the specification (the easiest to miss)

**In substantive examination this will be pointed out directly as "not supported by the specification", and it
usually cannot be cured through a response** (adding new numerical values is new matter).

How to check (tooling already exists in this project; it produces `07_drafting/claims/numerical_consistency_check.md`):

1. Extract every "numerical range" from the claims
2. Check one by one whether the specification contains it
3. Pay special attention to **contradictory ranges for the same parameter** — claims broader than the
   specification = over-broad

Three defect types and their severity:

| Defect | Example | Severity |
|---|---|---|
| **Over-broad** (claims broader than the specification) | claim `R_c ∈ 2~6`, specification `3.0~5.0` | **most dangerous**; cannot be remedied |
| Boundary not disclosed | claim `0.33~0.45`, specification only gives 0.36 | medium |
| No support at all | claim `λ ∈ 1.05~1.35`, no value anywhere in the specification | medium |

**Fix: choose one of two** — narrow the claims to the disclosed range (safe), or supplement the specification
before the filing date (only general statements and typical values may be added; no new technical solutions).

> ⚠️ This judgment **must be made by the inventor** — whether it can be supplemented depends on whether the
> range already has simulation/experimental support.

### 2. Every claim must map to specification paragraphs

Maintain `07_drafting/specification/support_mapping_table.md` and mark the supporting paragraph for each atom.
An atom that cannot be marked must either gain an embodiment or be deleted.

### 3. No orphan claims

Every dependent claim must depend on some independent claim, and its additional features must not contradict
the claim it depends on.

## Beneficial effects must be traceable

Hard requirement of `G-D-01`: **every beneficial effect must correspond to some difference in a D column of
`04_comparative_analysis`**.

An effect that cannot be matched to a D column either was never compared, or does not itself hold up.

| Acceptable | Not acceptable |
|---|---|
| "staged discharge cuts oxygen-discharge loss 1.86→0.44 mol/600s (-77%)" | "improves efficiency" |
| "oxygen-supply response to a load step 0.19→0.05 s (3.8×)" | "responds faster" |

## Formula rendering

| Wrong | Right | Reason |
|---|---|---|
| `n_{in}^{hat}` | `\hat{n}_{in}` | text inside a superscript renders literally as "hat" |
| bare `%` | `%%` (in some tools' argument parsing) | treated as a format specifier |

After changing formulas, **preview each one**; do not just look at the source.

## Pre-hand-off checklist

```powershell
python -m patentkit check        # validate --strict + gates
python -m patentkit attest --check
python -m patentkit gates
```

- [ ] all five gates PASS (`verified` column)
- [ ] `validate` 0 error / 0 warn
- [ ] `attest --check` passes (no sha256 drift)
- [ ] every claim value has specification support
- [ ] every beneficial effect maps to a specific D column
- [ ] the revision ledger has a new line
