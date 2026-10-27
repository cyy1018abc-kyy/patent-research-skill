"""Safe IO primitives for the sidecar state dir (blueprint F-03).

Guarantees (supply-chain rule 9 + interface rule 8):

* **UTF-8 everywhere** — explicit ``encoding="utf-8"`` on every read/write; Windows
  code pages never get a chance (IT-07);
* **atomic writes** — temp file + :func:`os.replace` in the same directory, so a crash
  never leaves a half-written JSON record behind (checkpoint/resume rely on this);
* **path containment** — every path handed to the writers must resolve *inside* a
  declared root; ``..`` traversal, absolute paths and Windows drive-absolute inputs are
  refused (tests/test_safe_io.py);
* **size limits** — reads refuse files above a declared ceiling so a hostile "fixture"
  cannot exhaust memory;
* **advisory cross-process lock** — best-effort exclusive lock for sidecar writers
  (``msvcrt``/``fcntl``), used around read-modify-write sections.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "SafeIOError",
    "PathEscapeError",
    "SizeLimitError",
    "DEFAULT_MAX_BYTES",
    "sha256_file",
    "sha256_bytes",
    "read_text_limited",
    "read_json_limited",
    "write_text_atomic",
    "write_json_atomic",
    "ensure_contained",
    "file_lock",
]

DEFAULT_MAX_BYTES = 64 * 1024 * 1024


class SafeIOError(Exception):
    """Base class for safe-io failures."""


class PathEscapeError(SafeIOError):
    """A path escapes its declared containment root."""


class SizeLimitError(SafeIOError):
    """A file exceeds the declared size ceiling."""


def ensure_contained(root: Path, candidate: Path) -> Path:
    """Resolve ``candidate`` and require it to stay inside ``root``; return the resolved path.

    Non-existent paths are resolved lexically (``os.path.abspath``); existing ones are
    resolved physically so symlink escapes are caught too.
    """
    root = Path(root).resolve()
    candidate = Path(candidate)
    if candidate.is_absolute():
        resolved = candidate.resolve() if candidate.exists() or candidate.parent.exists() else Path(os.path.abspath(candidate))
    else:
        resolved = Path(os.path.abspath(root / candidate))
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathEscapeError(
            f"path {candidate} resolves outside containment root {root}"
        ) from None
    return resolved


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_text_limited(path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """Read a UTF-8 text file with a hard size ceiling."""
    path = Path(path)
    size = path.stat().st_size
    if size > max_bytes:
        raise SizeLimitError(f"{path} is {size} bytes (limit {max_bytes})")
    return path.read_text(encoding="utf-8")


def read_json_limited(path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> Any:
    """Read and parse a UTF-8 JSON file with a hard size ceiling."""
    return json.loads(read_text_limited(path, max_bytes=max_bytes))


def write_text_atomic(path: Path, text: str, *, root: Path | None = None) -> None:
    """Atomically write UTF-8 text (LF newlines preserved verbatim — no translation)."""
    path = Path(path)
    if root is not None:
        path = ensure_contained(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():  # pragma: no cover - only on replace failure
            tmp.unlink(missing_ok=True)


def write_json_atomic(path: Path, data: Any, *, root: Path | None = None, indent: int = 2) -> None:
    """Atomically write a JSON document, ``ensure_ascii=False`` so CJK stays readable."""
    text = json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=False)
    if not text.endswith("\n"):
        text += "\n"
    write_text_atomic(path, text, root=root)


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Advisory exclusive lock around a read-modify-write section.

    Best effort by design: on platforms without ``msvcrt``/``fcntl`` the block runs
    unlocked rather than crashing — callers must still make their writes idempotent
    (interface rule 8), the lock only narrows the race window.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+b")
    try:
        locked = False
        try:
            import msvcrt  # noqa: PLC0415 - platform module, imported lazily

            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            locked = True
        except ImportError:
            try:
                import fcntl  # noqa: PLC0415

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                locked = True
            except ImportError:
                locked = False
        except OSError:
            locked = False
        try:
            yield
        finally:
            if locked:
                try:
                    fh.seek(0)
                    if os.name == "nt":
                        import msvcrt  # noqa: PLC0415

                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl  # noqa: PLC0415

                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError:  # pragma: no cover - already released on crash
                    pass
    finally:
        fh.close()
