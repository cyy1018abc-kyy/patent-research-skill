# patentkit 0.1.1

专利工作区校验 / 验收门内核（命令行 + Python 库）。
技能包 `patent-research-skill` 的规则执行层：证据三级判定、V001–V028 校验、G-S-01..05 验收门。

## 本版变化（0.1.0 → 0.1.1）

- **修复**：`gates.py` 的 G-S-01 提示文案带出历史真实目标 ID（`历史目标 ID`）——
  会随工具输出泄漏到客户端会话，改为通用文案。
- **版本单一来源**：`patentkit/__init__.py` 的 `__version__` 是唯一字面量，
  `pyproject.toml` 用 dynamic 读取；`tests/test_version.py` 守护。
- 工具数量 / 测试数量等文档口径统一。

## 附件与校验

| 附件 | SHA-256 |
|---|---|
| `patentkit-0.1.1-py3-none-any.whl` | `6edb60f761f03b88039ad50e58d5a271a397bc1883fcb43be8080eabd70f4231` |
| `patentkit-0.1.1.tar.gz` | `a77066c0db61fc40a0b791a9aebd2ff298764be512c2ad2c6f28c64e661f5585` |
| `SHA256SUMS-patentkit-v0.1.1.txt` | — |

## 安装

```powershell
# 直接用 release 附件
pip install https://github.com/cyy1018abc-kyy/patent-research-skill/releases/download/patentkit-v0.1.1/patentkit-0.1.1-py3-none-any.whl

# 或从 GitHub 的 tag 安装
pip install "git+https://github.com/cyy1018abc-kyy/patent-research-skill.git@patentkit-v0.1.1"
```

## 要求

- Python ≥ 3.11
- 运行期依赖：`jsonschema>=4.18`、`PyYAML>=6.0`（pip 自动安装）
- 可选：`mcp>=1.0,<2`（`patentkit mcp` 适配器，安装 `patentkit[mcp]`）

## 配套技能包

下载/安装 **skill-v2.3.0** 的 `patent-research-skill-v2.3.0.zip`（见同页 Releases）。
