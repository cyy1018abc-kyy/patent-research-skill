#!/usr/bin/env python3
"""Guard: every text-mode file IO pins an explicit encoding; every CLI entrypoint pins UTF-8 stdio.

Background (PR #15 CI, Phase L / WP-L1): a tools/ script printed an em-dash through a
cp1252-default stdout, the parent test's UTF-8 reader thread died mid-decode, and the
captured stream came back as ``None`` (``TypeError: NoneType is not iterable``).
Locally PYTHONUTF8 / PYTHONIOENCODING mask the whole bug class, so this check is
AST-based and environment-independent (runs identically on any locale).

Rules:
  A  builtin ``open()`` / ``Path.open()`` in text mode and ``read_text()`` /
     ``write_text()`` — must pass ``encoding=``; binary modes and archive modules
     (``tarfile.open(fileobj=...)`` etc.) are exempt;
  B  every entrypoint script under ``tools/``, ``evals/`` and ``research/scripts/``
     must pin stdio to UTF-8 (a ``*_pin_utf8*`` helper call, ``configure_stdio()``
     or an explicit ``reconfigure(encoding="utf-8")``) — tools own their output
     encoding, their callers' harnesses must be able to assume UTF-8.

Exit 0 = clean, 1 = violations listed (run in CI next to the other four guards).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("tools", "tests", "extensions", "evals", "research/scripts")
STDIO_PIN_ROOTS = ("tools", "evals", "research/scripts")
EXCLUDE_SEGMENTS = {".venv", "kernel-build", "_upstream", "build", "dist", ".git", "__pycache__"}
ARCHIVE_OPEN_RECEIVERS = {"tarfile", "zipfile", "gzip", "bz2", "io", "codecs"}


def _iter_py_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if EXCLUDE_SEGMENTS & set(p.parts) or any("egg-info" in seg for seg in p.parts):
                continue
            files.append(p)
    return sorted(files)


def _keyword(node: ast.Call, name: str) -> ast.keyword | None:
    return next((kw for kw in node.keywords if kw.arg == name), None)


def _mode_of(node: ast.Call) -> str | None:
    """Positional mode first (``open(f, "w")`` / ``fh.open("a")``), then ``mode=``."""
    if isinstance(node.func, ast.Name) and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        return str(node.args[1].value)
    if isinstance(node.func, ast.Attribute) and node.args and isinstance(node.args[0], ast.Constant):
        return str(node.args[0].value)
    kw = _keyword(node, "mode")
    if kw is not None and isinstance(kw.value, ast.Constant):
        return str(kw.value.value)
    return None


def _text_io_violation(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "open":
        if "b" in (_mode_of(node) or "") or _keyword(node, "encoding") is not None:
            return None
        return "open() text mode without encoding="
    if isinstance(func, ast.Attribute):
        name = func.attr
        if name == "open":
            if isinstance(func.value, ast.Name) and func.value.id in ARCHIVE_OPEN_RECEIVERS:
                return None
            if _keyword(node, "fileobj") is not None:  # archive-style: tarfile.open(fileobj=...)
                return None
            if "b" in (_mode_of(node) or "") or _keyword(node, "encoding") is not None:
                return None
            return ".open() text mode without encoding="
        if name in ("read_text", "write_text") and _keyword(node, "encoding") is None:
            return f"{name}() without encoding="
    return None


def _stdio_pinned(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        fname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
        if "pin_utf8" in fname or fname == "configure_stdio":
            return True
        if fname == "reconfigure":
            kw = _keyword(node, "encoding")
            if kw is not None and isinstance(kw.value, ast.Constant) and "utf-8" in str(kw.value.value):
                return True
    return False


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> int:
    _pin_utf8_stdio()
    violations: list[str] = []
    scanned = 0
    for path in _iter_py_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        scanned += 1
        tree = ast.parse(path.read_bytes(), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                why = _text_io_violation(node)
                if why:
                    violations.append(f"{rel}:{node.lineno}  {why}")
        if rel.startswith(STDIO_PIN_ROOTS):
            if not _stdio_pinned(tree):
                violations.append(f"{rel}:0  entrypoint does not pin UTF-8 stdio (_pin_utf8_stdio / configure_stdio)")
    if violations:
        print(f"[FAIL] explicit-encoding guard: {len(violations)} violation(s)")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"[OK] explicit-encoding guard: {scanned} files — text IO encoding + entrypoint stdio pinning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
