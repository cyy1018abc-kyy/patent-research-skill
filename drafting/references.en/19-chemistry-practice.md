# 19 Chemistry and materials practice (draft-grade)

> Applies to compounds, compositions, materials and medical-use subject matters. Practice
> sources always cite the Examination Guidelines 2025 edition, Part II Chapter 10
> (written as "Guidelines II-10 §x"). The general drafting discipline stays in
> [10](10-claim-drafting.md) and [09](09-disclosure-drafting.md); this reference covers only
> the domain-specific part. Output is a draft; this is not legal advice.

## The three enablement elements (Guidelines II-10 §3.1)

| Element | What to write | Common gap |
|---|---|---|
| Confirmation | structural formula / molecular formula + performance-parameter spectra; polymers additionally molecular weight and distribution, repeat-unit arrangement | only a code or trade name, no confirmation means |
| Preparation | at least one preparation method; compounds usually need preparation examples | a list of starting materials without steps and conditions |
| Use / effect | qualitative or quantitative experimental data for unpredictable effects; a new pharmaceutical compound needs the concrete medical use, pharmacological action, effective amount and administration method, with animal/clinical data where necessary | vacuous statements like "can be used to treat disease" |

- When **multiple measurement methods** exist for an effect, the one used must be stated —
  examination and responses both compare against that basis.
- **Supplementary experimental data** (§3.5): judged against the original application text —
  the effect being proven must be derivable from the original disclosure; supplementary data
  cannot rescue an effect that was missing from the original disclosure. Log this into the
  gap list at search time (see the search-side notes at the end).
- Numerical/embodiment thresholds follow [09](09-disclosure-drafting.md): ≥2 different
  embodiments for a broad generalization; range endpoints + at least one intermediate value.

## Claim forms (Guidelines II-10 §4)

- **Compounds**: defined by name / structural formula / molecular formula; trade names,
  codes and informal names are not allowed.
- **Compositions**: open wording ("containing / including / consisting essentially of") and
  closed wording ("consisting of / the remainder being") lead to **opposite** novelty
  outcomes — choose with the protection intent in mind: open wording has broader coverage,
  closed wording is narrower but harder to design around by adding components.
- **Amounts**: component percentages sum to 100%; "approximately / about / nearly" and ">X"
  formulations are not allowed; narrowing and endpoint discipline as in the numerical layer
  of [10](10-claim-drafting.md).
- **Medical use is drafted as a manufacturing use**: "use of compound X in the manufacture of
  a medicament for treating disease Y" — administration features (subject / route / mode /
  dosage / intervals) have **no limiting effect**; do not rely on them for scope. The four
  medical-use considerations on the novelty side (§5): a substantially different use, not
  directly revealed by the original mechanism of action, not a superordinate concept, and
  administration-process features do not limit.

## Novelty / inventive-step practice (shared by search and response)

- **Genus/spec direction** (§5): a genus (Markush-type) disclosure does **not** destroy the
  novelty of a specific compound (species); the reverse does — a specific compound's
  disclosure destroys the genus's novelty. Apply this direction in both search reading and
  claim layout.
- **Numerical ranges**: overlap or a shared endpoint destroys novelty; a product defined by
  parameters that cannot be distinguished in structure/composition is **presumed to lack
  novelty**, with the burden of rebuttal on the applicant (same root as the presumption rule
  in the research skill's three-tier determination).
- **Inventive step** (§6): structural difference + the use/effect brought by the
  modification → set the actually-solved technical problem and look for inspiration; an
  unexpected use/effect improvement supports inventive step; a known inevitable trend
  (e.g., effect rising with homolog carbon number) does not; a classic isosteric
  replacement yielding comparable activity does not, unless an unexpected effect results
  (e.g., activity tens of times higher).

## Unity (Guidelines II-10 §8)

Markush-type claim elements must share **common performance** + **common structure** (the
structure constituting the distinguishing feature and indispensable to the common
performance), or belong to one recognized class of compounds — otherwise they do not fit in
one application; split per the strategy in [10](10-claim-drafting.md).

## Search-side notes (for collaboration with the research skill; not executed here)

- Disclosure forms to check: structural formulas/spectra, **parameter/use/preparation
  definitions** (the presumption rule applies in reverse), exemplified-compound tables;
- for medical uses, watch for "looks different, actually the same" caused by non-limiting
  administration features;
- the supplementary-data rule caps what a response can achieve: record at search time
  whether the original disclosure can derive the effect.

## Tool hooks and boundaries

```powershell
patentkit provenance check      # all-green numbers before embodiments (A/B/C)
patentkit ledger                # cite ledger IDs only for background/comparison (V034)
patentkit deadlines list        # pharma subjects: mind pte_drug (PTE request within 3 months of approval)
```

- This reference does not judge patentability and never predicts grant; mark unsure clause
  classifications "attorney to confirm";
- it expands the chemistry quick reference in [10](10-claim-drafting.md)'s domain-specific
  forms; the two are consistent.
