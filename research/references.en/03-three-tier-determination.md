# 03 Three-tier determination

## relevance has **two dimensions**

This is the single most important criterion in this project. `relevance` is not a single score but a combination of two dimensions:

```
relevance = min(relevance_problem, relevance_means)
```

| Dimension | Question | Why it must be separate |
|---|---|---|
| **Technical problem** (`relevance_problem`) | How much does the problem it solves overlap with this invention? | Different problem → no comparison even if the means look alike |
| **Technical means** (`relevance_means`) | How much does its implementation overlap with this invention? | Different means → cannot defeat novelty even if the problem looks alike |

**Take `min`, not the average**: only when both dimensions qualify does the document qualify. A document with a
different technical problem cannot be saved even if its technical means are identical — and vice versa.

### 1–5 level definitions

| Score | Technical problem | Technical means |
|---|---|---|
| 5 | Completely identical | Completely identical |
| 4 | Same, only the application scenario differs | Main means the same, individual steps differ |
| 3 | Same field, different sub-problem (**default**) | Same category, different implementation |
| 2 | Related field | Only the principle is shared |
| 1 | Unrelated | Unrelated |

> **`3` is the ingest default**. A supported assessment with known actor distinguishes an actual score of 3 from an unjudged record; reviewed_at alone is not proof of review. AI may score G-S-02 with per-axis problem/means original-text support. Human confirmation is required for G-S-03.

## Four `role` values

| role | Meaning | Which gate it enters |
|---|---|---|
| `near_prior_art` | Closest-prior-art recommendation; requires valid human confirmation for G-S-03 | `G-S-03`, `G-S-04` |
| `pool` | Ordinary candidate in the pool | `G-S-02` |
| `excluded` | Excluded (wrong mapping / false hit / duplicate / belongs to another target) | Counted in no gate |
| `family` | Family member | `G-S-04` |

## Three-tier determination framework

### Tier 1: Per-document novelty

Question: **Did any single document disclose all core technical features of this invention?**

| `novelty_check` | Meaning |
|---|---|
| `blocking` | One document covers all core features → **novelty does not hold** |
| `covered` | Covers all features of one claim but not the invention as a whole |
| `partial` | Discloses only some features (most documents land here) |
| `untouched` | Discloses no feature / unrelated to the technical subject |

**How to judge**: for each document ask "read on its own, does it reveal the N technical axes of this invention?"
**Only a single document that discloses the core means of every axis at once qualifies as `blocking`** — this is
extremely rare, and that is precisely where the value of the invention lies.

### Tier 2: Combination inventive step

Question: **Would combining 2–3 documents make this invention obvious?**

**This tier is more dangerous than the first**: examiners love "D1 + D2 in combination".
The approach is not to find the weakest combination but to **actively find the strongest combination against
your own solution**.

**The strongest argument structure**: identify **zero-disclosure atoms** — features that no combination of the
comparison documents can assemble. A combination presupposes that each member contributes at least one feature;
an atom that nothing contributes cannot be assembled by combination either.

**You must attack yourself**: list the examiner's most likely rebuttals and your responses.
Omit this section and the conclusion is self-deception.

### Tier 3: Technical effect

Question: **Is there a non-obvious technical effect?**

Criterion: must the effect presuppose the distinguishing features of this invention? Without those features,
is reaching it **in principle impossible**?

| Valid | Invalid |
|---|---|
| "staged discharge cuts oxygen-discharge loss 1.86→0.44 mol/600s (-77%)" | "improves efficiency", "safer" |
| "cathode pressure drop under μG reaches 5.2× that at 1g" | qualitative claims without data |

> ⚠️ If the data comes from simulation, the simulation conditions must be stated in the specification; otherwise
> reproducibility will be questioned.

## Alignment with the examination practice (2025 Guidelines)

The framework maps layer by layer onto the substantive-examination practice of the Examination
Guidelines 2025 edition (section numbers follow the official text). **The alignment does not touch
the scoring system**: the two relevance dimensions, the 1–5 levels and the role values are all
unchanged — what is aligned is the judgment wording and the search obligations.

| This framework | Examination practice (Guidelines) | Alignment notes |
|---|---|---|
| Tier 1 per-document novelty | **Separate-comparison principle** (Part II Ch. 3 §3.1): each claim is compared with **each** document alone; combined comparison is prohibited | The `blocking` judgment is inherently a separate comparison; "the same invention" requires substantial identity in four aspects — field, problem, solution, expected effect — not just the feature list |
| Tier 1 search obligation | **Conflicting-application window** (Part II Ch. 3 §2.2, Ch. 7 §4.2): anything filed by anyone before the filing date and published/announced after it (inclusive), judged on the full text including drawings | Searches must cover applications published within 18 months after the filing date; family/citation tracking must not stop at publication dates earlier than the filing date |
| Tier 2 combination inventive step | **Three-step method** (Part II Ch. 4 §3.2.1.1): ① closest prior art → ② the technical problem actually solved → ③ technical inspiration | The "strongest argument structure" = walking the three steps for the examiner: pick the closest D1, set the actually-solved problem from the effect of the distinguishing features, then check the three inspiration situations (common knowledge / same document elsewhere with the same function / another document with the same function) |
| Tier 2 self-attack | **The actually-solved technical problem must not contain guidance or hints toward the distinguishing features** (Part II Ch. 4 §3.2.1.1, step ②) | When writing "what the examiner will say", the problem sentence must not contain wording of the distinguishing features themselves — if it does, the attack is hindsight and does not stand; do not celebrate early |
| Tier 3 technical effect | **Secondary considerations** (Part II Ch. 4 §5): an unexpected technical effect is a secondary factor of inventive step, not the only route | The criterion "must presuppose the distinguishing features" shares its root with step ②; when the three-step method already yields non-obviousness, do not force extra unexpected-effect claims |
| Parameter-defined subjects | **Presumption rule** (Part II Ch. 3 §3.2.5): a product defined by parameters/use/preparation that cannot be distinguished in structure/composition is presumed to lack novelty, with the burden on the applicant | For parameter-defined subjects (alloys/materials/compositions), treat the `partial` level strictly — with no structural/compositional distinction found, presume `covered` and state the presumption in the assessment |

**Content boundary of a cited document** (Part II Ch. 3 §2.3): a document's content includes what is
implicit and directly and unambiguously derivable; drawings count only for what is directly and
unambiguously derivable — **dimensions obtained by measuring a drawing are not disclosure**.
Apply this in the feature-comparison matrix whenever a drawing is cited.

## Workflow

Use [07-assessment-protocol.md](07-assessment-protocol.md) for supported AI/human assessments and explicit batch confirmation. The legacy CSV workflow below may update judgments, but never creates G-S-03 confirmation and unsupported records do not count.

```powershell
# 1. Check progress
python -m patentkit review progress

# 2. Export the unjudged entries (only those with abstracts can be judged)
python -m patentkit review export --unreviewed --with-abstract --axis N4 --out worksheet.csv

# 3. A human fills in relevance_problem / relevance_means in Excel (leave the other columns empty)
#    Note: Excel on Chinese Windows saves CSV as GBK and drops the BOM — the tool detects that automatically

# 4. Dry-run first to see the impact; write only after confirming
python -m patentkit review apply worksheet.csv
python -m patentkit review apply worksheet.csv --by reviewer-name --apply
```

> `apply` is **fail-closed**: if any row contains an invalid value, **not a single character is written**.
> This is deliberate — a previous partial failure left a dirty, partially written state.
