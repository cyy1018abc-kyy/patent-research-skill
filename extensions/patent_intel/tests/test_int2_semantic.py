"""INT2 semantic-lane wiring tests (4.3 W2) — doctor `semantic` section,
persisted-index configuration resolution, and index-backed dense ranking.
Stub-only: no model load, no network."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from patent_intel.cli import EXIT_FAIL, EXIT_OK, _cmd_doctor
from patent_intel.retrieval.hybrid import (
    DENSE_INDEX_DIR_ENV,
    DENSE_INDEX_NAME_ENV,
    DenseRetriever,
    dense_backend_info,
    dense_index_status,
    load_configured_dense_index,
)


def _write_manifest(directory: Path, name: str, *, sha: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    index_file = f"{name}.npz"
    payload = b"stub-index-bytes"
    if sha is None:
        sha = hashlib.sha256(payload).hexdigest()
    (directory / index_file).write_bytes(payload)
    manifest = {"model_id": "Snowflake/snowflake-arctic-embed-m-v2.0", "dims": 768,
                "count": 2, "corpus_sha256": "0" * 64, "build_seconds": 1.0,
                "index_file": index_file, "index_name": name,
                "index_sha256": sha}
    path = directory / f"{name}.manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class TestDenseBackendInfo:
    def test_keys_present_without_model_load(self):
        info = dense_backend_info()
        for key in ("model_id", "model_dir", "snapshot_complete",
                    "dense_extra_importable", "rerank_eval_lane_importable"):
            assert key in info
        assert isinstance(info["snapshot_complete"], bool)


class TestDenseIndexStatus:
    def test_unconfigured(self, monkeypatch):
        monkeypatch.delenv(DENSE_INDEX_DIR_ENV, raising=False)
        assert dense_index_status()["configured"] is False

    def test_manifest_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv(DENSE_INDEX_DIR_ENV, str(tmp_path))
        monkeypatch.delenv(DENSE_INDEX_NAME_ENV, raising=False)
        status = dense_index_status()
        assert status["configured"] is True and status["manifest_found"] is False

    def test_manifest_without_sha_field(self, monkeypatch, tmp_path):
        path = _write_manifest(tmp_path, "dense-full")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest.pop("index_sha256")
        path.write_text(json.dumps(manifest), encoding="utf-8")
        monkeypatch.setenv(DENSE_INDEX_DIR_ENV, str(tmp_path))
        status = dense_index_status()
        assert status["manifest_found"] is True and status["sha256_ok"] is None
        assert status["count"] == 2 and status["dims"] == 768

    def test_sha_mismatch_detected(self, monkeypatch, tmp_path):
        _write_manifest(tmp_path, "dense-full", sha="f" * 64)
        monkeypatch.setenv(DENSE_INDEX_DIR_ENV, str(tmp_path))
        assert dense_index_status()["sha256_ok"] is False

    def test_sha_match_detected(self, monkeypatch, tmp_path):
        _write_manifest(tmp_path, "dense-full")
        monkeypatch.setenv(DENSE_INDEX_DIR_ENV, str(tmp_path))
        assert dense_index_status()["sha256_ok"] is True


class TestLoadConfiguredIndex:
    def test_unconfigured_returns_none(self, monkeypatch):
        monkeypatch.delenv(DENSE_INDEX_DIR_ENV, raising=False)
        assert load_configured_dense_index() is None

    def test_missing_manifest_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv(DENSE_INDEX_DIR_ENV, str(tmp_path))
        with pytest.raises(FileNotFoundError):
            load_configured_dense_index()


class TestIndexBackedRank:
    def test_rank_delegates_and_ignores_docs(self):
        class _StubIndex:
            def __init__(self):
                self.queries: list[str] = []

            def search(self, query, *, top=10):
                self.queries.append(query)
                return [("z9", 0.9), ("a1", 0.5)][:top]

        def _no_backend():
            raise RuntimeError("no model")

        r = DenseRetriever(backend_factory=_no_backend)
        stub = _StubIndex()
        r.attach_index(stub)
        out = r.rank("cell", [("d1", "text"), ("d2", "text")], top=2)
        assert [d for d, _ in out] == ["z9", "a1"]
        assert stub.queries == ["cell"]  # docs ignored — no per-call encoding


class TestDoctorSemantic:
    def test_doctor_ok_without_configuration(self, monkeypatch, tmp_path, capsys):
        monkeypatch.delenv(DENSE_INDEX_DIR_ENV, raising=False)
        monkeypatch.chdir(tmp_path)
        code = _cmd_doctor(argparse.Namespace(root=None, state_dir=None, json=True))
        report = json.loads(capsys.readouterr().out)
        assert "semantic" in report["checks"]
        assert report["checks"]["semantic"]["note"]
        assert code == EXIT_OK

    def test_doctor_blocking_on_corrupt_index(self, monkeypatch, tmp_path, capsys):
        _write_manifest(tmp_path / "idx", "dense-full", sha="f" * 64)
        monkeypatch.setenv(DENSE_INDEX_DIR_ENV, str(tmp_path / "idx"))
        monkeypatch.delenv(DENSE_INDEX_NAME_ENV, raising=False)
        monkeypatch.chdir(tmp_path)
        code = _cmd_doctor(argparse.Namespace(root=None, state_dir=None, json=True))
        report = json.loads(capsys.readouterr().out)
        assert report["checks"]["semantic"]["index"]["sha256_ok"] is False
        assert code == EXIT_FAIL
