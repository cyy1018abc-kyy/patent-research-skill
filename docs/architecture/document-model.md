# 文档数据模型与解析器契约（WP-C）

解析器实现：`extensions/patent_intel/src/patent_intel/documents/`；测试：
`extensions/patent_intel/tests/test_documents.py`（夹具 `tests/fixtures/documents/`，
无敏感信息、合成内容）。

## 模型

```
StructuredPatentDocument
├── source_document      # 工作区相对路径（原始工件指针）
├── raw_sha256           # 原始字节哈希——一切定位的根锚
├── parser_version       # 结构变更必须升版；旧锚点随即 stale（UT-D02）
├── publication_number / title / language
├── paragraphs[]         # Paragraph{para_id, text, origin, section, page?}
│     origin ∈ {native_xml, parser_assigned}
│     section ∈ {abstract, claims, description, other}
├── claims[]             # Claim{number, text, depends_on[], unresolved_refs[]}
└── quality{}            # score/citable/notes —— 低质文档锚点拒绝自动可引
```

## 不变量（全部有测试锁定）

1. **verbatim**：`Paragraph.text` 是原文切片，解析器不修正、不合并、不注音。
2. **编号来源可辨**：源文档自带编号（XML `num`、权项 `num` 属性）⇒
   `origin=native_xml`；解析器自编 ⇒ `parser_assigned`。引用工作流必须区分
   官方段号与机器编号——后者永远不能冒充前者。
3. **XXE 安全**：任何含 DOCTYPE/ENTITY 声明的 XML 直接拒绝（UT-D01）。
4. **权项引用不猜测**：指向不存在权项号的引用进 `unresolved_refs`（标注
   unknown），绝不静默丢弃或猜测；环依赖与重复编号由 `claim_tree_issues` 报出。
5. **定位符三重绑定**：`raw_sha256 + paragraph id + text_hash`，外加
   `parser_version`；四者任一失配 ⇒ `verify_anchor` 返回 `stale`（文件改动、
   段号漂移、解析器升版都不静默复用旧锚，UT-D02）。
6. **低质即降级**：`quality.score < 0.7` 或 OCR 来源 ⇒ 锚点最高
   `unverified`，只能辅助检索，不能进入自动引用（接口规则 6）。
7. **受控失败**：超限（XML 32MB / PDF 200MB）、畸形 XML、加密/坏 PDF 都是
   带原因的异常，绝不产出半截结构。

## 解析器矩阵

| 入口 | 依赖 | 支持 |
|---|---|---|
| `patent_xml.parse_patent_xml` | 无（stdlib） | OPS exchange-document 等命名空间无关 XML |
| `patent_xml.parse_text_document` | 无 | CNIPA/网页导出的 md/txt（标题分节） |
| `pdf_adapter.parse_pdf` | extra `pdf`（docling） | PDF/扫描件；OCR 输出一律 `parser_assigned` + `ocr_source` 标记 |

## 演进

结构字段变更 ⇒ `PARSER_VERSION` 升版 + 变更记录在此；定位符语义向后兼容
（旧锚只降级 stale，永不误判 fresh）。
