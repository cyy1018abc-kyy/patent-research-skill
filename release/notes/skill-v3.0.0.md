# Patent Research Skill 3.0.0（多技能矩阵拆分）

Requires **patentkit 0.3.0, assessment protocol 1**（与本版不变，无需升级内核）, Python 3.11+.

## 什么变了

按已接受的拆分决策（docs/skill-matrix-plan.md，2026-10-25），单技能拆为两个、
同仓同包发布：

| 技能 | 覆盖 | references |
|---|---|---|
| `patent-research` | 检索/查新/证据链/验收门/交付物（docx/HTML/账本/布局） | 01–08 + glossary |
| `patent-drafting` | 交底书、权利要求与说明书、OA 答复（已并入）、多轮改稿闭环 | 00 前置摘要 + 09–13 + glossary |

- **全量包** `patent-research-skill-v3.0.0.zip`：一次安装两个技能（含合成样例工作区）；
- **单技能包** `patent-drafting-skill-v3.0.0.zip`：仅 drafting，可独立安装（无样例，
  安装自检自动降级为 SKILL.md 就位检查）；
- 安装器按 manifest（schema 2）的 skills 列表安装/升级/卸载全部载荷目录；
- `patent-drafting` 不带脚本封装，直接调 `python -m patentkit <子命令>`——规则只在内核一份；
  其 `references/00-prerequisites.md` 自包含地摘要了检索侧纪律（证据三级/五门/判断合格性）；
- 两份 glossary 副本由 CI 强制逐字节一致；evals 扩到 20 例并按技能锚定触发短语。

## 升级与迁移

- 从 2.5.0 升级：安装新包（`--force` 覆盖），得到 `patent-research/` + 新增的
  `patent-drafting/` 两个目录；旧 `patent-research/` 被替换。工作区数据不受影响，
  内核无需升级（0.3.0 不变）。
- 旧版卸载：安装器 `-Uninstall` 会移除清单内的全部技能目录。

## Download and install

Download `patent-research-skill-v3.0.0.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.3.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.3.0).
Keep these three files in the same directory. On Windows, double-click the CMD file;
manual PowerShell and POSIX instructions are in `INSTALL-colleagues.md`.
Verify against `SHA256SUMS-skill-v3.0.0.txt`（覆盖两个 zip）。

## 2.5.0 的既有能力（全部保留）

中文主文档 + references.en 镜像（术语 CI 锁定）、内核 0.3.0 交付安全层
（export-docx / map / layout / ledger / provenance / figures / deadlines、V031–V034）、
evals 触发评测、保密守卫、self_test 安装自检。逐项证据见
`docs/2026-10-25-iteration-report.md`。
