# patentkit 0.1.1

Validation and acceptance-gate kernel for patent workspaces (CLI + Python library).
It is the rule-execution layer used by the `patent-research-skill` package:
three-level evidence classification, V001-V028 validation, G-S-01..05 gates.

## Changes (0.1.0 -> 0.1.1)

- **Fixed**: a G-S-01 hint in `gates.py` could echo a historical target ID; replaced
  with a generic message.
- **Single version source**: the literal `__version__` lives only in
  `patentkit/__init__.py`; `pyproject.toml` reads it dynamically.
- Documentation counts aligned with the actual implementation.

## Assets

| Asset | SHA-256 |
|---|---|
| `patentkit-0.1.1-py3-none-any.whl` | `6edb60f761f03b88039ad50e58d5a271a397bc1883fcb43be8080eabd70f4231` |
| `patentkit-0.1.1.tar.gz` | `a77066c0db61fc40a0b791a9aebd2ff298764be512c2ad2c6f28c64e661f5585` |
| `SHA256SUMS-patentkit-v0.1.1.txt` | — |

## Install

```powershell
pip install https://github.com/cyy1018abc-kyy/patent-research-skill/releases/download/patentkit-v0.1.1/patentkit-0.1.1-py3-none-any.whl
```

## Requirements

- Python >= 3.11
- Runtime dependencies: `jsonschema>=4.18`, `PyYAML>=6.0` (installed by pip)
- Optional MCP adapter: `mcp>=1.0,<2` (`pip install "patentkit[mcp]"` from source)

## Companion skill

Install `patent-research-skill` v2.3.2 from the same Releases page.
