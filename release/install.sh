#!/usr/bin/env bash
# Install / uninstall patent-research-skill (bundled with the release package).
#
# Copies `patent-research/` from the release package into the local AI client's skills directory;
# the directory name = the `name` in SKILL.md (clients identify the skill by it).
# After installation it self-checks against the package's `samples/sample_workspace/` by default (requires patentkit installed).
#
# Exit codes: 0 success; 1 failure (self-check failed / target already exists, etc.); 2 release package structure incomplete.
#
# Usage:
#   ./install.sh                          # install to ~/.claude/skills (default)
#   ./install.sh --client both            # install into both Claude Code + Codex CLI
#   ./install.sh --dest /opt/skills       # custom skills root
#   ./install.sh --dry-run                # print only, write no files
#   ./install.sh --uninstall --client both
#   ./install.sh --force                  # overwrite an existing older version
#   ./install.sh --no-self-check          # skip the self-check (for debugging)

set -u

CLIENT=claude
DEST=""
UNINSTALL=0
DRY_RUN=0
NO_SELF_CHECK=0
FORCE=0

usage() {
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

fail() {
    # $1 = message; $2 = exit code (default 1)
    printf '❌ %s\n' "$1" >&2
    exit "${2:-1}"
}

note() { printf '  · %s\n' "$1"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --client)
            [ $# -ge 2 ] || fail "--client requires a value (claude/codex/both)" 2
            CLIENT=$2
            shift 2
            ;;
        --client=*) CLIENT=${1#*=}; shift ;;
        --dest)
            [ $# -ge 2 ] || fail "--dest requires a directory path" 2
            DEST=$2
            shift 2
            ;;
        --dest=*) DEST=${1#*=}; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --no-self-check) NO_SELF_CHECK=1; shift ;;
        --force) FORCE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "unknown argument: $1 (see --help for usage)" 2 ;;
    esac
done

case "$CLIENT" in
    claude|codex|both) ;;
    *) fail "--client must be claude / codex / both (current: $CLIENT)" 2 ;;
esac

PKG_ROOT=$(cd "$(dirname "$0")" && pwd)
MANIFEST="$PKG_ROOT/manifest.json"
[ -f "$MANIFEST" ] || fail "manifest.json not found — please run this script from the root of the unzipped release package (current: $PKG_ROOT)" 2

PYTHON_BIN=""
# Don't rely only on `command -v python3`: on Windows Git Bash python3 is often the Microsoft Store
# placeholder alias (fails as soon as it runs). Here each candidate is actually executed once, and 3.11+ is verified.
for cand in python3 python; do
    p=$(command -v "$cand" 2>/dev/null || true)
    [ -n "$p" ] || continue
    if "$p" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$p"
        break
    fi
done
[ -n "$PYTHON_BIN" ] || fail "Python ≥ 3.11 is required (no usable python3/python found). Once installed, run pip install patentkit" 1

read_manifest() {
    "$PYTHON_BIN" -c '
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for key in sys.argv[2].split("."):
    value = value[key]
print(value)
' "$MANIFEST" "$1"
}

SKILL_NAME=$(read_manifest "skill.name" 2>/dev/null) || fail "failed to parse manifest.json" 2
SKILL_VERSION=$(read_manifest "skill.version" 2>/dev/null) || fail "failed to parse manifest.json" 2
INSTALL_DIR_NAME=$(read_manifest "skill.install_dir" 2>/dev/null) || fail "failed to parse manifest.json" 2
[ -n "$SKILL_NAME" ] && [ -n "$INSTALL_DIR_NAME" ] || fail "manifest.json is missing skill.name / skill.install_dir" 2
[ "$INSTALL_DIR_NAME" = "$SKILL_NAME" ] || fail "manifest is self-contradictory: install_dir must equal name" 2

PAYLOAD="$PKG_ROOT/$INSTALL_DIR_NAME"
SAMPLE_ROOT="$PKG_ROOT/samples/sample_workspace"

if [ -n "$DEST" ]; then
    ROOTS=("$DEST")
else
    case "$CLIENT" in
        claude) ROOTS=("$HOME/.claude/skills") ;;
        codex) ROOTS=("$HOME/.agents/skills") ;;
        both) ROOTS=("$HOME/.claude/skills" "$HOME/.agents/skills") ;;
    esac
fi

MODE="Install"
[ "$UNINSTALL" -eq 1 ] && MODE="Uninstall"
echo ""
echo "patent-research-skill v$SKILL_VERSION  ·  $MODE"
echo "Skill name : $SKILL_NAME (the install directory name must match)"
echo "Targets    : ${ROOTS[*]}"
[ "$DRY_RUN" -eq 1 ] && echo "Mode       : DRY-RUN (no files are changed)"
echo ""

if [ "$UNINSTALL" -eq 1 ]; then
    removed=0
    for root in "${ROOTS[@]}"; do
        target="$root/$INSTALL_DIR_NAME"
        if [ ! -e "$target" ]; then
            note "not installed: $target"
            continue
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
            note "[dry-run] would delete: $target"
            continue
        fi
        rm -rf "$target"
        echo "✅ Uninstalled: $target"
        removed=$((removed + 1))
    done
    if [ "$DRY_RUN" -eq 1 ]; then
        note "dry-run finished: no files deleted"
    elif [ "$removed" -eq 0 ]; then
        note "no installed skill package found (try a different --client / --dest)"
    fi
    exit 0
fi

[ -d "$PAYLOAD" ] || fail "release package is missing the payload directory: $INSTALL_DIR_NAME (the zip may not have been fully extracted)" 2

for root in "${ROOTS[@]}"; do
    target="$root/$INSTALL_DIR_NAME"

    if [ -e "$target" ]; then
        if [ "$FORCE" -ne 1 ]; then
            fail "target already exists: $target
  Upgrade: run --uninstall first and then install; or add --force to overwrite it."
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
            note "[dry-run] would overwrite: $target"
        else
            rm -rf "$target"
        fi
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        note "[dry-run] would copy: $PAYLOAD  ->  $target"
        continue
    fi

    mkdir -p "$root"
    cp -R "$PAYLOAD" "$target"
    echo "✅ Installed: $target"
done

if [ "$DRY_RUN" -eq 1 ]; then
    note "dry-run finished: no files written"
    exit 0
fi

if [ "$NO_SELF_CHECK" -ne 1 ]; then
    PROBE="${ROOTS[0]}/$INSTALL_DIR_NAME"
    echo ""
    echo "Self-check (using the package's sample workspace; no real data touched)..."
    if [ -d "$SAMPLE_ROOT" ]; then
        "$PYTHON_BIN" "$PROBE/scripts/status.py" --root "$SAMPLE_ROOT" --json >/dev/null
    else
        "$PYTHON_BIN" -c 'import patentkit' >/dev/null
    fi
    if [ $? -ne 0 ]; then
        fail "self-check failed. Most likely the patentkit core is not installed: pip install patentkit"
    fi
    echo "✅ Self-check passed: the scripts can locate the workspace and compute the status"
fi

echo ""
echo "Next steps:"
echo "  1) In the client, say 'run a patent novelty check' or 'show the workspace status'"
echo "  2) No workspace yet? python -m patentkit init <dir> --target TGT-0002 --title <title>"
echo "  3) With a real workspace, the skill uses PATENTKIT_WORKSPACE or walks up from the current directory to find workspace.yml"
exit 0
