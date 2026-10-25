# patentkit 0.3.0 source patch

Skill 2.5.0 requires patentkit 0.3.0 with assessment protocol 1. The complete kernel
change — the 0.2.0 assessment protocol plus the 0.3.0 delivery-safety layer
(export-docx / map / layout / ledger / provenance / figures / deadlines, V031–V034,
and a reconstructed `tests/conftest.py` so the full suite runs from the patched tree) —
is provided as `patentkit-0.1.2-to-0.3.0.patch` (supersedes `-to-0.2.0.patch`, which is
kept for history). Kernel source remains separate from the skill runtime.

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
subprocess.run(["git", "apply", "--directory=kernel-build/patentkit-0.1.2", str(repo / "release/patches/patentkit-0.1.2-to-0.3.0.patch")], cwd=repo, check=True)
assert (kernel / "patentkit/assessment.py").is_file()
```

Then install into the chosen virtual environment and run the new regressions:

```bash
python -m pip install -e "./kernel-build/patentkit-0.1.2[dev]"
python -m pytest kernel-build/patentkit-0.1.2/regression_tests -o addopts= -q
```

The extracted directory retains its upstream `0.1.2` name; the patched package declares
version `0.3.0`. CI repeats the download, checksum verification, patch application and
regression tests. No real patent data is needed. CI builds the wheel/sdist and the
official installation ZIP, runs Windows/Linux acceptance, and publishes the paired
Releases after merge to main. See `../notes/skill-v3.0.1.md` for installation and migration.
