# Patent Research Skill 3.0.1（drafting 英文镜像）

Requires **patentkit 0.3.0, assessment protocol 1**（不变）, Python 3.11+.

## 什么变了（仅文档翻译，无代码/规则变更）

- `patent-drafting` 技能补齐英文镜像：`references.en/` 下 SKILL.en.md、
  00 前置纪律、09 交底、10 权要、11 OA、12 政策雷达、13 改稿闭环（术语与共享
  glossary 一致）；
- `patent-research` 的英文镜像说明与 SKILL.en.md 刷新到 3.x 拆分布局
  （research 侧 08 附图暂仍中文先行）；
- 术语一致性检查升级：drafting 00/09–13 中英配对强制；共享锚定词表扩展到撰写
  词汇（evidence ledger / revision loop / policy radar / office action / response
  draft / disclosure / illustrative example / figure-mark 等）。

## 升级

安装本包覆盖旧目录即可（`--force`）；内核无需升级（0.3.0 不变）；工作区无需迁移。

## Download and install

Download `patent-research-skill-v3.0.1.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.3.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.3.0).
Verify against `SHA256SUMS-skill-v3.0.1.txt`（覆盖两个 zip）。
