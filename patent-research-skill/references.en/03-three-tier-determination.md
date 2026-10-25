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
