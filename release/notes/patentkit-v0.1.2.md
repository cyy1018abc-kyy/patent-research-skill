# patentkit 0.1.2

Patent workspace validation / acceptance-gate core (CLI + Python library).
The rule-enforcement layer of the `patent-research-skill` skill package: three-tier evidence determination, V001–V028 validation, G-S-01..05 acceptance gates.

## Changes in this release (0.1.0 → 0.1.2)

- **Fixed**: the G-S-01 hint text in `gates.py` leaked a historical real target ID (`historical target`) —
  it would have leaked into client sessions through tool output; replaced with generic wording.
- **Single source of version**: `__version__` in `patentkit/__init__.py` is the only literal;
  `pyproject.toml` reads it dynamically; `tests/test_version.py` guards it.
- Documentation statements such as tool count / test count are unified.

## Assets and verification

| Asset | SHA-256 |
|---|---|
| `patentkit-0.1.2-py3-none-any.whl` | `6edb60f761f03b88039ad50e58d5a271a397bc1883fcb43be8080eabd70f4231` |
| `patentkit-0.1.2.tar.gz` | `a77066c0db61fc40a0b791a9aebd2ff298764be512c2ad2c6f28c64e661f5585` |
| `SHA256SUMS-patentkit-v0.1.2.txt` | — |

## Installation

```powershell
# Install directly from the release asset
pip install https://github.com/cyy1018abc-kyy/patent-research-skill/releases/download/patentkit-v0.1.2/patentkit-0.1.2-py3-none-any.whl

# Or install from the GitHub tag
pip install "git+https://github.com/cyy1018abc-kyy/patent-research-skill.git@patentkit-v0.1.2"
```

## Requirements

- Python ≥ 3.11
- Runtime dependencies: `jsonschema>=4.18`, `PyYAML>=6.0` (installed automatically by pip)
- Optional: `mcp>=1.0,<2` (the `patentkit mcp` adapter; install `patentkit[mcp]`)

## Companion skill package

Download/install `patent-research-skill-v2.3.0.zip` from **skill-v2.3.0** (see the Releases page).
