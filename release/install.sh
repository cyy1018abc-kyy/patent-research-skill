#!/usr/bin/env bash
# Install / uninstall patent-research-skill (bundled in the release package).
#
# Copy `patent-research/` from the release package into the local AI client's skills directory.
# Directory name = `name` in SKILL.md (clients identify skills by it).
# After installation, a self-check runs against the bundled `samples/sample-workspace/` (requires patentkit).
#
# Exit codes: 0 success; 1 failure (self-check failed / destination exists); 2 invalid release package.
#
# Usage:
#   ./install.sh                          # install into ~/.claude/skills (default)
#   ./install.sh --client both            # install for both Claude Code and Codex CLI
#   ./install.sh --dest /opt/skills       # custom skills root
#   ./install.sh --dry-run                # print actions only; do not write files
#   ./install.sh --uninstall --client both
#   ./install.sh --force                  # overwrite an existing installation
#   ./install.sh --no-self-check          # skip the self-check (debugging)

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
        *) fail "Unknown option: $1 (see --help)" 2 ;;
    esac
done

case "$CLIENT" in
    claude|codex|both) ;;
    *) fail "--client must be claude / codex / both (current: $CLIENT）" 2 ;;
esac

PKG_ROOT=$(cd "$(dirname "$0")" && pwd)
MANIFEST="$PKG_ROOT/manifest.json"
[ -f "$MANIFEST" ] || fail "manifest.json not found - run this script from the extracted release package root (current: $PKG_ROOT）" 2

PYTHON_BIN=""
# Do not rely on `command -v python3`: on Windows Git Bash, python3 is often a Microsoft Store
# placeholder alias (it fails as soon as it runs). Try each candidate and verify 3.11+.
for cand in python3 python; do
    p=$(command -v "$cand" 2>/dev/null || true)
    [ -n "$p" ] || continue
    if "$p" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$p"
        break
    fi
done
[ -n "$PYTHON_BIN" ] || fail "Python >= 3.11 is required (no usable python3/python found). Install Python, then run pip install patentkit" 1

read_manifest() {
    "$PYTHON_BIN" -c '
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for key in sys.argv[2].split("."):
    value = value[key]
print(value)
' "$MANIFEST" "$1"
}

SKILL_NAME=$(read_manifest "skill.name" 2>/dev/null) || fail "Failed to parse manifest.json" 2
SKILL_VERSION=$(read_manifest "skill.version" 2>/dev/null) || fail "Failed to parse manifest.json" 2
INSTALL_DIR_NAME=$(read_manifest "skill.install_dir" 2>/dev/null) || fail "Failed to parse manifest.json" 2
[ -n "$SKILL_NAME" ] && [ -n "$INSTALL_DIR_NAME" ] || fail "manifest.json is missing skill.name / skill.install_dir" 2
[ "$INSTALL_DIR_NAME" = "$SKILL_NAME" ] || fail "Inconsistent manifest: install_dir must equal name" 2

PAYLOAD="$PKG_ROOT/$INSTALL_DIR_NAME"
SAMPLE_ROOT="$PKG_ROOT/samples/sample-workspace"

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
echo "Skill name: $SKILL_NAME(install directory must match)"
echo "Targets  : ${ROOTS[*]}"
[ "$DRY_RUN" -eq 1 ] && echo "Mode     : DRY-RUN (no files changed)"
echo ""

if [ "$UNINSTALL" -eq 1 ]; then
    removed=0
    for root in "${ROOTS[@]}"; do
        target="$root/$INSTALL_DIR_NAME"
        if [ ! -e "$target" ]; then
            note "Not installed: $target"
            continue
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
            note "[dry-run] would remove: $target"
            continue
        fi
        rm -rf "$target"
        echo "OK, uninstalled: $target"
        removed=$((removed + 1))
    done
    if [ "$DRY_RUN" -eq 1 ]; then
        note "Dry-run finished: no files were deleted"
    elif [ "$removed" -eq 0 ]; then
        note "No installed skill package found (try another --client / --dest)"
    fi
    exit 0
fi

[ -d "$PAYLOAD" ] || fail "Release package is missing the payload directory: $INSTALL_DIR_NAME (the zip may not be fully extracted)" 2

for root in "${ROOTS[@]}"; do
    target="$root/$INSTALL_DIR_NAME"

    if [ -e "$target" ]; then
        if [ "$FORCE" -ne 1 ]; then
            fail "Destination already exists: $target
  Upgrade: run --uninstall then install; or add --force to overwrite."
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
    echo "OK, installed: $target"
done

if [ "$DRY_RUN" -eq 1 ]; then
    note "Dry-run finished: no files were written"
    exit 0
fi

if [ "$NO_SELF_CHECK" -ne 1 ]; then
    PROBE="${ROOTS[0]}/$INSTALL_DIR_NAME"
    echo ""
    echo "Self-check (using the bundled sample workspace, no real data)..."
    if [ -d "$SAMPLE_ROOT" ]; then
        "$PYTHON_BIN" "$PROBE/scripts/status.py" --root "$SAMPLE_ROOT" --json >/dev/null
    else
        "$PYTHON_BIN" -c 'import patentkit' >/dev/null
    fi
    if [ $? -ne 0 ]; then
        fail "Self-check failed. Most likely the patentkit kernel is missing: pip install patentkit"
    fi
    echo "OK: the scripts can locate the workspace and compute status"
fi

echo ""
echo "Next steps:"
echo "  1) In the client, ask: "run a patent novelty check" or "show workspace status""
echo "  2) No workspace yet? python -m patentkit init <dir> --target TGT-0002 --title <title>"
echo "  3) With a real workspace, the skill uses PATENTKIT_WORKSPACE or searches upward for workspace.yml"
exit 0
