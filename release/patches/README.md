# patentkit kernel source patches

The current kernel is **0.6.0** (skill 3.4.0): the G-S-04 census-evidence rework plus the
data-source chain fixes. G-S-04 now verifies a **census record** per dimension
(`patentkit/census.py` — queried + raw artifact archived and hash-bound; zero hits count as
complete, while not-queried / partial / failed / modified-artifact do not), validate gains
**V037** for census records that exist but are broken, and `fetch-bigquery` fixes:
dry-run pre-check and execution share the same SQL + query parameters, the cited-by
subquery returns the *citing* document's number, archives carry date/target/run-time and
refuse silent overwrite, and `--fill` writes the census records (field-level artifact
binding), constrains backfill to the passed target, and skips human-reviewed candidates
unless `--force` (every forced write is appended to `02_search_logs/backfill_audit.jsonl`).
It is provided as
`patentkit-0.1.2-to-0.6.0.patch`;
the 0.5.0 data-source presets — `fetch-bigquery` (G-S-04 family/cited-by census: dry-run by
default, `--run` under real GCP credentials) and OPS XML ingest (`read_raw` parses OPS
exchange-document exports, namespace-agnostic) — and the 0.5.1 rehearsal fixes remain part
of the chain, with the data-source access contract in `docs/data-sources.md`.
`-to-0.5.1.patch` and older are kept for history. Kernel source remains separate from
the skill runtime.

The patch applies to the public `patentkit-0.1.2.tar.gz` Release asset, whose SHA-256 is
`5ab1ff6e6387c1b6f30e8e084b0da88d93bf71426e9cb901158562d9b52aae14`.

From the repository root, use Python 3.12 and Git to reconstruct and verify the kernel:

```python
import hashlib
import io
import subprocess
import tarfile
import urllib.request
from pathlib import Path

repo = Path.cwd()
destination = repo / "kernel-build"
destination.mkdir(exist_ok=False)
url = "https://github.com/cyy1018abc-kyy/patent-research-skill/releases/download/patentkit-v0.1.2/patentkit-0.1.2.tar.gz"
data = urllib.request.urlopen(url, timeout=60).read()
assert hashlib.sha256(data).hexdigest() == "5ab1ff6e6387c1b6f30e8e084b0da88d93bf71426e9cb901158562d9b52aae14"
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    archive.extractall(destination, filter="data")
kernel = destination / "patentkit-0.1.2"
subprocess.run(["git", "apply", "--directory=kernel-build/patentkit-0.1.2", str(repo / "release/patches/patentkit-0.1.2-to-0.6.0.patch")], cwd=repo, check=True)
assert (kernel / "patentkit/assessment.py").is_file()
assert (kernel / "patentkit/revise.py").is_file()
assert (kernel / "patentkit/census.py").is_file()
assert (kernel / "patentkit/fetch_bigquery.py").is_file()
assert (kernel / "regression_tests/golden/expected/07-gates.json").is_file()
```

Then install into the chosen virtual environment and run the golden regression plus the
other regressions:

```bash
python -m pip install -e "./kernel-build/patentkit-0.1.2[dev]"
python -m pytest kernel-build/patentkit-0.1.2/regression_tests -o addopts= -q
```

Rebuilding the patch for a future kernel bump is scripted:
`python tools/build_kernel_patch.py --out <candidate> --verify-against release/patches/patentkit-0.1.2-to-0.6.0.patch`
(mirror → diff → strip double prefixes → CI-equivalent apply check → applied-tree equivalence;
`--verify-against` only applies when the old patch's applied tree should be identical).

The extracted directory retains its upstream `0.1.2` name; the patched package declares
version `0.6.0`. CI repeats the download, checksum verification, patch application and
regression tests. No real patent data is needed. CI builds the wheel/sdist and the
official installation ZIP, runs Windows/Linux acceptance, and publishes the paired
Releases after merge to main. See `../notes/skill-v3.4.0.md` for installation and migration.
