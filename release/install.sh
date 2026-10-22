#!/usr/bin/env bash
# 安装 / 卸载 patent-research-skill（发布包内自带）。
#
# 把发布包里的 `patent-research/` 复制到本地 AI 客户端技能目录；
# 目录名 = SKILL.md 的 name（客户端按这个识别技能）。
# 安装后默认用包内 `samples/示例工作区/` 跑一次自检（需要已安装 patentkit）。
#
# 退出码：0 成功；1 失败（自检不过/目标已存在等）；2 发布包结构不完整。
#
# 用法：
#   ./install.sh                          # 装到 ~/.claude/skills（默认）
#   ./install.sh --client both            # Claude Code + Codex CLI 都装
#   ./install.sh --dest /opt/skills       # 自定义技能根目录
#   ./install.sh --dry-run                # 只打印，不写文件
#   ./install.sh --uninstall --client both
#   ./install.sh --force                  # 覆盖已存在的旧版本
#   ./install.sh --no-self-check          # 跳过自检（调试用）

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
    # $1 = 消息；$2 = 退出码（默认 1）
    printf '❌ %s\n' "$1" >&2
    exit "${2:-1}"
}

note() { printf '  · %s\n' "$1"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --client)
            [ $# -ge 2 ] || fail "--client 需要取值（claude/codex/both）" 2
            CLIENT=$2
            shift 2
            ;;
        --client=*) CLIENT=${1#*=}; shift ;;
        --dest)
            [ $# -ge 2 ] || fail "--dest 需要目录路径" 2
            DEST=$2
            shift 2
            ;;
        --dest=*) DEST=${1#*=}; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --no-self-check) NO_SELF_CHECK=1; shift ;;
        --force) FORCE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "未知参数：$1（--help 看用法）" 2 ;;
    esac
done

case "$CLIENT" in
    claude|codex|both) ;;
    *) fail "--client 只能是 claude / codex / both（当前：$CLIENT）" 2 ;;
esac

PKG_ROOT=$(cd "$(dirname "$0")" && pwd)
MANIFEST="$PKG_ROOT/manifest.json"
[ -f "$MANIFEST" ] || fail "找不到 manifest.json —— 请在解压后的发布包根目录运行本脚本（当前：$PKG_ROOT）" 2

PYTHON_BIN=""
# 不能只靠 `command -v python3`：Windows Git Bash 里 python3 常是 Microsoft Store
# 的占位 alias（一执行就失败）。这里逐个候选实际跑一次，并校验 3.11+。
for cand in python3 python; do
    p=$(command -v "$cand" 2>/dev/null || true)
    [ -n "$p" ] || continue
    if "$p" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$p"
        break
    fi
done
[ -n "$PYTHON_BIN" ] || fail "需要 Python ≥ 3.11（没找到可用的 python3/python）。装好后执行 pip install patentkit" 1

read_manifest() {
    "$PYTHON_BIN" -c '
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for key in sys.argv[2].split("."):
    value = value[key]
print(value)
' "$MANIFEST" "$1"
}

SKILL_NAME=$(read_manifest "skill.name" 2>/dev/null) || fail "manifest.json 解析失败" 2
SKILL_VERSION=$(read_manifest "skill.version" 2>/dev/null) || fail "manifest.json 解析失败" 2
INSTALL_DIR_NAME=$(read_manifest "skill.install_dir" 2>/dev/null) || fail "manifest.json 解析失败" 2
[ -n "$SKILL_NAME" ] && [ -n "$INSTALL_DIR_NAME" ] || fail "manifest.json 缺 skill.name / skill.install_dir" 2
[ "$INSTALL_DIR_NAME" = "$SKILL_NAME" ] || fail "manifest 自相矛盾：install_dir 必须等于 name" 2

PAYLOAD="$PKG_ROOT/$INSTALL_DIR_NAME"
SAMPLE_ROOT="$PKG_ROOT/samples/示例工作区"

if [ -n "$DEST" ]; then
    ROOTS=("$DEST")
else
    case "$CLIENT" in
        claude) ROOTS=("$HOME/.claude/skills") ;;
        codex) ROOTS=("$HOME/.agents/skills") ;;
        both) ROOTS=("$HOME/.claude/skills" "$HOME/.agents/skills") ;;
    esac
fi

MODE="安装"
[ "$UNINSTALL" -eq 1 ] && MODE="卸载"
echo ""
echo "patent-research-skill v$SKILL_VERSION  ·  $MODE"
echo "技能名   : $SKILL_NAME（安装目录名必须一致）"
echo "目标位置 : ${ROOTS[*]}"
[ "$DRY_RUN" -eq 1 ] && echo "模式     : DRY-RUN（不改任何文件）"
echo ""

if [ "$UNINSTALL" -eq 1 ]; then
    removed=0
    for root in "${ROOTS[@]}"; do
        target="$root/$INSTALL_DIR_NAME"
        if [ ! -e "$target" ]; then
            note "未安装：$target"
            continue
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
            note "[dry-run] 将删除：$target"
            continue
        fi
        rm -rf "$target"
        echo "✅ 已卸载：$target"
        removed=$((removed + 1))
    done
    if [ "$DRY_RUN" -eq 1 ]; then
        note "dry-run 结束：没有删除任何文件"
    elif [ "$removed" -eq 0 ]; then
        note "没有找到已安装的技能包（换 --client / --dest 再试）"
    fi
    exit 0
fi

[ -d "$PAYLOAD" ] || fail "发布包缺 payload 目录：$INSTALL_DIR_NAME（zip 可能没解压完整）" 2

for root in "${ROOTS[@]}"; do
    target="$root/$INSTALL_DIR_NAME"

    if [ -e "$target" ]; then
        if [ "$FORCE" -ne 1 ]; then
            fail "目标已存在：$target
  升级：先 --uninstall 再安装；或加 --force 直接覆盖。"
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
            note "[dry-run] 将覆盖：$target"
        else
            rm -rf "$target"
        fi
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        note "[dry-run] 将复制：$PAYLOAD  ->  $target"
        continue
    fi

    mkdir -p "$root"
    cp -R "$PAYLOAD" "$target"
    echo "✅ 已安装：$target"
done

if [ "$DRY_RUN" -eq 1 ]; then
    note "dry-run 结束：没有写入任何文件"
    exit 0
fi

if [ "$NO_SELF_CHECK" -ne 1 ]; then
    PROBE="${ROOTS[0]}/$INSTALL_DIR_NAME"
    echo ""
    echo "自检（用包内示例工作区，不接触真实数据）..."
    if [ -d "$SAMPLE_ROOT" ]; then
        "$PYTHON_BIN" "$PROBE/scripts/status.py" --root "$SAMPLE_ROOT" --json >/dev/null
    else
        "$PYTHON_BIN" -c 'import patentkit' >/dev/null
    fi
    if [ $? -ne 0 ]; then
        fail "自检失败。多半是没装 patentkit 内核：pip install patentkit"
    fi
    echo "✅ 自检通过：脚本能定位工作区并算出状态"
fi

echo ""
echo "下一步："
echo "  1) 在客户端里说「跑一遍专利新颖性核查」或「看看工作区状态」"
echo "  2) 工作区还没有？python -m patentkit init <目录> --target TGT-0002 --title <名称>"
echo "  3) 用真实工作区时，技能会用 PATENTKIT_WORKSPACE 或从当前目录向上找 workspace.yml"
exit 0
