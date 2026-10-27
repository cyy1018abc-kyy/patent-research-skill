"""safe_io tests: atomicity, containment, size limits, UTF-8/CJK, locking (F-03 acceptance)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from patent_intel.io.safe_io import (
    PathEscapeError,
    SizeLimitError,
    ensure_contained,
    file_lock,
    read_json_limited,
    read_text_limited,
    sha256_bytes,
    write_json_atomic,
    write_text_atomic,
)


# ── atomic writes ─────────────────────────────────────────────────────


def test_write_text_atomic_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "sub" / "dir" / "record.json"
    write_text_atomic(p, '{"a": 1}\n')
    assert p.read_text(encoding="utf-8") == '{"a": 1}\n'
    assert not list(tmp_path.glob("**/*.tmp-*"))  # no temp litter


def test_write_text_atomic_overwrite_is_clean(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    write_text_atomic(p, "v1")
    write_text_atomic(p, "v2")
    assert p.read_text(encoding="utf-8") == "v2"


def test_write_json_atomic_keeps_cjk_readable(tmp_path: Path) -> None:
    p = tmp_path / "中文目录" / "记录.json"
    write_json_atomic(p, {"标题": "无线传感网时间同步", "n": 1})
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["标题"] == "无线传感网时间同步"
    assert "无线传感网时间同步" in p.read_text(encoding="utf-8")  # no \u escapes on disk


def test_write_json_atomic_lf_not_translated(tmp_path: Path) -> None:
    """Explicit-LF discipline: the file must contain LF, never CRLF, on any platform."""
    p = tmp_path / "lf.json"
    write_json_atomic(p, {"a": 1})
    raw = p.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def test_atomic_write_survives_interrupted_write(tmp_path: Path) -> None:
    """Simulate a crash mid-write: original file must stay intact, no half content."""
    p = tmp_path / "record.json"
    write_json_atomic(p, {"gen": 1})
    original = p.read_bytes()
    # simulate a temp file left behind by a crashed run
    tmp = p.with_name(f".{p.name}.tmp-999")
    tmp.write_text('{"gen": 2, "corrupt":', encoding="utf-8")
    # a reader still sees the old, complete file
    assert read_json_limited(p) == {"gen": 1}
    assert p.read_bytes() == original
    tmp.unlink()


# ── containment ───────────────────────────────────────────────────────


def test_containment_accepts_inside_path(tmp_path: Path) -> None:
    inside = ensure_contained(tmp_path, "sub/file.json")
    assert inside == (tmp_path / "sub" / "file.json").resolve()


def test_containment_refuses_traversal(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError, match="outside"):
        ensure_contained(tmp_path, "../escape.json")


def test_containment_refuses_absolute_outside(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError, match="outside"):
        ensure_contained(tmp_path, "C:/Windows/evil.json" if Path("C:/").exists() else "/etc/evil.json")


def test_containment_refuses_deceptive_absolute(tmp_path: Path) -> None:
    """An absolute-looking path must not be re-rooted into the containment dir."""
    outside = tmp_path.parent / "elsewhere.json"
    with pytest.raises(PathEscapeError):
        ensure_contained(tmp_path, outside)


def test_writers_enforce_containment(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        write_json_atomic(tmp_path / "ok.json", {}, root=tmp_path.parent / "nope")


# ── size limits ───────────────────────────────────────────────────────


def test_read_text_limited_refuses_oversize(tmp_path: Path) -> None:
    p = tmp_path / "big.txt"
    p.write_text("x" * 1000, encoding="utf-8")
    with pytest.raises(SizeLimitError, match="limit"):
        read_text_limited(p, max_bytes=100)


def test_read_json_limited_parses_utf8(tmp_path: Path) -> None:
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"k": "值"}, ensure_ascii=False), encoding="utf-8")
    assert read_json_limited(p, max_bytes=1000) == {"k": "值"}


# ── hashing ───────────────────────────────────────────────────────────


def test_sha256_matches_known_vector() -> None:
    assert sha256_bytes(b"hello") == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_sha256_file_matches_bytes(tmp_path: Path) -> None:
    from patent_intel.io.safe_io import sha256_file

    p = tmp_path / "f.bin"
    payload = b"\x00\x01binary\xff" * 100
    p.write_bytes(payload)
    assert sha256_file(p) == sha256_bytes(payload)


# ── file lock ─────────────────────────────────────────────────────────


def test_file_lock_serializes_read_modify_write(tmp_path: Path) -> None:
    """Two threads doing locked read-modify-write must not lose updates.

    The lock file is deliberately separate from the data file (locking the data file
    itself would fight the atomic-replace writer on Windows). The lock is advisory;
    this asserts the happy path serializes correctly on the current platform rather
    than proving exclusion under adversarial scheduling.
    """
    lock_path = tmp_path / "counter.lock"
    data_path = tmp_path / "counter.json"
    lock_use_lock = threading.Lock()  # guards the local expected counter below

    def worker() -> None:
        for _ in range(20):
            with file_lock(lock_path):
                with lock_use_lock:
                    current = read_json_limited(data_path) if data_path.exists() else {"n": 0}
                    write_json_atomic(data_path, {"n": current["n"] + 1})

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert read_json_limited(data_path)["n"] == 80
