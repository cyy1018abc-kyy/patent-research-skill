# patentkit 0.5.0

Companion kernel for Patent Research Skill 3.3.0; Python 3.11+.

**Data-source presets** (per `docs/data-sources.md` access contract — the half-built
state is deliberate: ready to enable the day a real search task arrives, never
connected without explicit credentials):

- `fetch-bigquery` — G-S-04 family/cited-by census skeleton against the public
  `patents-public-data.patents.publications` dataset. Default **dry-run**: census-target
  list (near_prior_art/family with gaps), skeleton SQL (re-validate column names against
  the current schema before a real run), cost template. `--run` requires
  `google-cloud-bigquery` + `GOOGLE_APPLICATION_CREDENTIALS`, does a dry-run query first
  for bytes-billed → cost estimate, asks for confirmation, then archives the JSONL census
  artifact + log per the contract (capture_mode=live, complete declared honestly).
  `--fill <raw> [--apply]` backfills candidate family/cited_by from an archived census
  artifact — empty arrays only, human data never overwritten, fully offline-testable.
- `ingest.read_raw` now accepts `.xml` — OPS (Espacenet OPS API) exchange-document
  exports. Namespace-prefix-agnostic (localname matching), zh-first title/abstract
  selection, conservative field mapping. An OPS XML archived under `02_search_logs/raw/`
  ingests into verified candidates like any other raw artifact.
- The ingest "unsupported format" error message now lists `.xml (OPS export)` in the
  supported formats.

No changes to validation rules, gates, or the assessment protocol. Workspaces need no
migration. Full suite: 540 passed / 9 skipped (dev tree), including the new
`tests/test_source_presets.py`.

Version single source: `patentkit.__version__ = "0.5.0"`.

Assets: `patentkit-0.5.0-py3-none-any.whl`, `patentkit-0.5.0.tar.gz`, and
`SHA256SUMS-patentkit-v0.5.0.txt`. The kernel is reconstructed in CI from the
public `patentkit-0.1.2.tar.gz` plus `release/patches/patentkit-0.1.2-to-0.5.0.patch`
(see `release/patches/README.md`).
