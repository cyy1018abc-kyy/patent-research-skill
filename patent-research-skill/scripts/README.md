# scripts/ —— patentkit 的薄封装

> 规则**不在**这里：数量阈值在 `patentkit/gates.py`，判断合格性在 `patentkit/assessment.py`。
> 本目录只做「参数解析 + 人类可读输出 + 统一退出码」。未安装 patentkit 时所有脚本打印安装指引并
> exit 3。公共层（编码/依赖/工作区定位/JSON 输出）在 `_env.py`。

## 脚本一览

| 脚本 | 用途 | 常用参数 | 退出码 |
|---|---|---|---|
| `status.py` | 目标/门禁/校验/候选分布/下一步 | `--root` `--json` | 0 / 2 / 3 |
| `validate.py` | 一致性校验 V001–V034 | `--strict` `--root` `--json` | 0 过 / 1 不过 |
| `gates.py` | 五门 × 三列验收门 | `--target` `--root` `--json` | 0 全 PASS / 1 未全 PASS |
| `report.py` | 生成对比 run 骨架 | `--target` `--out` `--root` | 0 / 1 / 2 / 3 |
| `check.py` | `validate --strict` + `gates` | `--root` `--json` | 0 / 1 / 2 / 3 |
| `self_test.py` | **安装后自检**：内核/封装/合成样例正反用例/docx 冒烟 | `--json` | 0 / 1 / 3 |
| `export_docx.py` | 导出 .docx 查新报告（需可选依赖 `patentkit[docx]`） | `<TGT>` `--out` | 0 / 1 / 2 / 3 |

**退出码约定**：`0` 成功；`1` 业务失败（校验有错/门未全 PASS/报告写不出）；
`2` 工作区问题（没定位到/`--root` 不对/数据不可解析；argparse 用法错误也是 2）；
`3` 缺依赖（Python < 3.11，或 patentkit / 其依赖 / python-docx 未装）。

> 注：原生 `patentkit gates` 把「未全 PASS」记为 exit 2；脚本层把它归一成 1，
> 让「工作区错误」始终可区分。CI 依赖原生退出码时直接调 `patentkit`。

其余内核能力（`map` / `layout` / `ledger` / `provenance` / `figures` / `deadlines`）
直接用 `python -m patentkit <子命令>` 调用——它们同样读取工作区、遵守统一退出码，
不为每个子命令复制一份封装。

## 工作区定位顺序

与内核一致：`--root` → 环境变量 `PATENTKIT_WORKSPACE` → 向上搜索 `workspace.yml`。
想在任意目录可用：

```powershell
[Environment]::SetEnvironmentVariable("PATENTKIT_WORKSPACE", "<专利工作区>", "User")
```

## 安装后第一件事

```powershell
python <技能目录>/scripts/self_test.py
```

六项检查通过（docx 冒烟可选）说明「内核 + 封装 + 工作区流」安装无误；
不通过时按 FAIL 行的提示修，再跑 `patentkit doctor` 定位。
