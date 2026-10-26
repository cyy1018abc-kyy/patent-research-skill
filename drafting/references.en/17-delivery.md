# 17 · Delivery Pipeline (P4): frozen snapshot → application document package → manifest → human sign-off

> P4 complete delivery: from **one frozen snapshot** produce the claims/specification/abstract/
> figures review copy (DOCX, optional PDF preview), a verifiable **delivery manifest** and a human
> **sign-off**. Discipline: artifacts come only from the frozen model; any input change
> **invalidates** the old delivery — rebuild and re-sign. `release_ready` is an internal delivery
> gate, not official-filing compliance and never "ready to submit".

## 1. Inputs (written by humans/AI)

| Input | Location | Rule |
|---|---|---|
| claims text | `07_drafting/manuscript/claims.md` | one numbered claim per line (`1. ...`); numbers must match the structured claims |
| specification text | `07_drafting/manuscript/specification.md` | paragraphs start with `[0001]`; support-mapping paragraphs must exist |
| abstract | `07_drafting/manuscript/abstract.md` | non-empty |
| structured model | `07_drafting/{drafting_plan,claim_atoms,claims_structured,support_mapping,support_review}` | P2 |
| figure plans | `07_drafting/figures/*.figure.yml` | P3; SVG/PNG rendered at build time |
| gates snapshot | `gates` computation | frozen into the model; a later change invalidates the manifest |

Manuscript prose lives only in the controlled workspace — never in the public repository.

## 2. Commands

```powershell
python -m patentkit draft status --root .\workspace           # requires the current review_draft state
python -m patentkit deliver build --root .\workspace          # dry-run
python -m patentkit deliver build --root .\workspace --apply
python -m patentkit deliver build --root .\workspace --apply --pdf   # needs a local converter
python -m patentkit deliver check --root .\workspace
python -m patentkit deliver sign --root .\workspace --by inventor --apply
python -m patentkit draft gate --to release_ready --by inventor --apply
python -m patentkit deliver status --root .\workspace
```

## 3. Workspace files

| File | Content |
|---|---|
| `11_delivery/patent_document_model.json` | **PatentDocumentModel**: target/candidate, claims, paragraphs, abstract, figures (with SVG/PNG hashes), input hashes, gates snapshot, `model_fingerprint` |
| `11_delivery/artifacts/patent-application.docx` | review copy: claims / specification / abstract / figures (PNG embedded when Pillow is available) |
| `11_delivery/artifacts/patent-application.pdf` | optional PDF preview; **reported as not generated** when no converter exists — never faked |
| `11_delivery/delivery_manifest.json` | manifest: snapshot, drafting-plan hash, gates, artifact_list (path/format/SHA-256/generator/official status), sign-off with bound fingerprint, `official_format_status` |
| `11_delivery/validation_report.json` | build-time checks, PDF/CNIPA status, warnings |
| `11_delivery/cnipa_format_notes.md` | CNIPA XML research record: `not_attempted` (**not** a compliance claim) |

## 4. Check codes (`deliver check`)

| Code | Level | Meaning |
|---|---|---|
| E-001 | error | no manifest yet (build first) |
| E-002 | error | frozen snapshot is stale (candidate/plan/atoms/claims/support/manuscript/model fingerprint changed) |
| E-003 | error | artifact missing or hash differs from the manifest |
| E-004 | error | claims text numbers differ from the frozen model / unparsable |
| E-005 | error | specification paragraph set differs / support paragraph missing |
| E-006 | error | text cites a figure that the frozen model does not contain |
| E-007 | error | research gates differ from the frozen snapshot |
| E-008 | error | `draft audit` has errors (including figure D-018) |
| E-009 | error | not signed, or sign-off fingerprint no longer matches the manifest |
| E-010 | error | manifest/model schema violation or broken JSON |
| E-011 | error | missing independent claim (claim 1) or empty abstract |
| E-012 | error | official verification claimed without any verified artifact (fake compliance blocked) |
| W-001 | warn | no figures in the delivery |
| W-002 | warn | PDF requested but not generated (no local converter) |

## 5. Sign-off and invalidation

1. **Sign-off binds the manifest fingerprint** (`review_signoff.manifest_fingerprint`, computed
   without the sign-off field). Any substantive later change to the manifest invalidates it (E-009).
2. **Any input change** (candidate/plan/atoms/claims/support/manuscript/figure spec/gates) makes
   `deliver check` report E-002 and demotes `draft status` from `release_ready` to `concept` (stale).
3. Revision flow: edit prose/model → re-pass the `review_draft` gate → rebuild (`deliver build`) →
   `deliver check` → re-sign → `draft gate --to release_ready`. Re-signing a stale manifest is forbidden.
4. `release_ready` means internal delivery checks passed with a sign-off; until CNIPA XML is
   independently verified, nothing may be called compliant or ready for official submission.

## 6. Official format (CNIPA XML) status

- CNIPA XML is **not implemented**: first complete the official-schema research and official-tool
  verification (plan §5.4), then upgrade `official_format_status` (`not_attempted` →
  `generated_unverified` → `verified_by_official_tool`).
- `export_cnipa_xml()` fails closed; the manifest stays `not_attempted`; E-012 blocks false claims.
- DOCX/PDF are internal review copies, not official electronic filing documents.

## 7. Pre-delivery checklist

- [ ] `deliver check` has zero errors (E-009 disappears after sign-off);
- [ ] manifest artifact hashes match the files on disk;
- [ ] claim numbers / paragraph numbers / figure numbers agree across model, manuscripts and figures;
- [ ] the gates snapshot equals the current gates;
- [ ] a human reviewed the DOCX page by page (figure legibility, numbering, pagination) and signed;
- [ ] manuscript prose never entered the public repository; no real patent data in tests.
