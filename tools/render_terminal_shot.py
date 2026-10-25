"""渲染 docs/assets/self-test-terminal.png：安装后自检的"终端截图"。

截图内容不是手贴文本——本脚本**真实运行** `research/scripts/self_test.py` 并把
捕获到的输出渲染成 Windows 终端风格 PNG，数据全部来自安装包自带的合成样例工作区。
输出变化后重跑本脚本即可再生成（脱敏不靠人工挑选，靠 self_test 本身只碰合成数据）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "self-test-terminal.png"

FONT_MONO = Path("C:/Windows/Fonts/consola.ttf")
FONT_CJK = Path("C:/Windows/Fonts/msyh.ttc")
FONT_SYM = Path("C:/Windows/Fonts/seguisym.ttf")  # ⚠ 等符号（Consolas/雅黑缺字形时兜底）

BG = (12, 12, 12)
TITLE_BG = (40, 40, 40)
FG = (204, 204, 204)
GREEN = (23, 156, 60)
YELLOW = (245, 201, 81)
DIM = (150, 150, 150)

CJK_START = 0x2E80  # 该码点以上用中文字体渲染
#: Consolas 缺字形的符号走 seguisym
SYMBOLS = set("⚠✓✗")


def _pick_font(ch: str, font_mono, font_cjk, font_sym):
    if ch in SYMBOLS and font_sym is not None:
        return font_sym
    return font_cjk if ord(ch) >= CJK_START else font_mono


def _run_self_test() -> str:
    proc = subprocess.run([sys.executable, str(ROOT / "research/scripts/self_test.py")],
                          cwd=ROOT, capture_output=True)
    text = (proc.stdout + proc.stderr).decode("utf-8", "replace").rstrip()
    if proc.returncode != 0 or "6/6" not in text:
        raise SystemExit(f"self_test 未通过（rc={proc.returncode}），拒绝渲染失败状态的截图：\n{text}")
    return text


def _render(text: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    scale = 2
    font_mono = ImageFont.truetype(str(FONT_MONO), 15 * scale)
    font_cjk = ImageFont.truetype(str(FONT_CJK), 15 * scale)
    font_sym = ImageFont.truetype(str(FONT_SYM), 15 * scale) if FONT_SYM.exists() else None
    title_font = ImageFont.truetype(str(FONT_CJK), 13 * scale)

    footer = "⚠ 合成样例数据，不含任何真实项目信息 · kernel 0.4.0 / skill 3.2.0"
    lines = text.splitlines() + ["", footer]

    char_w = font_mono.getbbox("M")[2]
    line_h = int(15 * scale * 1.5)
    pad = 16 * scale
    header_h = 30 * scale
    # CJK 字形按两倍等宽占位估宽，避免右侧截断
    def wide(ch: str) -> int:
        return 2 if (ord(ch) >= CJK_START or ch in SYMBOLS) else 1

    units = max(sum(wide(ch) for ch in line) for line in lines)
    width = units * char_w + pad * 2 + 8 * scale
    height = header_h + pad * 2 + line_h * len(lines)

    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, header_h], fill=TITLE_BG)
    draw.text((pad, 8 * scale), "命令提示符 — python research\\scripts\\self_test.py",
              font=title_font, fill=(225, 225, 225))

    def draw_mixed(x: int, y: int, content: str, color):
        for ch in content:
            font = _pick_font(ch, font_mono, font_cjk, font_sym)
            draw.text((x, y), ch, font=font, fill=color)
            x += font.getbbox(ch)[2] - font.getbbox(ch)[0] if (ord(ch) >= CJK_START or ch in SYMBOLS) else char_w
        return x

    for i, line in enumerate(lines):
        y = header_h + pad + i * line_h
        x = pad
        if "[OK  ]" in line:
            head, _, rest = line.partition("[OK  ]")
            x = draw_mixed(x, y, head + "[OK  ]", GREEN)
            draw_mixed(x, y, rest, FG)
        elif line.startswith("⚠"):
            draw_mixed(x, y, line, YELLOW)
        elif line.startswith("结果："):
            draw_mixed(x, y, line, GREEN)
        else:
            draw_mixed(x, y, line, FG if line else DIM)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, "PNG")
    print(f"已生成 {OUT.relative_to(ROOT)}（{image.width}x{image.height}）")


def main() -> int:
    _render(_run_self_test())
    return 0


if __name__ == "__main__":
    sys.exit(main())
