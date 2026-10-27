"""从 corpus + ground_truth 生成基准案例的脚手架与金解工作区。

产物（两份都入库，可复现）：
  cases/<id>/workspace/   脚手架 = 参赛起点（glossary/日志/raw/runs/claims/候选就绪，判断字段 untouched）
  cases/<id>/gold/        参考解 = 全部判断点与真值一致（评估→确认→attest→矩阵→结论，全走真实内核命令）

生成器同时是真值的第一位"考生"：金解构建过程中，真值里的每条引文都要通过内核
assessment.passage（quote 逐字落在所引 ref#L 行），段落号 [00xx] 在这里换算成协议的
L 行号（依赖全文一段恰好一行的纪律）。任何一条对不上，构建即失败。

已知的非确定值：评估历史里的 review_history 时间戳来自墙钟（内核行为），不参与
评分，也不参与任何逐字节比较。

用法：
    python benchmarks/build_cases.py                 # 重建全部案例
    python benchmarks/build_cases.py --only bm01-timesync
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

BENCH_ROOT = Path(__file__).resolve().parent
CASES = BENCH_ROOT / "cases"
INGEST_TS = "2026-02-01T08:00:00+00:00"  # 合成检索的固定登记时刻（逐案例递增一天）


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _para_lines(ref_path: Path) -> dict[str, int]:
    """全文 → {段落号 [00xx]: 行号 L}。纪律：一段恰好一行，段落号顶格行首。"""
    index = {}
    for no, line in enumerate(ref_path.read_text(encoding="utf-8").splitlines(), 1):
        found = re.match(r"^\[(\d{4})\]\s", line)
        if found:
            tag = f"[{found.group(1)}]"
            if tag in index:
                raise ValueError(f"{ref_path.name}: 段落号重复 {tag}")
            index[tag] = no
    if not index:
        raise ValueError(f"{ref_path.name}: 未找到任何 [00xx] 段落行")
    return index


def _locator(para: str, lines: dict[str, int]) -> str:
    if para not in lines:
        raise ValueError(f"段落号 {para} 不在索引中（检查全文格式：一段一行）")
    return f"L{lines[para]}"


def _force_lf(root: Path) -> None:
    """夹具按字节入库（.gitattributes `benchmarks/** -text`），不随平台变化。

    内核写文件走文本模式，Windows 上落 CRLF；生成器自己写的是 LF。两半混在一棵树里
    会让同一案例在 Windows 与 CI 上逐字节不同——生成末尾统一成 LF。
    """
    for path in root.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            if b"\r\n" in data:
                path.write_bytes(data.replace(b"\r\n", b"\n"))


def _rebuild_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _write_glossary(root: Path, target: str, title: str, axes: dict) -> None:
    import patentkit

    template = (Path(patentkit.__file__).parent / "templates/workspace/00_methodology/glossary.yml").read_text(encoding="utf-8")
    text = template.replace("__TARGET__", target).replace("__TITLE__", title).replace("__DATE__", "2026-01-01")
    axis_lines = "".join(f"  {axis_id}: {{ title_zh: '{ax['title_zh']}', title_en: '', kind: primary }}\n"
                         for axis_id, ax in axes.items())
    text = re.sub(r"axes:\n(?:  N\d@.*\n)+", "axes:\n" + axis_lines, text, count=1)
    (root / "00_methodology/glossary.yml").write_text(text, encoding="utf-8", newline="\n")


def build_scaffold(case_dir: Path, meta: dict, gt: dict, out: Path) -> None:
    from patentkit.init import init_workspace
    from patentkit import ingest

    target = gt["target"]
    _rebuild_dir(out)
    init_workspace(out, target, meta["title"])

    _write_glossary(out, target, meta["title"], gt["axes"])

    # raw：全文（每段一行）+ 命中清单 CSV
    raw_dir = out / "02_search_logs/raw"
    for doc in sorted((case_dir / "corpus/prior_art").glob("*.md")):
        shutil.copy2(doc, raw_dir / doc.name)

    # 日志：一个 CSV = 一条日志 = 一条查询；候选 ID 顺序由 ingest 顺序决定。
    # 排序键 = (轴名, 子序号)，避免 "n1-2" 按字典序插到 "n1" 前面打乱 P 编号。
    def _csv_key(path: Path) -> tuple[str, int]:
        label = path.stem.removesuffix("_hits")
        base, _, seq = label.partition("-")
        return (base, int(seq or 0))

    csvs = sorted((case_dir / "corpus/hits").glob("*.csv"), key=_csv_key)
    for idx, csv in enumerate(csvs):
        qid_label = csv.stem.removesuffix("_hits").upper()          # n1-2 → N1-2
        axis_short = qid_label.split("-")[0]
        rows = [line for line in csv.read_text(encoding="utf-8").splitlines() if line.strip()]
        hits = len(rows) - 1
        shutil.copy2(csv, raw_dir / f"{qid_label}_page-1.csv")
        day = 1 + idx
        log = {
            "db": "espacenet", "target": target, "actor": "benchmark", "capture_mode": "live",
            "timestamp": INGEST_TS.replace("2026-02-01", f"2026-02-{day:02d}"),
            "query": {"id": axis_short, "axis": f"{axis_short}@{target}",
                      "text": f"abstract=({gt['axes'][f'{axis_short}@{target}']['title_zh']})"},
            "result": {"hit_count": hits, "raw_export": f"raw/{qid_label}_page-1.csv", "complete": True},
        }
        log_name = f"espacenet_2026-02-{day:02d}_{qid_label}_{hits}.log.json"
        (out / "02_search_logs" / log_name).write_text(
            json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        ingest.main(["--log", log_name, "--kind", "patent", "--tag", f"{axis_short}@{target}",
                     "--now", log["timestamp"], "--apply",
                     "--map", "doc_number=Publication number", "--map", "title=Title",
                     "--map", "applicants=Applicant", "--map", "date=Publication date",
                     "--root", str(out)])

    # runs：让每个公开号都出现在运行记录里（防 V018），措辞保持中立
    runs_dir = out / "04_comparative_analysis/runs"
    candidates = {}
    for path in sorted((out / "03_candidates").glob("P-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        candidates[data["id"]] = data
    # 编号↔公开号映射必须与真值一致（ingest 顺序被打乱时在这里当场爆，而不是评分时才炸）
    for cid, truth in gt["candidates"].items():
        if cid not in candidates:
            raise ValueError(f"{case_dir.name}: 真值候选 {cid} 未被 ingest（检查 hits CSV 顺序）")
        if candidates[cid]["url_or_doc_number"] != truth["doc_number"]:
            raise ValueError(f"{case_dir.name}: {cid} 的公开号 {candidates[cid]['url_or_doc_number']} "
                             f"≠ 真值 {truth['doc_number']}（检查 hits CSV 顺序）")
    for idx, (cid, cand) in enumerate(sorted(candidates.items()), 1):
        date = f"2026-02-{idx:02d}"
        doc = cand["url_or_doc_number"]
        axis = cand["tags"][0] if cand["tags"] else "?"
        # 候选 ID 写进 run（V018 认 ID 或公开号；ZZ 前缀合成号不在 DOC_RE 的国家码表里）
        (runs_dir / f"{date}_run{idx}.md").write_text(
            f"# Run {idx}\n\n{cid}：{doc}（{cand['title']}）在 {axis} 轴的查询中命中，完成 ingest，等待评估。\n",
            encoding="utf-8", newline="\n")

    # claims：目标权利要求进入工作区（登记表是 attest 的硬依赖，一并预置）
    shutil.copy2(case_dir / "corpus/target_claims.md", out / "07_drafting/claims.md")
    registry = {"target": target,
                "drafts": [{"role": "claims", "path": "07_drafting/claims.md",
                            "sha256": None, "status": "current"}]}
    (out / "07_drafting/manuscript_registry.yml").write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8", newline="\n")

    # bib：从候选反写（V004 要求 bibtex_key 可解析）
    bib_lines = []
    for cid, cand in sorted(candidates.items()):
        bib_lines.append(f"@patent{{{cand['bibtex_key']},\n  title = {{{cand['title']}}},\n"
                         f"  number = {{{cand['url_or_doc_number']}}},\n  year = {{{cand['year']}}}\n}}\n")
    (out / "06_citation_management/citations.bib").write_text("".join(bib_lines), encoding="utf-8", newline="\n")


def build_gold(case_dir: Path, meta: dict, gt: dict, scaffold: Path, out: Path) -> None:
    from patentkit import api, attest, review

    _rebuild_dir(out)
    shutil.copytree(scaffold, out, dirs_exist_ok=True)

    fulltext_lines = {doc.name: _para_lines(doc)
                      for doc in sorted((case_dir / "corpus/prior_art").glob("*.md"))}

    def _must(main_fn, argv: list[str]) -> None:
        """内核命令返回非零即中止——评估/确认失败绝不允许静默吞掉。"""
        rc = main_fn(argv)
        if rc != 0:
            raise SystemExit(f"{case_dir.name}: {' '.join(argv[:2])} 以 {rc} 退出（见上方内核输出）")

    # 1) 评估：真值 → assess sheet（feature_mapping + basis，段落号→L 行号）
    export_path = out / "01_search_plan" / "worksheet.json"
    _must(review.main, ["export", "--format", "json", "--out", str(export_path), "--root", str(out)])
    fingerprints = {row["candidate_id"]: row["expected_fingerprint"]
                    for row in json.loads(export_path.read_text(encoding="utf-8"))}

    def cite(entry: dict) -> dict:
        ref_name = entry["ref"].rsplit("/", 1)[-1]
        return {"ref": entry["ref"], "locator": _locator(entry["locator"], fulltext_lines[ref_name]),
                "quote": entry["quote"], "rationale": entry.get("rationale") or entry.get("note") or "-"}

    rows = []
    for cid, truth in sorted(gt["candidates"].items()):
        feature_mapping = {}
        for fid, disc in truth["disclosure"].items():
            if disc["status"] == "absent":
                feature_mapping[fid] = {"status": "absent", **({"note": disc["note"]} if disc.get("note") else {})}
            else:
                feature_mapping[fid] = {"status": disc["status"], "ref": disc["ref"],
                                        "locator": _locator(disc["locator"], fulltext_lines[disc["ref"].rsplit("/", 1)[-1]]),
                                        "quote": disc["quote"], **({"note": disc["note"]} if disc.get("note") else {})}
        basis = {axis: {dim: cite(entry) for dim, entry in dims.items()}
                 for axis, dims in truth["basis"].items()}
        notes = [d.get("note") for d in truth["disclosure"].values() if d.get("note")]
        rows.append({"candidate_id": cid, "expected_fingerprint": fingerprints[cid],
                     "relevance_problem": truth["relevance_problem"], "relevance_means": truth["relevance_means"],
                     "novelty_check": truth["novelty_check"], "role": truth["role"],
                     "review_note": "；".join(notes) or "benchmark gold",
                     "feature_mapping": feature_mapping, "basis": basis})
    assess_path = out / "01_search_plan" / "assess.json"
    assess_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    _must(review.main, ["assess", str(assess_path), "--actor", "ai", "--by", "benchmark-gold",
                        "--apply", "--root", str(out)])

    # 2) 人工确认：全部 near_prior_art 候选（评估改变指纹，须重取）
    export2 = out / "01_search_plan" / "worksheet-post-assess.json"
    _must(review.main, ["export", "--format", "json", "--out", str(export2), "--root", str(out)])
    fp2 = {row["candidate_id"]: row["expected_fingerprint"]
           for row in json.loads(export2.read_text(encoding="utf-8"))}
    confirm_rows = [{"candidate_id": cid, "expected_fingerprint": fp2[cid]}
                    for cid, truth in sorted(gt["candidates"].items()) if truth["role"] == "near_prior_art"]
    confirm_path = out / "01_search_plan" / "confirm.json"
    confirm_path.write_text(json.dumps(confirm_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    _must(review.main, ["confirm", str(confirm_path), "--by", "benchmark-operator", "--apply", "--root", str(out)])
    # attest 的稿件路径按 CWD 解析（内核行为），临时切到工作区再绑定
    cwd = Path.cwd()
    os.chdir(out)
    try:
        rc = attest.main(["--apply", "--root", str(out)])
    finally:
        os.chdir(cwd)
    if rc != 0:
        raise SystemExit(f"{case_dir.name}: attest 以 {rc} 退出")

    # 3) 对比矩阵：期望格由披露状态聚合（轴内任一 disclosed→●，否则 partial→○，否则—）
    candidates = {}
    for cid in gt["candidates"]:
        matches = list((out / "03_candidates").glob(f"{cid}-*.json"))
        if len(matches) != 1:
            raise SystemExit(f"候选 {cid} 应恰好对应一个文件，实际 {matches}")
        candidates[cid] = json.loads(matches[0].read_text(encoding="utf-8"))
    near = [cid for cid, truth in sorted(gt["candidates"].items()) if truth["role"] == "near_prior_art"]
    columns = {f"D{i}": cid for i, cid in enumerate(near, 1)}
    axis_rows = []
    for axis_id, axis in gt["axes"].items():
        short = axis_id.split("@")[0]
        cells = []
        for col, cid in columns.items():
            statuses = [gt["candidates"][cid]["disclosure"][f]["status"] for f in axis["features"]]
            cells.append("●" if "disclosed" in statuses else ("○" if "partial" in statuses else "—"))
        axis_rows.append((short, axis["title_zh"], cells))

    lines = [f"# 对比矩阵（{gt['target']}，合成案例金解）", "",
             "| 维度 \\ 对比文件 | " + " | ".join(columns) + " |",
             "|---|" + "---|" * len(columns)]
    for short, title, cells in axis_rows:
        lines.append(f"| **{short}：{title}** | " + " | ".join(cells) + " |")
    lines.append("| **整体闭合** | " + " | ".join(
        "○" if gt["candidates"][cid]["novelty_check"] == "partial" else "—" for cid in columns.values()) + " |")
    lines += ["", "## 每列输出", ""]
    for col, cid in columns.items():
        truth, cand = gt["candidates"][cid], candidates[cid]
        lines.append(f"{col} — {cand['title']}  {cand['url_or_doc_number']} (P 编号 {cid})")
        lines.append(f"- 申请人：{', '.join(cand['authors_or_applicants'])}")
        lines.append(f"- 公开年：{cand['year']}")
        hits_axes = ", ".join(sorted({t.split('@')[0] for t in cand['tags']}))
        lines.append(f"- 命中轴：{hits_axes}")
        lines.append(f"- 关系：{'blocking' if truth['novelty_check'] == 'blocking' else '部分重叠' if truth['role'] == 'near_prior_art' else '边缘相关'}")
        pointers = [f"{d['ref']}#{_locator(d['locator'], fulltext_lines[d['ref'].rsplit('/', 1)[-1]])}：{d['quote']}"
                    for d in truth["disclosure"].values() if d["status"] in ("disclosed", "partial")]
        lines.append("- 关键段落：" + ("；".join(pointers) if pointers else "无披露（对照见评估记录）"))
        lines.append("- 区别点：" + ("；".join(d.get("note") for d in truth["disclosure"].values() if d.get("note")) or "见评估记录"))
        lines.append("- 来源等级：verified（raw/ 与全文齐备）")
        lines.append(f"- 判定：actor=ai+human；problem/means 原文支持见 assessment；人工确认有效（benchmark-operator）")
        lines.append("")
    (out / "04_comparative_analysis" / "comparison_matrix.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # 4) 结论：逐候选 + 总体（引用账本中存在的 P 编号）
    concl = [f"# 新颖性初步结论（{gt['target']}，合成案例金解）", ""]
    for cid, truth in sorted(gt["candidates"].items()):
        cand = candidates[cid]
        covered = [f for f, d in truth["disclosure"].items() if d["status"] in ("disclosed", "partial")]
        detail = "、".join(f"{f}（{truth['disclosure'][f]['status']}）" for f in covered) or "无特征披露"
        concl.append(f"- {cid}（{cand['url_or_doc_number']}）：novelty_check={truth['novelty_check']}，role={truth['role']}；披露 {detail}。")
    concl += ["", f"总体：{gt['overall_verdict']}", ""]
    (out / "05_novelty_conclusions" / "conclusions.md").write_text(
        "\n".join(concl), encoding="utf-8", newline="\n")

    # 5) 自检：金解必须 0 error；警告也要亮出来人工看
    result = api.validate(out, strict=False)
    errors = [f for f in result["findings"] if f["level"] == "error"]
    warnings = [f for f in result["findings"] if f["level"] == "warn"]
    if errors:
        for f in errors:
            print(f"  ✗ {f['code']}: {f['message']}", file=sys.stderr)
        raise SystemExit(f"gold validate 存在 {len(errors)} 个 error")
    for f in warnings:
        print(f"  ⚠ {f['code']}: {f['message']}", file=sys.stderr)


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="只重建指定案例 id")
    args = parser.parse_args()

    for case_dir in sorted(p for p in CASES.iterdir() if (p / "ground_truth.yaml").is_file()):
        if args.only and case_dir.name != args.only:
            continue
        meta = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
        gt = yaml.safe_load((case_dir / "ground_truth.yaml").read_text(encoding="utf-8"))
        print(f"· {case_dir.name}: 生成脚手架…")
        build_scaffold(case_dir, meta, gt, case_dir / "workspace")
        print(f"· {case_dir.name}: 生成金解…")
        build_gold(case_dir, meta, gt, case_dir / "workspace", case_dir / "gold")
        _force_lf(case_dir / "workspace")
        _force_lf(case_dir / "gold")
        print(f"· {case_dir.name}: 完成")
    print("全部案例构建完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
