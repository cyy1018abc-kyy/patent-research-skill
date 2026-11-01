"""Normalization layer (adaptive roadmap Stage 2).

Cross-source identifier and field normalization that stays honest about what each
source actually reported: original strings preserved verbatim, confidence graded,
conflicts kept and auditable.
"""

from patent_intel.normalization.conflicts import FieldConflictLog, FieldValue, ResolvedField

__all__ = ["FieldConflictLog", "FieldValue", "ResolvedField"]
