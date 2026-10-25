#!/usr/bin/env python3
"""Check relative links inside every skill payload (repo tree or unpacked release zip).

Why this exists
---------------
After the dual-skill split (3.0.0), reference files moved between `research/` and
`drafting/`. Links that were correct inside the old single skill kept pointing at
old locations — in the repo they may resolve via `../` into a sibling skill, but an
installed user receives ONE skill directory, so any link escaping its own skill
root is broken in the installed experience even when it works in the repo.

Scope rules
-----------
* A "skill root" is any directory containing `SKILL.md` or `SKILL.en.md`.
* Only files inside a skill root are checked (repo-only files like README/docs are
  not part of any installed payload).
* Every relative link in a checked file must resolve to an existing file **inside
  the same skill root**. Links escaping the root (`../`) are reported even when
  they resolve on disk — cross-skill navigation must go through the documented
  skill handoff, not file links.
* Absolute URLs (http/https/mailto) and pure `#anchors` are ignored.

Usage
-----
    python tools/check_reference_links.py [--root PATH] [--quiet]

`--root` defaults to the repository root; point it at an unpacked release zip to
verify the packaged experience (CI does both). Exit 0 = all links resolve,
exit 1 = at least one broken link, exit 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?([^)<>\s]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "ftp://")


def strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks so inline examples are not scanned as links."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None:
            out.append(line)
    return "\n".join(out)


def skill_roots(root: Path) -> dict[Path, str]:
    """Map skill-root dir -> display name.

    A payload root is a directory containing the (Chinese, authoritative) `SKILL.md`.
    `SKILL.en.md` mirrors that live in `references.en/` are payload *members*, not roots —
    they ship inside the same payload and are checked against the enclosing root.
    """
    roots: dict[Path, str] = {}
    for marker in sorted(root.rglob("SKILL.md")):
        roots[marker.parent.resolve()] = marker.parent.name
    return roots


def check(root: Path) -> list[str]:
    problems: list[str] = []
    roots = skill_roots(root)
    if not roots:
        return [f"no skill payload found under {root} (no SKILL.md / SKILL.en.md)"]
    for skill_root in sorted(roots):
        name = roots[skill_root]
        for md in sorted(skill_root.rglob("*.md")):
            try:
                text = strip_code_blocks(md.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                problems.append(f"{name}/{md.relative_to(skill_root).as_posix()}: unreadable ({exc})")
                continue
            for m in LINK_RE.finditer(text):
                target = m.group(1).strip()
                if not target or target.startswith(("#",) + SKIP_SCHEMES):
                    continue
                if "<" in target or ">" in target or " " in target:
                    problems.append(f"{name}/{md.relative_to(skill_root).as_posix()}: malformed link target '{target}'")
                    continue
                resolved = (md.parent / target).resolve()
                try:
                    rel = resolved.relative_to(skill_root)
                except ValueError:
                    problems.append(
                        f"{name}/{md.relative_to(skill_root).as_posix()}: link '{target}' escapes the "
                        f"skill payload (installed users cannot reach it; use the documented skill handoff)")
                    continue
                if not resolved.is_file():
                    problems.append(
                        f"{name}/{md.relative_to(skill_root).as_posix()}: broken link '{target}' "
                        f"(→ {rel.as_posix()} missing)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                    help="repo root or unpacked release directory (default: repo root)")
    ap.add_argument("--quiet", action="store_true", help="only print the summary line")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"[FATAL] root is not a directory: {root}", file=sys.stderr)
        return 2
    problems = check(root)
    if problems:
        for p in problems:
            print(f"  ✗ {p}")
        print(f"[FAIL] {len(problems)} broken link(s) under {root}")
        return 1
    if not args.quiet:
        print(f"[OK] all relative links resolve inside their skill payload ({root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
