"""Stub-backend unit tests for the DE1 dense corpus index (4.3).

No model is ever downloaded or loaded here: DenseRetriever either gets an
injected stub ``backend_factory`` or has its import lanes blocked; DenseIndex
runs on hand-built vectors. Cases needing numpy carry
``@pytest.mark.skipif`` so the pure-python lane (numpy-less kernel venv) still
runs the contract tests (backend error message, manifest contract shape).
"""

from __future__ import annotations

import builtins
import json

import pytest

from patent_intel.retrieval.hybrid import (
    DEFAULT_DENSE_MODEL_DIR,
    DENSE_INDEX_REQUIRED_MANIFEST_FIELDS,
    DENSE_MODEL_ID,
    DenseIndex,
    DenseRetriever,
    dense_unavailable_message,
)

try:
    import numpy as np
except ImportError:  # pure-python lane (kernel venv)
    np = None

requires_numpy = pytest.mark.skipif(np is None, reason="numpy not installed in this lane")

BLOCKED_LANES = {"fastembed", "sentence_transformers"}


def _block_backend_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make fastembed/sentence_transformers unimportable regardless of the venv."""
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split(".")[0] in BLOCKED_LANES:
            raise ImportError(f"blocked for this test: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


class _StubBackend:
    """Satisfies the backend contract: embed(texts, batch_size=...) -> 2-D rows."""

    def __init__(self, table: dict[str, list[float]]):
        self.table = table
        self.embedded: list[list[str]] = []

    def embed(self, texts, batch_size=64, **kwargs):
        self.embedded.append(list(texts))
        return np.asarray([self.table[t] for t in texts], dtype="float32")


# ── DenseRetriever backend contract ──────────────────────────────────────────


def test_missing_backend_message_names_extra_and_local_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    """No backend at all -> RuntimeError naming the dense extra (numpy+fastembed,
    never sentence-transformers) and the local weights path (DE1 defect fix)."""
    _block_backend_imports(monkeypatch)
    retriever = DenseRetriever()
    with pytest.raises(RuntimeError) as excinfo:
        retriever.rank("query", [("doc-1", "some text")], top=3)
    message = str(excinfo.value)
    assert "fastembed" in message
    assert str(DEFAULT_DENSE_MODEL_DIR) in message
    assert "_models" in str(DEFAULT_DENSE_MODEL_DIR)
    assert "pip install 'patent_intel[dense]'" in message
    # the fixed defect: the extra no longer promises sentence-transformers
    assert "installs numpy+sentence-transformers" not in message


def test_missing_backend_message_via_encode_query(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_backend_imports(monkeypatch)
    with pytest.raises(RuntimeError) as excinfo:
        DenseRetriever().encode_query("query")
    assert "fastembed" in str(excinfo.value)


def test_missing_backend_message_is_stable_and_covers_weights_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_backend_imports(monkeypatch)
    assert dense_unavailable_message() == dense_unavailable_message()
    assert DENSE_MODEL_ID in dense_unavailable_message()


def test_rank_with_stub_backend_orders_and_breaks_ties_by_id() -> None:
    if np is None:
        pytest.skip("numpy not installed in this lane")
    table = {
        "query": [1.0, 0.0],
        "doc-a": [1.0, 0.0],   # cos 1.0
        "doc-b": [0.6, 0.8],   # cos 0.6
        "doc-c": [0.0, 1.0],   # cos 0.0
        "doc-t1": [0.0, 1.0],  # cos 0.0 — tie with doc-t2, id ascending
        "doc-t2": [0.0, 1.0],
    }
    retriever = DenseRetriever(backend_factory=lambda: _StubBackend(table))
    docs = [("doc-c", "doc-c"), ("doc-t2", "doc-t2"), ("doc-a", "doc-a"),
            ("doc-b", "doc-b"), ("doc-t1", "doc-t1")]
    ranked = retriever.rank("query", docs, top=5)
    assert [d for d, _ in ranked] == ["doc-a", "doc-b", "doc-c", "doc-t1", "doc-t2"]
    assert ranked[0][1] == pytest.approx(1.0)
    assert ranked[1][1] == pytest.approx(0.6)
    assert ranked[2][1] == pytest.approx(0.0)


def test_rank_with_stub_backend_normalizes_unnormalized_vectors() -> None:
    if np is None:
        pytest.skip("numpy not installed in this lane")
    table = {
        "query": [3.0, 0.0],          # unnormalized
        "doc-x": [2.0, 0.0],          # direction identical to query -> cos 1.0
        "doc-y": [0.0, 5.0],          # orthogonal -> cos 0.0
    }
    retriever = DenseRetriever(backend_factory=lambda: _StubBackend(table))
    ranked = retriever.rank("query", [("doc-y", "doc-y"), ("doc-x", "doc-x")], top=2)
    assert [d for d, _ in ranked] == ["doc-x", "doc-y"]
    assert ranked[0][1] == pytest.approx(1.0)


def test_rank_is_deterministic_across_repeats() -> None:
    if np is None:
        pytest.skip("numpy not installed in this lane")
    table = {
        "query": [1.0, 1.0],
        "doc-a": [1.0, 0.5],
        "doc-b": [0.5, 1.0],
        "doc-c": [1.0, 0.5],  # tie with doc-a -> id ascending
    }
    retriever = DenseRetriever(backend_factory=lambda: _StubBackend(table))
    docs = [("doc-b", "doc-b"), ("doc-c", "doc-c"), ("doc-a", "doc-a")]
    assert retriever.rank("query", docs, top=3) == retriever.rank("query", docs, top=3)


def test_rank_empty_docs_returns_empty() -> None:
    if np is None:
        pytest.skip("numpy not installed in this lane")
    retriever = DenseRetriever(backend_factory=lambda: _StubBackend({"query": [1.0, 0.0]}))
    assert retriever.rank("query", [], top=5) == []


# ── DenseIndex: cosine correctness + determinism ─────────────────────────────


def _toy_index(encoder=None) -> "DenseIndex":
    ids = ["doc-a", "doc-b", "doc-c", "doc-t1", "doc-t2"]
    vectors = [
        [1.0, 0.0],
        [0.6, 0.8],
        [0.0, 1.0],
        [0.0, 1.0],
        [0.0, 1.0],
    ]
    return DenseIndex(ids=ids, vectors=vectors, model_id=DENSE_MODEL_ID, encoder=encoder)


@requires_numpy
def test_dense_index_search_vector_order_and_cosine() -> None:
    index = _toy_index()
    hits = index.search([1.0, 0.0], top=5)
    assert [d for d, _ in hits] == ["doc-a", "doc-b", "doc-c", "doc-t1", "doc-t2"]
    assert hits[0][1] == pytest.approx(1.0)
    assert hits[1][1] == pytest.approx(0.6)
    assert hits[2][1] == pytest.approx(0.0)
    assert hits[1][1] > hits[2][1] >= hits[3][1] >= hits[4][1]


@requires_numpy
def test_dense_index_ties_break_by_id_ascending() -> None:
    index = _toy_index()
    hits = index.search([0.0, 1.0], top=4)
    # doc-c, doc-t1, doc-t2 all tie at cosine 1.0; doc-a/doc-b below
    assert [d for d, _ in hits][:3] == ["doc-c", "doc-t1", "doc-t2"]
    assert hits[0][1] == hits[1][1] == hits[2][1]


@requires_numpy
def test_dense_index_search_is_deterministic() -> None:
    index = _toy_index()
    assert index.search([0.3, 0.7], top=5) == index.search([0.3, 0.7], top=5)


@requires_numpy
def test_dense_index_cosine_handles_unnormalized_input() -> None:
    index = DenseIndex(ids=["big", "small", "ortho"], vectors=[[9.0, 0.0], [0.001, 0.002], [0.0, 4.0]],
                       model_id=DENSE_MODEL_ID)
    hits = index.search([2.0, 0.0], top=3)
    assert [d for d, _ in hits] == ["big", "small", "ortho"]
    assert hits[0][1] == pytest.approx(1.0)               # 9x magnitude, direction kept
    assert hits[1][1] == pytest.approx(0.4472136, abs=1e-6)
    assert hits[2][1] == pytest.approx(0.0)
    # equal-direction unnormalized vectors tie and break by id ascending
    tie = DenseIndex(ids=["b", "a"], vectors=[[5.0, 0.0], [5.0, 0.0]], model_id=DENSE_MODEL_ID)
    assert [d for d, _ in tie.search([2.0, 0.0], top=2)] == ["a", "b"]


@requires_numpy
def test_dense_index_search_by_text_requires_encoder() -> None:
    index = _toy_index()
    with pytest.raises(RuntimeError) as excinfo:
        index.search("some query text", top=2)
    message = str(excinfo.value)
    assert "fastembed" in message
    assert str(DEFAULT_DENSE_MODEL_DIR) in message


@requires_numpy
def test_dense_index_search_by_text_uses_attached_encoder() -> None:
    table = {"alpha q": [1.0, 0.0], "beta q": [0.0, 1.0]}
    index = _toy_index(encoder=lambda text: table[text])
    assert [d for d, _ in index.search("alpha q", top=1)] == ["doc-a"]
    assert [d for d, _ in index.search("beta q", top=1)] == ["doc-c"]  # tie doc-c < doc-t1 < doc-t2


@requires_numpy
def test_dense_index_rejects_bad_shapes() -> None:
    with pytest.raises(ValueError):
        DenseIndex(ids=["a", "b"], vectors=[[1.0, 0.0], [0.0, 1.0]], model_id=DENSE_MODEL_ID, dims=4)
    with pytest.raises(ValueError):
        DenseIndex(ids=["a"], vectors=[[1.0, 0.0], [0.0, 1.0]], model_id=DENSE_MODEL_ID)
    index = _toy_index()
    with pytest.raises(ValueError):
        index.search([1.0, 2.0, 3.0], top=1)  # wrong query length


@requires_numpy
def test_dense_index_build_from_retriever_keeps_provenance() -> None:
    table = {
        "query": [1.0, 0.0],
        "doc-a": [1.0, 0.0],
        "doc-b": [0.0, 1.0],
    }
    retriever = DenseRetriever(backend_factory=lambda: _StubBackend(table))
    index = retriever.build_index(["doc-a", "doc-b"], ["doc-a", "doc-b"], corpus_sha256="abc123")
    assert isinstance(index, DenseIndex)
    assert index.model_id == DENSE_MODEL_ID
    assert index.corpus_sha256 == "abc123"
    assert index.dims == 2
    assert [d for d, _ in index.search("query", top=1)] == ["doc-a"]


# ── DenseIndex persistence: manifest contract ────────────────────────────────


@requires_numpy
def test_dense_index_save_manifest_fields_and_load_roundtrip(tmp_path) -> None:
    index = _toy_index(encoder=lambda text: [1.0, 0.0])
    manifest = index.save(tmp_path, "unit-index", extra={"build_seconds": 1.25, "fields": ["title", "abstract"]})
    for field in DENSE_INDEX_REQUIRED_MANIFEST_FIELDS:
        assert field in manifest, f"manifest missing required field: {field}"
    assert manifest["model_id"] == DENSE_MODEL_ID
    assert manifest["dims"] == 2
    assert manifest["count"] == 5
    assert manifest["build_seconds"] == pytest.approx(1.25)
    assert manifest["index_file"] == "unit-index.npz"

    loaded = DenseIndex.load(tmp_path, "unit-index")
    assert loaded.ids == index.ids
    assert loaded.dims == index.dims
    assert loaded.model_id == index.model_id
    assert loaded.manifest is not None
    assert [d for d, _ in loaded.search([1.0, 0.0], top=2)] == ["doc-a", "doc-b"]
    # load() does not restore a callable encoder (not serializable): a freshly
    # loaded index answers vector search, and text search raises the honest
    # unavailability error until the caller attaches one.
    with pytest.raises(RuntimeError) as excinfo:
        loaded.search("alpha", top=1)
    assert "fastembed" in str(excinfo.value)


@requires_numpy
def test_dense_index_load_rejects_manifest_missing_fields(tmp_path) -> None:
    _toy_index().save(tmp_path, "broken")
    manifest_path = tmp_path / "broken.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["corpus_sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        DenseIndex.load(tmp_path, "broken")
    assert "corpus_sha256" in str(excinfo.value)


@requires_numpy
def test_dense_index_load_rejects_tampered_npz(tmp_path) -> None:
    _toy_index().save(tmp_path, "tampered")
    manifest_path = tmp_path / "tampered.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["index_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        DenseIndex.load(tmp_path, "tampered")


@requires_numpy
def test_dense_index_load_missing_manifest_errors(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        DenseIndex.load(tmp_path, "absent")
