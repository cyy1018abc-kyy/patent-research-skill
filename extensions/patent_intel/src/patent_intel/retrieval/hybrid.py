"""Hybrid ranking: RRF fusion and family-aware collapse (blueprint A-04).

* :func:`rrf_fuse` — Reciprocal Rank Fusion over multiple ranked lists, fully
  deterministic (ties by stable key order).
* :func:`family_collapse` — one family occupies one ranking slot; same-family
  documents never masquerade as independent hits (UT-S03 / interface rule 4).
* :class:`DenseRetriever` — optional (`dense` extra); degrades with an honest
  error naming the missing dependency. No model download happens implicitly.
  4.3 (DE1, G3 route B): fastembed ONNX is the release backend, loaded from a
  local weights snapshot only; sentence-transformers is the evaluation-lane
  fallback, never a release dependency.
* :class:`DenseIndex` — corpus-level persisted dense index (ids + float32
  embedding matrix + manifest provenance) with brute-force numpy cosine
  search; deterministic ties by doc id ascending.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "rrf_fuse",
    "family_collapse",
    "DenseRetriever",
    "DenseIndex",
    "DENSE_MODEL_ID",
    "DENSE_FASTEMBED_ALIAS",
    "DEFAULT_DENSE_MODEL_DIR",
    "DENSE_MODEL_DIR_ENV",
    "dense_unavailable_message",
]

# ── 4.3 DE1 dense constants ──────────────────────────────────────────────────
# G3 (2026-11-20): embedding = snowflake-arctic-embed-m-v2.0 (Apache-2.0, 768-dim
# MRL, 8192-token context) — the same model the DAPFAM paper calibrated
# IN recall 0.4973 with. Runtime lane B: fastembed ONNX, no torch.
DENSE_MODEL_ID = "Snowflake/snowflake-arctic-embed-m-v2.0"

# fastembed (<=0.9.1) has no registry entry for the v2.0 model: its registry
# check runs before weight resolution and would reject the v2.0 name. We pass
# this v1 registry alias and point ``specific_model_path`` at the local v2.0
# snapshot — ONNX graph + tokenizer all load from that directory and nothing
# is downloaded (local_files_only=True).
DENSE_FASTEMBED_ALIAS = "snowflake/snowflake-arctic-embed-m"

# Local weights snapshot: workspace-level materialization (one-time, outside
# git), consumed read-only at runtime. Override with the env var below.
DENSE_MODEL_DIR_ENV = "PATENT_INTEL_DENSE_MODEL_DIR"
DEFAULT_DENSE_MODEL_DIR = Path(r"F:\GitHub项目合集\专利调研与润色\_models\snowflake-arctic-embed-m-v2.0")

# Manifest fields every persisted index must carry (DE1 contract).
DENSE_INDEX_REQUIRED_MANIFEST_FIELDS = (
    "model_id",
    "dims",
    "count",
    "corpus_sha256",
    "build_seconds",
)


def _resolve_model_dir(model_dir: str | Path | None = None) -> Path:
    if model_dir is not None:
        return Path(model_dir)
    env = os.environ.get(DENSE_MODEL_DIR_ENV)
    if env:
        return Path(env)
    return DEFAULT_DENSE_MODEL_DIR


def _fastembed_snapshot_complete(model_dir: Path) -> bool:
    """True when the local dir carries the ONNX graph + tokenizer fastembed needs."""
    return (model_dir / "onnx" / "model.onnx").is_file() and (model_dir / "tokenizer.json").is_file()


def dense_unavailable_message() -> str:
    """Honest unavailability message: names the extra, the install option and the
    local weights path. Kept in sync with the `dense` extra declaration
    (numpy + fastembed) — it never promises sentence-transformers."""
    return (
        "dense retrieval requires the optional 'dense' extra "
        "(numpy>=1.26 + fastembed>=0.7): pip install 'patent_intel[dense]'; "
        "no model download happens implicitly — place the local weights snapshot of "
        f"{DENSE_MODEL_ID} at {_resolve_model_dir()} "
        f"(override with {DENSE_MODEL_DIR_ENV}; the snapshot is materialized once, "
        "e.g. HF_ENDPOINT=https://hf-mirror.com python -c \"from huggingface_hub import "
        f"snapshot_download; snapshot_download('{DENSE_MODEL_ID}', local_dir="
        f"'{_resolve_model_dir()}')\"); until then ranking degrades to BM25-only"
    )


def rrf_fuse(
    rankings: dict[str, list[str]],
    *,
    k: int = 60,
    top: int | None = None,
    weights: dict[str, float] | None = None,
) -> list[tuple[str, float]]:
    """Fuse named rankings into one list by RRF: score = Σ w_i/(k + rank_i).

    Deterministic: equal fused scores break by doc id ascending; input list order
    is also a tiebreaker (dict insertion order), so identical inputs give identical
    outputs (UT-R01). ``weights`` optionally scales each channel (default 1.0);
    weights do not participate in tie-breaking — equal scores still break by doc id.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    channel_weights = weights or {}
    scores: dict[str, float] = {}
    for source_name in rankings:
        weight = channel_weights.get(source_name, 1.0)
        for rank, doc_id in enumerate(rankings[source_name], start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
    fused = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return fused[:top] if top else fused


def family_collapse(
    ranked: list[tuple[str, float]],
    family_of: dict[str, str],
) -> list[tuple[str, float]]:
    """Collapse ranked docs to one representative per family (best position kept).

    Docs without a family mapping stay independent — unknown family relations are
    never invented here (that merging belongs to kernel census, G-S-04).
    """
    seen_families: set[str] = set()
    out: list[tuple[str, float]] = []
    for doc_id, score in ranked:
        family = family_of.get(doc_id)
        if family is not None:
            if family in seen_families:
                continue
            seen_families.add(family)
        out.append((doc_id, score))
    return out


class _SentenceTransformersBackend:
    """Adapts a SentenceTransformer to the ``embed(texts, batch_size=...)`` contract."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def embed(self, texts: Sequence[str], batch_size: int = 64, **_: Any) -> Any:
        return self._model.encode(
            list(texts),
            batch_size=max(1, batch_size),
            normalize_embeddings=True,
            show_progress_bar=False,
        )


def _chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


class DenseRetriever:
    """Optional dense retrieval. Requires the `dense` extra; no implicit downloads.

    Backend order (4.3 G3 route B):

    1. ``backend_factory`` — an injected callable returning an object with
       ``embed(texts, batch_size=...) -> 2-D array of L2-normalized rows``
       (test stubs plug in here);
    2. fastembed ONNX (release lane) — loaded from the local weights snapshot
       only (``local_files_only=True``); missing/failed weights raise
       RuntimeError instead of downloading;
    3. sentence-transformers (evaluation lane) — only when fastembed is not
       installed; never a release dependency;
    4. RuntimeError naming the `dense` extra, the install option and the local
       weights path.

    There is no silent cross-lane fallback: once fastembed is importable it owns
    the request (loading sentence-transformers would pull torch into release
    contexts, which G3 forbids).
    """

    def __init__(
        self,
        model_id: str = DENSE_MODEL_ID,
        *,
        model_dir: str | Path | None = None,
        backend_factory: Callable[[], Any] | None = None,
        threads: int | None = None,
        batch_size: int = 64,
    ) -> None:
        self.model_id = model_id
        self.model_dir = _resolve_model_dir(model_dir)
        self._backend_factory = backend_factory
        self._threads = threads
        self._batch_size = max(1, int(batch_size))
        self._model: Any = None

    # ── backend resolution ────────────────────────────────────────────
    def _require_model(self) -> Any:
        if self._model is None:
            if self._backend_factory is not None:
                self._model = self._backend_factory()
            else:
                self._model = self._resolve_backend()
        return self._model

    def _resolve_backend(self) -> Any:
        try:
            from fastembed import TextEmbedding  # type: ignore[attr-defined]
        except ImportError:
            pass
        else:
            return self._fastembed_backend(TextEmbedding)
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[attr-defined]
        except ImportError:
            raise RuntimeError(dense_unavailable_message()) from None
        return self._st_backend(SentenceTransformer)

    def _fastembed_backend(self, text_embedding_cls: Any) -> Any:
        if not _fastembed_snapshot_complete(self.model_dir):
            raise RuntimeError(dense_unavailable_message())
        # The v2.0 model is absent from fastembed's registry (<=0.9.1); the alias
        # passes the registry check while specific_model_path pins ALL artifacts
        # (ONNX graph, tokenizer) to the local snapshot. Nothing is downloaded.
        try:
            return text_embedding_cls(
                model_name=DENSE_FASTEMBED_ALIAS,
                specific_model_path=str(self.model_dir),
                local_files_only=True,
                threads=self._threads,
            )
        except Exception as exc:  # pragma: no cover - depends on broken snapshots
            raise RuntimeError(
                "fastembed could not load the local dense weights from "
                f"{self.model_dir} ({exc}); nothing was downloaded — restore the "
                f"snapshot or point {DENSE_MODEL_DIR_ENV} at a complete one"
            ) from exc

    def _st_backend(self, sentence_transformer_cls: Any) -> Any:  # pragma: no cover - evaluation lane
        if not (self.model_dir / "model.safetensors").is_file():
            raise RuntimeError(dense_unavailable_message())
        try:
            return _SentenceTransformersBackend(
                sentence_transformer_cls(str(self.model_dir), local_files_only=True)
            )
        except TypeError:  # older sentence-transformers without local_files_only
            return _SentenceTransformersBackend(sentence_transformer_cls(str(self.model_dir)))
        except Exception as exc:
            raise RuntimeError(dense_unavailable_message()) from exc

    # ── encoding ──────────────────────────────────────────────────────
    def encode_query(self, query: str) -> Any:
        """One query text -> 1-D L2-normalized float32 vector."""
        model = self._require_model()
        import numpy as np  # provided by the dense extra

        vec = np.asarray(list(model.embed([query], batch_size=1)), dtype=np.float32)[0]
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0.0 else vec

    def encode_documents(self, texts: Sequence[str], *, batch_size: int | None = None) -> Any:
        """Texts -> (N, dims) float32 matrix of L2-normalized rows, input order kept.

        Rows are re-normalized defensively (idempotent for backends that already
        emit unit vectors): cosine math here must never silently depend on the
        backend honoring the normalized-rows contract.
        """
        model = self._require_model()
        import numpy as np  # provided by the dense extra

        effective = max(1, self._batch_size if batch_size is None else int(batch_size))
        batches = [
            np.asarray(list(model.embed(chunk, batch_size=effective)), dtype=np.float32)
            for chunk in _chunks(list(texts), effective)
        ]
        if not batches:
            return np.zeros((0, 0), dtype=np.float32)
        matrix = np.concatenate(batches, axis=0)
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0.0] = 1.0
        return matrix / norms[:, None]

    # ── ranking ───────────────────────────────────────────────────────
    def rank(self, query: str, docs: list[tuple[str, str]], *, top: int = 10) -> list[tuple[str, float]]:
        """Rank (doc_id, text) pairs by cosine similarity. Deterministic per model."""
        model = self._require_model()
        import numpy as np  # provided by the dense extra

        doc_ids = [d[0] for d in docs]
        if not doc_ids:
            return []
        q = np.asarray(self.encode_query(query), dtype=np.float32)
        matrix = self.encode_documents([d[1] for d in docs])
        sims = matrix @ q
        order = sorted(range(len(doc_ids)), key=lambda i: (-float(sims[i]), doc_ids[i]))
        return [(doc_ids[i], float(sims[i])) for i in order[:top]]

    # ── corpus-level interface (DE1) ──────────────────────────────────
    def build_index(
        self,
        ids: Sequence[str],
        texts: Sequence[str],
        *,
        corpus_sha256: str | None = None,
        batch_size: int | None = None,
    ) -> "DenseIndex":
        """Embed a whole corpus and return a searchable :class:`DenseIndex`."""
        vectors = self.encode_documents(texts, batch_size=batch_size)
        return DenseIndex(
            ids=list(ids),
            vectors=vectors,
            model_id=self.model_id,
            corpus_sha256=corpus_sha256,
            encoder=self.encode_query,
        )


class DenseIndex:
    """Corpus-level persisted dense index: brute-force numpy cosine.

    Rows are L2-normalized at construction (and the query at search time), so
    the dot product is exactly cosine similarity whatever the caller passed in.
    Deterministic: score ties always break by doc id ascending, so identical
    inputs give identical outputs. ``corpus_sha256`` carries the provenance hash
    of the source corpus file for the manifest (Audit Integrity convention).
    """

    def __init__(
        self,
        ids: Sequence[str],
        vectors: Any,
        model_id: str,
        dims: int | None = None,
        corpus_sha256: str | None = None,
        encoder: Callable[[str], Any] | None = None,
    ) -> None:
        import numpy as np  # provided by the dense extra

        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2:
            raise ValueError(f"vectors must be 2-D (n, dims), got shape {matrix.shape}")
        id_list = list(ids)
        if len(id_list) != len(matrix):
            raise ValueError(f"ids/vectors length mismatch: {len(id_list)} ids vs {len(matrix)} rows")
        resolved_dims = matrix.shape[1] if dims is None else int(dims)
        if matrix.shape[1] != resolved_dims:
            raise ValueError(f"dims={resolved_dims} does not match vectors shape {matrix.shape}")
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0.0] = 1.0
        self._matrix = matrix / norms[:, None]
        self.ids = id_list
        self.model_id = model_id
        self.dims = resolved_dims
        self.corpus_sha256 = corpus_sha256
        self.encoder = encoder
        self.manifest: dict[str, Any] | None = None

    # ── search ────────────────────────────────────────────────────────
    def search(self, query: Any, *, top: int = 10) -> list[tuple[str, float]]:
        """Search by query vector or query text; returns [(doc_id, cosine), ...].

        ``query`` may be a 1-D vector (length ``dims``) or a text string; strings
        require an encoder to be attached (see :meth:`DenseRetriever.build_index`).
        Ties break by doc id ascending.
        """
        import numpy as np  # provided by the dense extra

        if isinstance(query, str):
            if self.encoder is None:
                raise RuntimeError(dense_unavailable_message())
            qvec = np.asarray(self.encoder(query), dtype=np.float32).reshape(-1)
        else:
            qvec = np.asarray(query, dtype=np.float32).reshape(-1)
        if qvec.shape[0] != self.dims:
            raise ValueError(f"query vector must have length {self.dims}, got {qvec.shape[0]}")
        norm = float(np.linalg.norm(qvec))
        if norm > 0.0:
            qvec = qvec / norm
        sims = self._matrix @ qvec
        order = sorted(range(len(self.ids)), key=lambda i: (-float(sims[i]), self.ids[i]))
        return [(self.ids[i], float(sims[i])) for i in order[:top]]

    # ── persistence ───────────────────────────────────────────────────
    def save(
        self,
        out_dir: str | Path,
        name: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write ``<name>.npz`` (ids + float32 matrix) plus a ``<name>.manifest.json``
        sidecar and return the manifest. Index artifacts are runtime outputs and
        never enter git."""
        import numpy as np  # provided by the dense extra

        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        index_path = out_path / f"{name}.npz"
        np.savez(index_path, ids=np.asarray(self.ids, dtype=np.str_), vectors=self._matrix)
        extra_fields = dict(extra or {})
        manifest: dict[str, Any] = dict(extra_fields)
        manifest.update(
            {
                "index_name": name,
                "index_file": index_path.name,
                "index_sha256": _sha256_file(index_path),
                "model_id": self.model_id,
                "dims": self.dims,
                "count": len(self.ids),
                "corpus_sha256": self.corpus_sha256,
                "build_seconds": float(extra_fields.get("build_seconds", 0.0)),
            }
        )
        manifest_path = out_path / f"{name}.manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.manifest = manifest
        return manifest

    @classmethod
    def load(cls, out_dir: str | Path, name: str) -> "DenseIndex":
        """Load ``<name>.npz`` + sidecar manifest; validates the required fields."""
        import numpy as np  # provided by the dense extra

        out_path = Path(out_dir)
        manifest_path = out_path / f"{name}.manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        missing = [f for f in DENSE_INDEX_REQUIRED_MANIFEST_FIELDS if f not in manifest]
        if missing:
            raise ValueError(f"index manifest {manifest_path.name} is missing fields: {missing}")
        index_file = manifest.get("index_file", f"{name}.npz")
        if manifest.get("index_sha256"):
            actual = _sha256_file(out_path / index_file)
            if actual != manifest["index_sha256"]:
                raise ValueError(
                    f"index file {index_file} sha256 mismatch: manifest "
                    f"{manifest['index_sha256'][:12]}… vs actual {actual[:12]}…"
                )
        data = np.load(out_path / index_file, allow_pickle=False)
        index = cls(
            ids=[str(x) for x in data["ids"].tolist()],
            vectors=data["vectors"],
            model_id=manifest["model_id"],
            dims=manifest["dims"],
            corpus_sha256=manifest.get("corpus_sha256"),
        )
        index.manifest = manifest
        return index
