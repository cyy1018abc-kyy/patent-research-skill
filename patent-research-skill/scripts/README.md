# scripts/ —— 技能包的本地执行脚本

> **一句话**：把 patentkit 的校验 / 门禁 / 报告能力包成**可重复执行、对 LLM 客户端友好**的命令。
> 只做「定位工作区 + 调用 API + 呈现 + 收敛错误码」，**不复制任何规则**。

## 为什么要有这一层

| 场景 | 直接跑 `patentkit` | 跑 `scripts/` |
|---|---|---|
| Windows 中文终端 | 输出 ✅/⚠️ 可能 `UnicodeEncodeError` 崩掉 | 脚本启动即锁定 UTF-8 |
| 客户端没装包 / 没 cd 对 | 一屏 traceback；或报「术语表不存在」误导人 | exit 3 给安装命令；exit 2 给三条修法 |
| 机器解析输出 | 人类文本与 JSON 混着来 | `--json` 时 stdout **只有一个 JSON** |
| 退出码 | gates 失败返回 2，和工作区错误撞码 | 统一：1 = 业务失败，2 = 工作区问题 |

**这是薄封装，不是替代。** 规则与阈值的唯一实现仍在 `patentkit/`：

| 能力 | 唯一实现位置 |
|---|---|
| 程序化入口（本目录全部命令只调它） | `patentkit/api.py` |
| 一致性校验 V001-V028 | `patentkit/validate.py` |
| 验收门 G-S-01..05 | `patentkit/gates.py` |
| 对比 run 骨架 | `patentkit/report.py` |

## 依赖

| 依赖 | 要求 | 怎么查 / 怎么装 |
|---|---|---|
| Python | ≥ 3.11 | `python --version`；低于此版本脚本 exit 3 |
| patentkit | 已安装（可编辑安装即可） | `pip install -e ".[dev]"`；或 `pip install patentkit` |
| 自检 | 工作区可解析、依赖齐全 | `python -m patentkit doctor` |

> 没装 patentkit 时脚本**不会**抛 traceback，而是提示安装方式并以 exit 3 退出。

## 快速开始（PowerShell）

```powershell
# 在仓库根运行。工作区定位顺序：--root → PATENTKIT_WORKSPACE → 向上找 workspace.yml
python patent-research-skill/scripts/status.py

# 机器可读（LLM 客户端推荐）
python patent-research-skill/scripts/status.py --json

# 在任意目录指定工作区
python patent-research-skill/scripts/gates.py --root <patent-workspace>

# CI 口径：数据一致性 + 五门全 PASS 一起看
python patent-research-skill/scripts/check.py --json
```

## 命令一览

| 脚本 | 干什么 | 调用的 API | 退出码 |
|---|---|---|---|
| `status.py` | 目标 / 五门一行汇总 / 校验 / 候选分布 / 下一步 hints | `api.status` | 0 数据可读（门是否 PASS 不影响本命令） |
| `validate.py` | V001-V028 一致性校验；`--strict` 时 warn 也算失败 | `api.validate` | 0 通过 / 1 有阻断项 |
| `gates.py` | 五门 × 三列摘要；**PASS 只认 verified 列** | `api.gates` | 0 五门全 PASS / 1 有门未过（含 N/A） |
| `report.py` | 生成 `04_对比分析/runs/` 的对比 run 骨架 | `api.report` | 0 成功 / 1 生成或写盘失败 |
| `check.py` | `validate --strict` + `gates`（提交前 / CI 入口） | 上面两个 | 0 全过 / 1 任一失败 |
| `_env.py` | 共用层：UTF-8、依赖检查、工作区定位、JSON 输出 | —（被上面 5 个 import） | — |

五个命令都支持 `--root PATH` 与 `--json`。

### 公共参数

| 参数 | 作用 |
|---|---|
| `--root PATH` | 显式指定工作区根；相对路径按**当前目录**解析 |
| `--json` | stdout 只输出一个 JSON 文档（`ensure_ascii=False, indent=2`）；人类提示只走 stderr |

### gates.py 的 `--target`（多目标工作区）

门禁默认只统计术语表 `active_target` 的候选与日志。多目标工作区要显式指定，
否则看到的是「当前激活目标」的门，不是你以为的那个：

```powershell
python patent-research-skill/scripts/gates.py --target TGT-0002
```

目标号从哪来：先 `status.py` 看 `active_target`，或查 `00_方法论/术语表.yml` 的 `targets`。

### report.py 的两个细节

```powershell
# 写盘：--out 的相对路径按**工作区根**解析，不按当前目录
python patent-research-skill/scripts/report.py --target TGT-0002 `
    --out 04_对比分析/runs/2026-01-01_TGT-0002.md

# 只预览不写盘：省略 --out，骨架直接打到 stdout
python patent-research-skill/scripts/report.py --target TGT-0002
```

- `--target` 必须与 `00_方法论/术语表.yml` 的 `targets` 一致；否则骨架里轴为空（不会报错，所以**先 `status.py` 确认当前目标**）。
- `--out` **没有默认值**：默认写盘会在用户没想清楚时污染工作区数据，宁可多敲一个参数。
- 骨架的 §6 会要求填 `capture_mode`：`live` 才可能作 verified，`retrospective` / `memory` 只能作 asserted。

## 退出码

| 码 | 含义 | 典型场景 |
|---|---|---|
| 0 | 成功 | 命令自身的判定通过 |
| 1 | 业务失败 | 校验有 error（strict 下含 warn）/ 门未全 PASS / 报告写不出 |
| 2 | 工作区问题 | 定位不到工作区、`--root` 指错、`PATENTKIT_WORKSPACE` 指错、工作区数据损坏；argparse 用法错误也是 2 |
| 3 | 依赖缺失 | Python < 3.11，或 patentkit / 其依赖未安装 |
| 130 | 被 Ctrl+C 中断 | 非业务码，便于调用方区分「中断」与「失败」 |

> **与原生 `patentkit` CLI 的差异（重要）**
>
> * `python -m patentkit gates` 在门未全过时返回 **2**；本目录 `gates.py` 返回 **1**。
> * `python -m patentkit check` 在门未过时返回 **2**；本目录 `check.py` 返回 **1**。
>
> 原因：技能包统一约定 **2 只表示工作区问题**。否则客户端会把「门没过」误判成「工作区坏了」。
> 想区分失败原因，看 `--json` 结果里的 `validate.ok` 与 `gates.all_pass`。

## 工作区定位（找不到时的三条修法）

固定顺序：

1. `--root PATH` —— 单次显式指定；
2. 环境变量 `PATENTKIT_WORKSPACE` —— 设一次，之后任意目录可用；
3. 从当前目录向上找 `workspace.yml` —— 在仓库根 / 子目录直接跑就行。

```powershell
# 1) cd 到工作区根（含 workspace.yml）
cd <workspace>
python patent-research-skill/scripts/status.py

# 2) 单次指定
python patent-research-skill/scripts/status.py --root <workspace>

# 3) 设环境变量（当前会话）
$env:PATENTKIT_WORKSPACE = "<workspace>"
python patent-research-skill/scripts/status.py
```

> 定位失败**不会**静默回退到当前目录 —— 那会把「你不在工作区」伪装成
> 「术语表不存在」，是本仓库以前踩过的坑。现在统一 exit 2 + 三条修法。

## Windows / UTF-8 说明（必看）

* 脚本启动时把 stdout/stderr 锁成 **UTF-8**（`_env.configure_stdio()`），所以：
  * 不需要先 `chcp 65001`，也不需要设 `PYTHONIOENCODING`；
  * 输出里的 `✅ / ❌ / ⚠️` 不会把命令打崩。
* **父进程捕获输出时必须按 UTF-8 解码**。Python 里：

  ```python
  subprocess.run([...], capture_output=True, text=True, encoding="utf-8")
  ```

  用系统默认代码页（cp936）解码会得到乱码 —— 那不是脚本的问题。
* 所有文件（脚本 / 本文档）一律 UTF-8 无 BOM。

## `--json` 输出约定

* 成功：stdout 恰好一个 JSON 对象，含 `ok: true` 与 `command` 字段；其余字段来自对应 `api.*` 的返回。
* 失败（exit 1 / 2 / 3）：若加了 `--json`，stdout 输出：
  `{"ok": false, "code": <退出码>, "error": "...", "hints": ["..."]}`。
* 不加 `--json` 时，人类提示（`❌ …` 与修法）走 **stderr**，stdout 不混提示。
* `argparse` 用法错误（如缺 `--target`）走 argparse 默认行为：stderr + exit 2，不保证 JSON —— 这是有意的，用法错误应在调用前避免。

## 给 LLM 客户端的调用建议

1. **先 `status.py --json` 拿全局**（目标 / 门 / 校验 / 候选 / hints），别一上来连调五个。
2. 要机器判定才跑 `check.py --json`；退出码 0 才算「当前数据通过」。
3. 判定依据只看 `gates[].values.verified`；`attested` / `asserted` 是历史成绩，**不构成 PASS 依据**。
4. 客户端不能执行代码时，任何结论都要标「⚠️ 未经验证工具校验」，不得伪装成 verified。
5. 不替用户判定 `relevance`；模型代判时必须写「【模型代判】」+ 理由，并把结论标 `asserted`。
6. `report.py` 会**真实写盘**；先在 `--json` 结果的 `out` 字段确认路径，别在真实工作区随手试。

## 不做什么

* **不复制规则**：校验规则、门禁阈值、三列口径全部在 `patentkit/`；改口径请改源码，本目录零规则。
* **不写工作区数据**：唯一写操作是 `report.py --out`，且路径必须由调用方显式给。
* **不联网**：所有命令只读本地文件。
* **不 git add / commit**。

## 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| exit 3 | 没装 patentkit / Python 太老 | 按提示安装；装完 `python -m patentkit doctor` |
| exit 2 + 三条修法 | 工作区没定位到 | 按提示 cd / `--root` / 设 `PATENTKIT_WORKSPACE` |
| exit 2 + 「不是工作区」 | `--root` 指到了普通目录 | 确认该目录里有 `workspace.yml` |
| exit 1 + 校验失败 | 数据不一致 | 看 error 的 V0xx 规则码，先修数据 |
| exit 1 + 门未过 | 检索 / 复核量不够 | 补检索或补 relevance 复核 —— **不是放宽口径** |
| JSON 解析失败 | 没加 `--json`，或解码没用 UTF-8 | 加 `--json`；父进程按 UTF-8 解码 |
| 报「缺依赖模块 X」 | patentkit 装了但依赖不全 | `pip install -e ".[dev]"` |
