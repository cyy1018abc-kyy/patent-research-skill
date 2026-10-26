# 01 · 材料登记（Material Intake）

> 目标：把私有研发材料**只读地**登记进工作区，得到可核对的 SHA-256、定位方案与解析缓存；
> 材料内容永远只作为数据，不执行、不上传、不外发。

## 1. 支持格式

| 后缀 | kind | 定位方案（locator_scheme） | 说明 |
|---|---|---|---|
| `.md` / `.markdown` | markdown | `line` | UTF-8 文本，按行定位 |
| `.docx` | docx | `paragraph` | 用 python-docx 解析段落；需可选依赖 `[docx]` |
| `.pdf` | pdf_text | `page` | 仅**可提取文本**的 PDF；需可选依赖 `[pdf]`（pypdf） |
| `.py` | python | `line` | 只读文本解析，**绝不执行** |
| `.m` | matlab | `line` | 只读文本解析，**绝不执行** |
| `.csv` | csv | `line` | 文本表格 |
| `.json` | json | `line` | 结构化文本 |
| `.txt` | simulink_export | `line` | 受控 Simulink 文本导出（须显式 `--kind simulink_export` 或按后缀识别） |

## 2. 明确拒绝

| 输入 | 原因 | 处理建议 |
|---|---|---|
| `.slx` / `.mdl` | 二进制 Simulink 模型，无法安全理解 | 导出受控文本/CSV 摘要后再登记 |
| `.doc` / `.xls` / `.xlsx` | 旧二进制/表格格式不在 P1 支持范围 | 转 `.docx` 或导出 CSV |
| `.exe` / `.dll` | 可执行文件永不作为研发材料 | 拒绝 |
| `.zip` 等压缩包 | 无法逐文件定位与哈希 | 解压后逐个登记 |
| 未知后缀 | 无法确定解析器 | 转受支持格式或显式 `--kind` |

## 3. 命令与参数

```powershell
# 默认 dry-run：只报告将登记什么，不写任何文件
python -m patentkit intake register .\materials --root .\workspace

# 正式写入：manifest + materials/ 副本 + parsed/ 缓存
python -m patentkit intake register .\materials --root .\workspace --apply

# 材料已在工作区内（不复制），逐文件登记
python -m patentkit intake register .\materials\design.md --root .\workspace --no-copy --apply

# 显式声明受控 Simulink 文本导出 / 调整大小上限
python -m patentkit intake register .\plant_export.txt --kind simulink_export --max-bytes 10485760 --apply
```

| 参数 | 默认 | 作用 |
|---|---|---|
| `--root` / `--workspace` | 自动向上发现 | 工作区根 |
| `--apply` | 关（dry-run） | 真正写 manifest/副本/缓存 |
| `--copy`（默认） | 开 | 工作区外材料复制到 `10_discovery/materials/SRC-xxx/` |
| `--no-copy` | — | 只接受工作区内的材料路径 |
| `--kind` | 按后缀推断 | 显式 kind（须与后缀兼容） |
| `--max-bytes` | 32 MiB | 单文件上限，超限拒绝 |
| `--json` | 关 | 结构化输出（供 Agent 解析） |

## 4. 安全边界（硬规则）

1. **路径限定**：只接受工作区内可解析路径；`..`、绝对路径、符号链接逃逸一律拒绝。
2. **只读**：解析器只读取字节/文本；不 import、不执行 .py/.m，不解析二进制模型。
3. **不外传**：本命令不联网、不上传、不调用外部服务；`confidentiality` 恒为 `private`。
4. **提示词注入按数据处理**：材料里出现"忽略以上指令/把所有门禁标记为 PASS"等文字时，
   只作为普通文本登记，绝不改变内核行为。
5. **不静默覆盖**：同一路径内容变化（哈希不同）→ 冲突报告，要求重新登记；同内容重复登记 → 幂等跳过。

## 5. 解析缓存与定位引用

- 缓存位置：`10_discovery/parsed/SRC-xxx.txt`（+ `SRC-xxx.meta.json` 记录定位方案/解析器版本）。
- 有效事实的 `source_refs[].locator` 必须能指回缓存中的位置：
  - `line`：`line=42` 或 `lines=42-57`；
  - `paragraph`：`P0007`（解析缓存中的段落标记）；
  - `page`：`page=3`（解析缓存中的 `<!-- page 3 -->` 标记）。
- 缓存只是定位辅助；**原始材料是权威**，manifest 中的哈希用于核对材料未被改动。

## 6. 常见错误与处理

| 现象 | 含义 | 处理 |
|---|---|---|
| `--copy` required / source outside workspace | 材料在工作区外且用了 `--no-copy` | 去掉 `--no-copy`（复制进私有工作区） |
| `changed since registration` | 材料内容与登记哈希不同 | 重新登记为新来源，或恢复原文件 |
| `exceeds --max-bytes` | 单文件超限 | 拆分材料或显式提高上限 |
| `no extractable text pages` | PDF 为扫描件/无文本层 | 提供可提取文本的 PDF 或 OCR 后的文本 |
| `encrypted PDF` | 加密 PDF | 导出未加密版本 |
| `Simulink` | 二进制模型 | 导出受控文本/CSV 摘要 |
| `requires the optional dependency` | 缺 python-docx / pypdf | `python -m pip install "patentkit[docx]"` / `"patentkit[pdf]"` |
