"""patent_intel — optional retrieval/document/evidence extension for the patent-research skills.

Boundary contract (docs/adr/0001-kernel-boundary.md):

* the `patentkit` kernel stays the single authority for evidence levels, G-S gates,
  judgements and sign-off;
* this package only produces proposals, read-only analyses and replayable diagnostics;
* every record it writes carries ``schema_version`` and an ``owner`` work-package tag and
  lives inside the sidecar state dir — kernel workspace files are never modified.

The base install is standard-library only; kernel/pdf/dense/ops capabilities import their
dependencies lazily and degrade with actionable errors.
"""

from __future__ import annotations

__version__ = "0.2.0"

#: Record schemas understood by this build. Records whose ``schema_version`` major is
#: higher than this are refused with UnsupportedSchemaError instead of being silently
#: reinterpreted (docs/architecture/contracts.md).
SCHEMA_VERSION = 1

__all__ = ["__version__", "SCHEMA_VERSION"]
