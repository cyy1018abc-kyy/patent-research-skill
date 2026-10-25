# Patent Research Skill 2.5.0

Requires **patentkit 0.3.0, assessment protocol 1**, Python 3.11+
(`pip install python-docx` additionally enables the docx export).

本版是「中文主版本 + 交付安全层」的合并发布（对应升级清单 P0+P1+P2，
原计划的 2.5/2.6/2.7/2.8 节奏合并为一轮验证）。逐项证据见仓库
`docs/2026-10-25-iteration-report.md`。

## 中文主版本（Chinese-primary runtime）

- `SKILL.md`、13 篇 `references/`（新增 08 附图 / 09 交底与申请文件 / 10 权利要求 /
  11 OA 答复 / 12 政策雷达 / 13 改稿闭环）与资产模板均为**中文权威版**；
  英文镜像在 `references.en/`（01–07 双侧维护），中英术语由 `references/glossary.md`
  统一、CI（`evals/check_terminology.py`）锁定一致性。
- 新增硬约束 9（结论只能引用证据账本内的编号，V034）与 10（数值声明必须 A/B/C 溯源，
  V031/V032 fail-closed）。

## 交付安全层（内核 0.3.0）

- `patentkit export-docx`：把工作区状态导出为可编辑 .docx 查新报告，数字零手工转写，
  三层级判定留显式人工占位（可选依赖 `patentkit[docx]`）。
- `patentkit map / layout / ledger`：离线自包含 HTML 总览、跨目标 1+N 组合视图、
  证据账本（结论引用受 V034 拦截）。
- `patentkit provenance scan/check`：数值声明 A/B/C 溯源登记，无来源即 error。
- `patentkit figures check/draw`：附图标记双向一致性（V033 warn）与确定性 SVG 框图。
- `patentkit deadlines`：提交后期限台账（以官方发文为准，缺基础信息拒绝计算）。
- `scripts/self_test.py`：安装后六项自检（含「空样例必须不过门禁」反用例）。

## 质量工程（CI 新步骤）

- `evals/`：14 组触发/边界/拒绝/格式用例；触发短语逐字锚定 `SKILL.md` description。
- `tools/check_no_workspace_data.py` 保密守卫 + `.gitignore` 保密红线。
- 内核补丁 `release/patches/patentkit-0.1.2-to-0.3.0.patch`（取代 to-0.2.0，后者保留存档）；
  重建的 `tests/conftest.py` 让 CI 跑全量内核套件（503 项）而非仅 31 项回归。

## Download and install

Download `patent-research-skill-v2.5.0.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.3.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.3.0).
Keep these three files in the same directory. On Windows, double-click the CMD file;
manual PowerShell and POSIX instructions are in `INSTALL-colleagues.md`.
Use only this version pair. Verify the downloads against `SHA256SUMS-skill-v2.5.0.txt`
and the kernel's checksum file.

## Upgrade an existing workspace

Back up the workspace first, then install the new kernel and skill. The installers
replace only the skill directory; they do not migrate research data automatically.
Assessment data from 2.4.0 needs no migration (protocol unchanged, version 1);
run `python scripts/self_test.py` after upgrading to confirm the environment.
