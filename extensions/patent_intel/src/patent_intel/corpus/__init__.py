"""Corpus lifecycle (adaptive roadmap Stage 3 / Task 6).

Hybrid local corpus: frozen evaluation sets, incremental production imports,
content-addressed snapshots and versioned index manifests.
"""

from patent_intel.corpus.manager import CorpusManager
from patent_intel.corpus.models import (
    CorpusSnapshot,
    CorpusUpdate,
    EvaluationCorpus,
    IndexManifest,
    IndexStatus,
    UpdateMode,
)

__all__ = [
    "CorpusManager",
    "CorpusUpdate",
    "CorpusSnapshot",
    "EvaluationCorpus",
    "IndexManifest",
    "IndexStatus",
    "UpdateMode",
]
