#!/usr/bin/env python
"""仓库保密守卫：真实工作区数据不得进入公开仓库（CI 步骤，也是发布前的最后一道闸）。

为什么需要：这个仓库分发的是「方法论 + 工具」，而真实项目的候选清单、检索日志、
稿件（docx）都是未公开申请的衍生内容。发布器（build_skill_release.py）已经校验
**包内**不含 TGT-000[01]/真实公开号；本脚本把同样的纪律扩到**整个仓库**：
真实数据根本不应该出现在仓库目录里，而不是「出现了但没被打进包」。

检查项（任一命中即失败）：
1. 仓库根或技能源码目录下存在 `workspace.yml`（工作区标记 = 混入了工作区）；
2. 存在真实工作区数据目录形态：`0X_*/` 且包含非模板内容（排除 kernel-build 内的
   `patentkit/templates/workspace/` 模板与发布样例 `samples/`）；
3. 任何 `*.docx` / `*.doc` / `*.pptx`（稿件类工作产物；发布器需要时由 CI 构建产物提供）；
4. `02_search_logs` / `03_candidates` 目录出现在技能源码或仓库根（样例合成数据在
   `assets/sample_data/`，不以此形态存在）。

误报处理：确属合成/模板的内容，加进 ALLOWED 前缀表并在 PR 里说明，而不是绕过脚本。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SRC = ROOT / "patent-research-skill"

#: 允许出现工作区形态内容的路径前缀（模板/样例/构建产物）
ALLOWED_PREFIXES = (
    "kernel-build",          # 上游 sdist + 补丁，其中 patentkit/templates/workspace/ 是模板
    "dist",                  # CI 构建产物（含合成样例工作区 samples/）
    "_upstream",             # 上游源码（不提交，但本地存在也不算泄漏）
    ".venv",
)

WORKSPACE_DIR_PREFIXES = (
    "00_", "01_", "02_", "03_", "04_", "05_", "06_", "07_", "08_", "09_",
)

DOC_SUFFIXES = {".docx", ".doc", ".pptx"}


def _allowed(rel: Path) -> bool:
    return rel.parts[0] in ALLOWED_PREFIXES or rel.parts[0].startswith(".")


def main() -> int:
    problems: list[str] = []

    # 1. 工作区标记出现在仓库根/技能源码
    for p in (ROOT / "workspace.yml", SKILL_SRC / "workspace.yml"):
        if p.is_file():
            problems.append(f"工作区标记泄漏：{p.relative_to(ROOT)}")

    # 2/4. 真实工作区数据目录形态
    for base in (ROOT, SKILL_SRC):
        for child in base.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            rel = child.relative_to(ROOT)
            if _allowed(rel):
                continue
            if child.name in {"02_search_logs", "03_candidates", "05_novelty_conclusions", "07_drafting"} or (
                child.name.startswith(WORKSPACE_DIR_PREFIXES) and any(child.iterdir())
            ):
                problems.append(f"疑似工作区数据目录：{rel}")

    # 3. 稿件类文件（任何位置；排除放行前缀）
    for pattern in ("*.docx", "*.doc", "*.pptx"):
        for p in ROOT.rglob(pattern):
            rel = p.relative_to(ROOT)
            if _allowed(rel):
                continue
            problems.append(f"稿件类文件不得入库：{rel}")

    if problems:
        print(f"保密守卫拦截（{len(problems)} 项）——真实项目数据不能出现在公开仓库：")
        for p in problems:
            print(f"  · {p}")
        print("处理：把数据移回私有工作区；确属合成/模板内容则更新 ALLOWED_PREFIXES 并在 PR 说明。")
        return 1
    print("✅ 保密守卫通过：仓库内无工作区标记、无工作区数据目录、无稿件类文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
