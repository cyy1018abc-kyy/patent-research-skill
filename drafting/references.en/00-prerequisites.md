# 00 Prerequisites for the drafting lines (self-contained summary)

> This file summarizes the research-side discipline the drafting lines rely on — readable
> without the patent-research skill installed. The authoritative implementation always
> lives in the `patentkit` kernel (`gates.py` / `assessment.py`); this summary shares its
> source with the research skill's references 01–08, which take precedence on details.

## The three evidence levels (source provenance)

| evidence_level | Meaning | Eligible for strict PASS |
|---|---|---|
| verified | Replayable raw artifact from live collection, retained in the workspace | Yes, subject to the gate-specific judgment requirements |
| attested | External material with an in-workspace SHA-256 binding | No |
| asserted | Source provenance is not verified | No |

**AI scoring never downgrades a genuine source; human confirmation never upgrades an
asserted source.** Source provenance and judgment (who assessed it, whether the support is
sufficient) are two independent properties.

## The five acceptance gates (G-S; PASS trusts the verified column only)

| Gate | Threshold |
|---|---|
| G-S-01 | Candidate list: ≥200 patents + ≥200 literature |
| G-S-02 | ≥10 supported judgments per axis (both dimensions ≥4 + per-axis problem/means citations) |
| G-S-03 | ≥5 near-prior-art documents with explicit human confirmation bound to the current fingerprint |
| G-S-04 | family and cited_by complete for near_prior_art / family roles |
| G-S-05 | 100% of search logs replayable (live + raw artifacts) |

**Minimum bar for drafting: G-S-01 through G-S-03 met.** A gate FAIL means the search is
insufficient — never loosen the criteria.

## Judgment eligibility (assessment protocol 1, essentials)

- relevance = min(problem dimension, means dimension); both dimensions need original-text
  citations (ref + locator + quote + rationale);
- AI may score G-S-02; G-S-03 accepts explicit human confirmation only (bound to the
  judgment fingerprint);
- substantive changes (scores / role / axes / rationale / citations) invalidate
  confirmation; re-assess and re-confirm;
- a verified source does not mean a correct judgment; ledger entries in state
  unknown / needs_review must not be used as a basis.

## Three-tier determination (the argumentation skeleton for OA responses and claims)

1. **Per-document novelty**: does any single document disclose all core features
   (novelty_check: blocking / covered / partial / untouched)?
2. **Combined inventive step**: would a combination of 2–3 documents be obvious?
   **Zero-disclosure atoms** — features no combination can assemble — are the core of the
   independent claim;
3. **Technical effect**: does the effect presuppose the distinguishing features?
   (Quantified first; map each effect to a column-D difference.)

## Kernel commands the drafting lines use

```powershell
patentkit ledger                # evidence ledger: conclusions / background cite ledger IDs only
patentkit gates                 # gate status (precondition check)
patentkit provenance scan/check # numerical-claim A/B/C provenance
patentkit figures check         # bidirectional figure-mark consistency
patentkit attest --check        # manuscript sha256 drift detection
patentkit deadlines list        # statutory-deadline ledger (official documents prevail)
```
