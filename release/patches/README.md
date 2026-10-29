# patentkit kernel source patches

The current kernel is **0.9.0** (skill 3.9.0): the P0–P4 upgrade — versioned data
contracts + non-destructive workspace upgrade, the discovery/technical-fact control layer
(G-I), the structured drafting pipeline (G-D, `concept`/`review_draft` gate), the
professional figure engine, and the complete delivery pipeline (frozen
`PatentDocumentModel` → DOCX/optional PDF → delivery manifest → human sign-off bound to
the manifest fingerprint → `release_ready` gate). CNIPA XML is **not implemented**:
`official_format_status` stays `not_attempted` until the official schema and tool are
researched and independently verified (plan §5.4).

The patch is provided as `patentkit-0.1.2-to-0.9.0.patch`; it adds, among others,
`patentkit/contracts.py`, `workspace_upgrade.py`, `source_intake.py`, `discovery.py`,
`discovery_handoff.py`, `draft.py`, `figure_plan.py` and `delivery.py` on top of the
previously released modules. Kernel 0.9.0 makes every kernel text write explicit-LF
(`write_text(..., newline="\n")` across the 31 previously uncovered call sites), so
workspaces, benchmark cases and reports are byte-identical across Windows and Linux;
invariant regressions (`test_init_writes_lf_only`, `test_pipeline_writes_lf_only`) lock
the discipline in. Kernel 0.8.0 had wired the revision loop to the
novelty conclusions (`revise reconfirm`, stale marking on apply, close precondition and
validate rule V038) and made drafting support citations resolvable (D-019). The patch
SHA-256 is `89aa48d538ddaec905222f5a6903bdaaaf3428aa1f72d45d4aea2db54ee00894`.
History: `-to-0.8.0.patch` was the revision↔conclusions linkage (V038) + structured
support citations (D-019), `-to-0.6.0.patch` was the census-evidence rework (G-S-04 census
records + V037 + the BigQuery/OPS data-source fixes), and `-to-0.5.1.patch` and older are
kept for history.
Kernel source remains separate from the skill runtime.

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
subprocess.run(["git", "apply", "--directory=kernel-build/patentkit-0.1.2", str(repo / "release/patches/patentkit-0.1.2-to-0.9.0.patch")], cwd=repo, check=True)
assert (kernel / "patentkit/assessment.py").is_file()
assert (kernel / "patentkit/revise.py").is_file()
assert (kernel / "patentkit/contracts.py").is_file()
assert (kernel / "patentkit/workspace_upgrade.py").is_file()
assert (kernel / "patentkit/source_intake.py").is_file()
assert (kernel / "patentkit/discovery.py").is_file()
assert (kernel / "patentkit/draft.py").is_file()
assert (kernel / "patentkit/figure_plan.py").is_file()
assert (kernel / "patentkit/delivery.py").is_file()
assert (kernel / "tests/test_delivery.py").is_file()
assert (kernel / "regression_tests/golden/expected/07-gates.json").is_file()
```

Then install into the chosen virtual environment and run the golden regression plus the
other regressions:

```bash
python -m pip install -e "./kernel-build/patentkit-0.1.2[dev]"
python -m pytest kernel-build/patentkit-0.1.2/regression_tests -o addopts= -q
python -m pytest kernel-build/patentkit-0.1.2/tests -o addopts= -q
```

Rebuilding the patch for a future kernel bump is scripted:
`python tools/build_kernel_patch.py` (defaults: dev tree `../patentkit`, upstream
`../_upstream/patentkit-0.1.2.tar.gz`, output `release/patches/patentkit-0.1.2-to-<kernel>.patch`).
The tool mirrors the dev tree → diffs against the checksum-verified upstream → strips the
double prefixes → applies the candidate in a real temporary git repository exactly like CI
(`git apply --directory=...`, `core.autocrlf=false`) → checks CI sentinel files → verifies
the applied tree is byte-identical (LF-normalised) to the dev-tree mirror. `--verify-against
<old patch>` additionally checks that a same-version rebuild reconstructs the old patch's
applied tree exactly (used when only the build tooling changed).

The extracted directory retains its upstream `0.1.2` name; the patched package declares
version `0.9.0`. CI repeats the download, checksum verification, patch application, and
regression tests. No real patent data is needed. CI builds the wheel/sdist and the
official installation ZIP, runs Windows/Linux acceptance, and publishes the paired
Releases after merge to main. See `../notes/skill-v3.9.0.md` for installation and
migration: existing workspaces can run `python -m patentkit upgrade check` first (read-only)
and `upgrade apply` to add the `10_discovery/` and `11_delivery/` directories non-destructively.
