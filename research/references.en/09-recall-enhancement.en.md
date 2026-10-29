# 09 · Recall Enhancement (optional `patent_intel` extension)

> **Boundary first**: everything here comes from the optional `patent_intel`
> extension (new in 4.0). The extension only produces **query proposals and offline
> diagnostics**; evidence levels, G-S gates and the human approval of
> `query_library.yml` remain owned by the `patentkit` kernel and by you. Without the
> extension the research workflow is unchanged — you may skip this document entirely.

## What it does

| Capability | Command | Nature |
|---|---|---|
| Axis → query-family proposals (single-feature / broad / cross / cross-domain) | `python research/scripts/recall.py plan --axis N1` | Proposal, needs human approval |
| Offline recall diagnostic (BM25 coverage + incremental yield + uncovered sub-areas) | `python research/scripts/recall.py report` | Read-only on the workspace; report goes to the sidecar |
| Environment self-check | `python -m patent_intel doctor --root <ws>` | Read-only |

## When to use it

1. **Before opening a new axis**: `plan` drafts the query family; copy valuable
   queries into `query_library.yml` through the existing approval flow (the
   extension never edits the library itself).
2. **Mid-search**: `report` shows which axes have zero hits and which queries
   produced *independent new* families — low-yield directions are not worth more
   quota.
3. **Reviewing expansions**: every expanded term carries its `relation`
   (synonym/hypernym/translation…) and source feature. **Broader terms and
   translations widen the net; they are not legal equivalents** — disclosure
   judgements still compare the original feature statement against document text.

## When NOT to use it

- Your 3 CNIPA sub-queries are used up and coverage judgement is done — the
  extension cannot help the G-S gates.
- You need `verified` evidence — the only path is the kernel `fetch-*`/`ingest`
  contract; the extension has no bypass.
- The report says an axis has zero hits — that only means **this candidate corpus**
  had no hit. It is **not** proof that no closer prior art exists.

## Stop conditions (honest statement)

Adaptive retrieval stops on budget exhaustion / consecutive zero-gain rounds /
manual cancel — **stopping is not exhaustive recall**. The report carries that
caveat verbatim; never cite extension output as an argument that "no closer
document exists".
