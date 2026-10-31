#!/usr/bin/env bash
# Install / uninstall the patent skills bundled with the release package (multi-skill).
#
# 按 manifest.json 的 skills 列表，把每个技能目录（patent-research/、patent-drafting/…）
# 复制到本地 AI 客户端的技能目录；目录名 = SKILL.md 的 name（客户端按它识别技能）。
# 安装后默认对包内 samples/sample_workspace/ 自检（需要 patentkit；单技能包无样例时，
# 自检降级为「SKILL.md 就位」检查）。
#
# Exit codes: 0 success; 1 failure (self-check failed / target already exists, etc.); 2 release package structure incomplete.
#
# Usage:
#   ./install.sh                          # install to ~/.claude/skills (default)
#   ./install.sh --client both            # install into both Claude Code + Codex CLI
#   ./install.sh --dest /opt/skills       # custom skills root
#   ./install.sh --dry-run                # print only, write no files
#   ./install.sh --uninstall --client both
#   ./install.sh --force                  # overwrite existing older versions
#   ./install.sh --no-self-check          # skip the self-check (for debugging)

set -u

CLIENT=claude
DEST=""
UNINSTALL=0
DRY_RUN=0
NO_SELF_CHECK=0
FORCE=0

usage() {
    sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
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

# skills 列表：每行 "install_dir"；并校验 install_dir == name 且属于受支持集合
SKILL_ROWS=$("$PYTHON_BIN" -c '
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
skills = data.get("skills")
if data.get("schema_version") != 2 or not isinstance(skills, list) or not skills:
    raise SystemExit("manifest.json must be schema 2 with a non-empty skills list")
for s in skills:
    if s.get("install_dir") != s.get("name") or s["name"] not in {"patent-research", "patent-drafting", "patent-discovery"}:
        raise SystemExit(f"unsupported skill entry: {s}")
print(" ".join(s["name"] for s in skills))
print(skills[0]["version"])
' "$MANIFEST" 2>&1) || fail "failed to parse manifest.json: $SKILL_ROWS" 2
SKILL_DIRS=$(printf '%s\n' "$SKILL_ROWS" | sed -n 1p)
SKILL_VERSION=$(printf '%s\n' "$SKILL_ROWS" | sed -n 2p)
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
echo "patent-research-skill v$SKILL_VERSION  ·  $MODE（multi-skill）"
echo "Skills     : $SKILL_DIRS"
echo "Targets    : ${ROOTS[*]}"
[ "$DRY_RUN" -eq 1 ] && echo "Mode       : DRY-RUN (no files are changed)"
echo ""

if [ "$UNINSTALL" -eq 1 ]; then
    removed=0
    for root in "${ROOTS[@]}"; do
        for dir in $SKILL_DIRS; do
            target="$root/$dir"
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
    done
    if [ "$DRY_RUN" -eq 1 ]; then
        note "dry-run finished: no files deleted"
    elif [ "$removed" -eq 0 ]; then
        note "no installed skill package found (try a different --client / --dest)"
    fi
    exit 0
fi

for dir in $SKILL_DIRS; do
    [ -d "$PKG_ROOT/$dir" ] || fail "release package is missing the payload directory: $dir (the zip may not have been fully extracted)" 2
done

if [ "$DRY_RUN" -eq 0 ] && [ "$NO_SELF_CHECK" -eq 0 ]; then
    "$PYTHON_BIN" -c 'from patentkit.assessment import PROTOCOL_VERSION; assert PROTOCOL_VERSION == 1' || fail "Install the patentkit 0.10.0 wheel before replacing the skill"
fi

for root in "${ROOTS[@]}"; do
    for dir in $SKILL_DIRS; do
        payload="$PKG_ROOT/$dir"
        target="$root/$dir"

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
            note "[dry-run] would copy: $payload  ->  $target"
            continue
        fi

        mkdir -p "$root"
        cp -R "$payload" "$target"
        echo "✅ Installed: $target"
    done
done

if [ "$DRY_RUN" -eq 1 ]; then
    note "dry-run finished: no files written"
    exit 0
fi

if [ "$NO_SELF_CHECK" -ne 1 ]; then
    echo ""
    echo "Self-check (no real data touched)..."
    if [ -d "$SAMPLE_ROOT" ]; then
        probe="${ROOTS[0]}/patent-research"
        "$PYTHON_BIN" "$probe/scripts/status.py" --root "$SAMPLE_ROOT" --json >/dev/null ||
            fail "self-check failed. Install the matching patentkit 0.10.0 wheel and retry"
        echo "✅ Self-check passed: status.py located the sample workspace and computed the status"
    else
        # 单技能包（无样例）：退化为就位检查
        for dir in $SKILL_DIRS; do
            [ -f "${ROOTS[0]}/$dir/SKILL.md" ] || fail "self-check failed: ${ROOTS[0]}/$dir/SKILL.md missing"
        done
        echo "✅ Self-check passed: SKILL.md in place for $SKILL_DIRS (no sample workspace in this package)"
    fi
fi

echo ""
echo "Next steps:"
echo "  1) In the client, say 'run a patent novelty check' or 'show the workspace status' (patent-research)"
echo "  2) Drafting/OA work: 'draft a disclosure from the search results' (patent-drafting)"
echo "  3) No workspace yet? python -m patentkit init <dir> --target TGT-0002 --title <title>"
echo "  4) With a real workspace, the skill uses PATENTKIT_WORKSPACE or walks up from the current directory to find workspace.yml"
exit 0
