"""Raw-artifact registration (adaptive roadmap Task 4).

统一登记，不统一物理路径 — see :mod:`patent_intel.artifacts.registry`.
"""

from patent_intel.artifacts.registry import (
    RawArtifactRegistry,
    RegistrationError,
    infer_mime,
)

__all__ = ["RawArtifactRegistry", "RegistrationError", "infer_mime"]
