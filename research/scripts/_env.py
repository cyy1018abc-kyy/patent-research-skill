"""Shared environment layer for the skill scripts — encoding, dependencies, workspace, JSON.

Commands under `scripts/` are invoked by **LLM clients as subprocesses** (Codex CLI / Claude Code /
Cline …); the caller only cares about "exit code + whether stdout can be parsed", not terminal
formatting. Four classes of problems recur in such environments, so they are handled centrally here
and each command script keeps only its business presentation:

| Problem | Consequence if unhandled | Handling here |
|---|---|---|
| Windows console encodes stdout as GBK | Printing ✅/⚠️ crashes with `UnicodeEncodeError`; the subprocess captures mojibake | `configure_stdio()` locks UTF-8 |
| patentkit not installed | A screenful of traceback; the client does not know what to install | `require_patentkit()` prints the install command, exit 3 |
| Not inside a workspace | Silent fallback to cwd, misleading "glossary does not exist" | `resolve_workspace()` uses a fixed resolution order, exit 2 + three fixes |
| Human hints mixed into `--json` | The caller's `json.loads` fails outright | `emit_json()` is the only stdout exit in --json mode |

Exit-code conventions (differences from the `patentkit` CLI are in `scripts/README.md`):

| Code | Meaning |
|---|---|
| 0 | Success; the command's own determination passed |
| 1 | Business failure: validation errors / not all gates PASS / report cannot be written |
| 2 | Workspace problem: not located, wrong `--root`, unparseable workspace data; argparse usage errors are also 2 |
| 3 | Missing dependency: Python < 3.11, or patentkit / its dependencies not installed |

Design constraint: **this file depends only on the standard library**. All patentkit imports are deferred
into functions; otherwise "package not installed" would become a traceback on the script's first line, and
`require_patentkit()`'s friendly hint would never get to run.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Iterable, NoReturn

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_WORKSPACE = 2
EXIT_DEPENDENCY = 3
#: Non-business code: Ctrl+C interruption. POSIX convention 130 = 128 + SIGINT.
EXIT_INTERRUPTED = 130

#: Keep in sync with requires-python in `patentkit/pyproject.toml`
MIN_PYTHON = (3, 11)

#: The dependency check runs only once (main may be called repeatedly in the same process)
_REQUIRED = False


# ── Encoding ─────────────────────────────────────────────────────────


def configure_stdio() -> None:
    """Pin stdout/stderr to UTF-8.

    On Windows, Python encodes output using the console code page (cp936) by default. This package's
    output contains symbols such as `✅/❌/⚠️`, so a plain print raises `UnicodeEncodeError`; when
    captured by a parent process it also becomes mojibake because of the encoding mismatch.
    Reconfiguring the encoding is more reliable than asking users to run `chcp 65001` or set
    `PYTHONIOENCODING` first — the caller should not have to fill this pit.

    `errors="replace"`: if the terminal truly cannot display a symbol, downgrade it to `?` rather
    than crash the whole command.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # replaced by a non-TextIOWrapper stream (e.g. StringIO in tests)
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - extreme cases such as a closed stream
            pass


# ── Dependencies ─────────────────────────────────────────────────────


def require_patentkit(*, as_json: bool = False) -> None:
    """Confirm the Python version and that patentkit is usable; otherwise print fixes and exit 3.

    Check order: Python version first (below 3.11 there is no point even trying to install patentkit),
    then `import patentkit`. Two kinds of ImportError are distinguished:

    * `patentkit` itself is missing — not installed; print the install command;
    * a third-party dependency (e.g. `yaml`) is missing — installed but incomplete; print the
      add-on install command. The previous version always said "patentkit is not installed", so
      users would reinstall it for nothing.
    """
    global _REQUIRED
    if _REQUIRED:
        return

    if sys.version_info < MIN_PYTHON:
        _die(
            f"Python ≥ {MIN_PYTHON[0]}.{MIN_PYTHON[1]} required, "
            f"current version is {platform.python_version()}",
            EXIT_DEPENDENCY,
            as_json=as_json,
            hints=(
                "These skill scripts use 3.11+ syntax (`X | None`, built-in generics)",
                'After upgrading Python, reinstall: pip install -e ".[dev]"',
            ),
        )

    try:
        import patentkit  # noqa: F401  # availability probe only
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing == "patentkit" or missing.startswith("patentkit."):
            _die(
                "The patentkit package was not found",
                EXIT_DEPENDENCY,
                as_json=as_json,
                hints=(
                    'Install from the repo root (containing pyproject.toml): pip install -e ".[dev]"',
                    "Or install the released version: pip install patentkit",
                    "Self-check after installing: python -m patentkit doctor",
                ),
            )
        _die(
            f"patentkit is installed, but the dependency module '{missing}' is missing",
            EXIT_DEPENDENCY,
            as_json=as_json,
            hints=(
                'Complete the dependencies: pip install -e ".[dev]"',
                "See [project] dependencies in the repo-root pyproject.toml for the dependency list",
            ),
        )

    try:
        from patentkit.assessment import PROTOCOL_VERSION
        if PROTOCOL_VERSION != 1:
            raise ImportError("unsupported assessment protocol")
    except ImportError:
        _die(
            "This skill requires patentkit >= 0.5.1 with assessment protocol 1",
            EXIT_DEPENDENCY,
            as_json=as_json,
            hints=("Install the matching patentkit-0.5.1 wheel; old kernels cannot enforce human confirmation for G-S-03",),
        )
    _REQUIRED = True


# ── Workspace ────────────────────────────────────────────────────────


def _workspace_hints() -> tuple[str, ...]:
    """The three fixes for a failed resolution. Fixed order, easy for callers to grep."""
    return (
        "1) cd into the workspace root (the directory containing workspace.yml), then run again",
        "2) add --root <workspace-path> to specify it explicitly",
        "3) set the environment variable PATENTKIT_WORKSPACE=<workspace-path>; afterwards it works from any directory",
    )


def resolve_workspace(explicit: str | None = None, *, as_json: bool = False) -> Path:
    """Locate the workspace root; **exit 2 if not found** (no return, no silent fallback).

    Resolution order matches `patentkit.paths.find_workspace`:

    1. `--root PATH`: explicit. A wrong path is reported directly — **never fall back silently**,
       otherwise the user thinks they are editing workspace A while B is actually used.
    2. environment variable `PATENTKIT_WORKSPACE`: explicit; a wrong value is likewise reported directly.
    3. search upward from the current directory for `workspace.yml` (compatible with older flag combinations).

    This does not simply call `find_workspace()` and stop, because the two contexts "wrong --root" and
    "wrong environment variable" must first be distinguished so the matching fix can be given; passing
    the exception message straight through would point `--root` scenarios in the wrong direction.
    """
    require_patentkit(as_json=as_json)
    from patentkit import paths

    if explicit:
        root = Path(explicit).expanduser()
        if not paths.is_workspace(root):
            _die(
                f"The directory given by --root is not a patentkit workspace: {root}",
                EXIT_WORKSPACE,
                hints=_workspace_hints(),
                as_json=as_json,
            )
        return root.resolve()

    env_value = os.environ.get(paths.ENV_WORKSPACE) or ""
    if env_value:
        root = Path(env_value).expanduser()
        if not paths.is_workspace(root):
            _die(
                f"The directory given by the environment variable {paths.ENV_WORKSPACE} is not a workspace: {env_value}",
                EXIT_WORKSPACE,
                hints=(
                    f"Point it to a directory containing workspace.yml, or clear {paths.ENV_WORKSPACE} to fall back to upward search",
                    *_workspace_hints(),
                ),
                as_json=as_json,
            )
        return root.resolve()

    try:
        return paths.find_workspace()
    except paths.WorkspaceNotFound:
        _die(
            f"No patentkit workspace (workspace.yml) found upward from {Path.cwd()}",
            EXIT_WORKSPACE,
            hints=_workspace_hints(),
            as_json=as_json,
        )


# ── Common arguments and output ──────────────────────────────────────


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add the uniform `--root` / `--json` arguments to a subcommand.

    The help text spells out the resolution order and the JSON contract — many people only read `--help`.
    """
    parser.add_argument(
        "--root",
        metavar="PATH",
        default=None,
        help="workspace root; by default resolved as --root → PATENTKIT_WORKSPACE → upward search for workspace.yml",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output machine-readable JSON only (stdout is exactly one JSON document; human hints go to stderr only)",
    )
    return parser


def emit_json(data: Any) -> None:
    """The **only** permitted stdout output in --json mode.

    `ensure_ascii=False`: output non-ASCII text as-is so logs and manual inspection stay readable;
    `indent=2`: keeps the same shape as the other `--json` outputs of `patentkit`.
    """
    print(json.dumps(data, ensure_ascii=False, indent=2))


def failure(
    message: str,
    code: int = EXIT_FAIL,
    *,
    hints: Iterable[str] = (),
    as_json: bool = False,
) -> int:
    """Uniform failure exit: human hints go to stderr; --json mode emits a structured error to stdout.

    Returns the exit code instead of raising, so `main()` can simply `return _env.failure(...)`;
    places that need to exit immediately use `_die()`.
    """
    hint_list = list(hints)
    if as_json:
        emit_json({"ok": False, "code": code, "error": message, "hints": hint_list})
    else:
        print(f"❌ {message}", file=sys.stderr)
        for hint in hint_list:
            print(f"   · {hint}", file=sys.stderr)
    return code


def _die(
    message: str,
    code: int = EXIT_FAIL,
    *,
    hints: Iterable[str] = (),
    as_json: bool = False,
) -> NoReturn:
    """Like `failure()`, but exits immediately with `SystemExit(code)`."""
    raise SystemExit(failure(message, code, hints=hints, as_json=as_json))


# ── Script entry point ───────────────────────────────────────────────


def run_script(main: Any) -> int:
    """Uniform script entry: lock encoding → run main → collapse unexpected exceptions into an exit code.

    Why catch unexpected exceptions: an LLM client that reads a traceback just pastes the whole thing
    back, drowning the genuinely useful information (which command to re-run, what the exit code is).
    Expected failures (workspace/business) are already handled as 1/2/3 inside each `main()`; anything
    reaching this point is unexpected, so print a one-line summary + self-check command and count it as
    "business failure".

    argparse usage errors (exit 2) and resolve_workspace exits (exit 2) are both `SystemExit` and must
    pass through unchanged; they must not be reclassified.
    """
    configure_stdio()
    try:
        return int(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as exc:  # noqa: BLE001 - see the function docstring: deliberately caught
        print(f"❌ Unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("   · Run python -m patentkit doctor first to self-check", file=sys.stderr)
        print("   · Add --json when a structured error is needed", file=sys.stderr)
        return EXIT_FAIL
