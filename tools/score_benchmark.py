"""score_benchmark —— 合成专利案例行为基准评分器（引用准确性 / 特征遗漏 / 误判率）。

评分对象是"一个已经跑完判断链的工作区"；评分依据是案例的 ground_truth.yaml。
边界纪律（见 benchmarks/README.md）：

* 规则判断全部交给内核：先 `patentkit.api.validate`（有 error 直接拒评，exit 2）；
* 引文核验直接调用内核 `patentkit.assessment.passage`（ref#L 行定位 + quote 逐字包含），
  与评估协议同一套语义，这里不另立标准；
* 评分器新增的只有"工作区产物 ↔ 案例真值"的比对。

指标：
* citation_precision   三个引文面（assessment.basis / feature_mapping / 对比矩阵关键段落）
                       的逐字核验通过率；
* citation_coverage    真值 expected_citations（由 basis + 披露引文推导）被覆盖的比例；
* feature_omission     真值认为有候选披露的特征中，工作区没有任何候选以
                       disclosed/partial（且引文核验通过）表态的比例；
* misjudgment_rate     逐判断点（role / novelty_check / relevance 两维 / 逐特征状态 /
                       矩阵格 / 结论必引）与真值不一致的比例。

用法：
    python tools/score_benchmark.py --case benchmarks/cases/bm01-timesync --workspace <dir>
    python tools/score_benchmark.py --suite benchmarks/cases --gold --gate perfect   # CI 金解门
    python tools/score_benchmark.py --case ... --workspace ... --json

退出码：0 通过；1 评分完成但 --gate 未达标；2 环境/工作区无效（不可评）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = ROOT / "benchmarks"

MATRIX_ROW_RE = re.compile(r"^\|\s*\*\*(N\d)：[^*]+\*\*(.*)\|\s*$")
COLUMN_HEAD_RE = re.compile(r"^D(\d+)\s*—")
POINTER_RE = re.compile(r"([\w./\\-]+\.md)#(L\d+(?:-L\d+)?)：([^；]+)")
CELL_SPLIT_RE = re.compile(r"[●○—?]")
PID_RE = re.compile(r"\b[PL]-\d{3,}\b")
LOC_RE = re.compile(r"^L(\d+)(?:-L?(\d+))?$")


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _locator_range(locator: str) -> tuple[int, int] | None:
    found = LOC_RE.match(locator.strip())
    if not found:
        return None
    first, last = int(found.group(1)), int(found.group(2) or found.group(1))
    return (first, last) if first <= last else None


# ── 引文收集 ──────────────────────────────────────────────────────────────


def collect_citations(workspace: Path, candidates: list) -> tuple[list[dict], list[str]]:
    """三个引文面 → [{surface, owner, ref, locator, quote, ok}]；并返回解析期问题。"""
    from patentkit.assessment import passage

    citations: list[dict] = []
    notes: list[str] = []

    def verify(surface: str, owner: str, ref: str, locator: str, quote: str) -> None:
        entry = {"surface": surface, "owner": owner, "ref": ref, "locator": locator, "quote": quote}
        try:
            passage(workspace, {"ref": ref, "locator": locator, "quote": quote, "rationale": "-"})
            entry["ok"] = True
        except (ValueError, OSError) as exc:
            entry["ok"] = False
            entry["error"] = str(exc)[:200]
        citations.append(entry)

    for cand in candidates:
        basis = (cand.data.get("assessment") or {}).get("basis") or {}
        if isinstance(basis, dict):
            for axis, dims in basis.items():
                if not isinstance(dims, dict):
                    continue
                for dim in ("problem", "means"):
                    cite = dims.get(dim)
                    if isinstance(cite, dict) and cite.get("ref") and cite.get("quote"):
                        verify("assessment", f"{cand.id}/{axis}/{dim}",
                               str(cite["ref"]), str(cite.get("locator", "")), str(cite["quote"]))
        mapping = cand.data.get("feature_mapping") or {}
        if isinstance(mapping, dict):
            for fid, entry in mapping.items():
                if not isinstance(entry, dict) or entry.get("status") not in ("disclosed", "partial"):
                    continue
                if entry.get("ref") and entry.get("quote"):
                    verify("feature_mapping", f"{cand.id}/{fid}",
                           str(entry["ref"]), str(entry.get("locator", "")), str(entry["quote"]))
                else:
                    notes.append(f"{cand.id} 的 feature_mapping[{fid}] 状态为 {entry.get('status')} 但缺 ref/quote")
    return citations, notes


def parse_matrix(workspace: Path) -> tuple[dict[str, str], dict[tuple[str, str], str], list[dict], list[str]]:
    """对比矩阵 → (列→候选, {(轴短名, 候选): 格}, 关键段落引文, 解析问题)。

    结构约定：先表格（表头行给出 D 列顺序），后每列输出块（D1 — … 起头，
    块内 `- 关键段落：路径#L行：摘句；…`）。
    """
    path = workspace / "04_comparative_analysis" / "comparison_matrix.md"
    if not path.is_file():
        return {}, {}, [], [f"缺少对比矩阵：{path.relative_to(workspace)}"]
    text = path.read_text(encoding="utf-8")
    col_to_cand: dict[str, str] = {}
    cells: dict[tuple[str, str], str] = {}
    citations: list[dict] = []
    problems: list[str] = []
    column_order: list[str] = []
    current_col: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("| 维度"):
            column_order = [token.strip() for token in stripped.split("|")
                            if re.fullmatch(r"D\d+", token.strip())]
            if not column_order:
                problems.append("矩阵表头行没有解析到 D 列（约定：| 维度 \\ 对比文件 | D1 | D2 |…）")
            continue
        head = COLUMN_HEAD_RE.match(stripped)
        if head:
            current_col = f"D{head.group(1)}"
            ids = PID_RE.findall(stripped)
            if ids:
                col_to_cand[current_col] = ids[0]
            else:
                problems.append(f"矩阵列 {current_col} 首行未包含候选 ID（约定：D1 — 标题 (P-001)）")
            continue
        row = MATRIX_ROW_RE.match(stripped)
        if row:
            axis_short, rest = row.group(1), row.group(2)
            marks = CELL_SPLIT_RE.findall(rest)
            if len(marks) != len(column_order):
                problems.append(f"矩阵行 {axis_short} 的格子数（{len(marks)}）与列数（{len(column_order)}）不一致")
            for col, mark in zip(column_order, marks):
                cells[(axis_short, col)] = mark
            continue
        if stripped.startswith("- 关键段落："):
            owner = col_to_cand.get(current_col or "", current_col or "?")
            for found in POINTER_RE.finditer(stripped):
                citations.append({"surface": "matrix", "owner": owner,
                                  "ref": found.group(1), "locator": found.group(2),
                                  "quote": found.group(3).strip()})
            continue
    return col_to_cand, cells, citations, problems


# ── 评分 ──────────────────────────────────────────────────────────────────


def score_case(case_dir: Path, workspace: Path) -> tuple[dict, list[str]]:
    """返回 (指标报告, 不可评原因)。原因非空 = exit 2。"""
    from patentkit import api
    from patentkit.assessment import passage
    from patentkit.model import load_candidates

    case_dir = case_dir.resolve()
    workspace = workspace.resolve()
    gt = yaml.safe_load((case_dir / "ground_truth.yaml").read_text(encoding="utf-8"))
    target = gt["target"]

    # 语料完整性：raw 下的全文与命中清单必须与 corpus 逐字节一致（防"改语料凑引文"）
    for doc in sorted((case_dir / "corpus/prior_art").glob("*.md")):
        deployed = workspace / "02_search_logs/raw" / doc.name
        if not deployed.is_file() or hashlib.sha256(deployed.read_bytes()).hexdigest() != hashlib.sha256(doc.read_bytes()).hexdigest():
            return {}, [f"语料被改动或缺失：{doc.name}（工作区 raw/ 必须与 corpus 逐字节一致）"]
    for csv in sorted((case_dir / "corpus/hits").glob("*.csv")):
        label = csv.stem.removesuffix("_hits").upper()
        deployed = workspace / "02_search_logs/raw" / f"{label}_page-1.csv"
        if not deployed.is_file() or hashlib.sha256(deployed.read_bytes()).hexdigest() != hashlib.sha256(csv.read_bytes()).hexdigest():
            return {}, [f"命中清单被改动或缺失：{label}_page-1.csv"]

    validation = api.validate(workspace)
    if validation["summary"]["errors"] > 0:
        bad = [f for f in validation["findings"] if f["level"] == "error"]
        return {}, ["工作区校验存在 error，先修复再评分："] + [f"  {f['code']} {f['path']} — {f['message']}" for f in bad[:10]]
    warn_count = validation["summary"]["warnings"]

    # 全文行索引：段落号 [00xx] → L 行号（语料纪律：一段恰好一行）
    para_lines: dict[str, dict[str, int]] = {}
    for doc in sorted((case_dir / "corpus/prior_art").glob("*.md")):
        index = {}
        for no, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            found = re.match(r"^\[(\d{4})\]\s", line)
            if found:
                index[f"[{found.group(1)}]"] = no
        para_lines[doc.name] = index

    def expected_locator(ref: str, para: str) -> str:
        name = ref.rsplit("/", 1)[-1]
        key = para if para.endswith("]") else f"[{para.strip('[]')}]"
        if name not in para_lines or key not in para_lines[name]:
            raise ValueError(f"真值定位无法解析：{ref}#{para}")
        return f"L{para_lines[name][key]}"

    candidates = load_candidates(workspace)
    by_id = {c.id: c for c in candidates}

    # ── 引文面 ──
    basis_fm_citations, notes = collect_citations(workspace, candidates)
    col_to_cand, cells, matrix_citations, matrix_problems = parse_matrix(workspace)
    notes += matrix_problems
    citations = basis_fm_citations + [
        {**c, "ok": _verify_one(workspace, c)} for c in matrix_citations]
    for c in citations:
        c["range"] = _locator_range(c["locator"])
    total = len(citations)
    passed = sum(1 for c in citations if c["ok"])
    precision = (passed / total) if total else None

    # ── coverage：真值期望引文（basis + 披露引文） ──
    expected_pairs: set[tuple[str, str]] = set()
    for cid, truth in gt["candidates"].items():
        for dims in truth["basis"].values():
            for cite in dims.values():
                expected_pairs.add((cite["ref"], expected_locator(cite["ref"], cite["locator"])))
        for disc in truth["disclosure"].values():
            if disc["status"] in ("disclosed", "partial"):
                expected_pairs.add((disc["ref"], expected_locator(disc["ref"], disc["locator"])))
    verified_pairs = {(c["ref"], c["locator"]) for c in citations if c["ok"]}

    def covered(ref: str, locator: str) -> bool:
        want = _locator_range(locator)
        if want is None:
            return False
        for pair in verified_pairs:
            if pair[0] != ref:
                continue
            got = _locator_range(pair[1])
            if got and got[0] <= want[0] and got[1] >= want[1]:
                return True
        return False

    covered_pairs = {pair for pair in expected_pairs if covered(*pair)}
    coverage = (len(covered_pairs) / len(expected_pairs)) if expected_pairs else None

    # ── 特征遗漏 ──
    features_detail: dict[str, dict] = {}
    omissions: list[str] = []
    feature_ids = list(gt["features"])
    for fid in feature_ids:
        truth_disclosers = [cid for cid, truth in gt["candidates"].items()
                            if truth["disclosure"].get(fid, {}).get("status") in ("disclosed", "partial")]
        found = False
        for cand in candidates:
            entry = (cand.data.get("feature_mapping") or {}).get(fid) if isinstance(cand.data.get("feature_mapping"), dict) else None
            if isinstance(entry, dict) and entry.get("status") in ("disclosed", "partial"):
                if entry.get("ref") and entry.get("quote"):
                    try:
                        passage(workspace, {"ref": entry["ref"], "locator": str(entry.get("locator", "")),
                                            "quote": str(entry["quote"]), "rationale": "-"})
                        found = True
                    except (ValueError, OSError):
                        pass
        features_detail[fid] = {"expected_disclosers": truth_disclosers, "captured": found}
        if truth_disclosers and not found:
            omissions.append(fid)
    omission_rate = (len(omissions) / len(feature_ids)) if feature_ids else None

    # ── 误判点 ──
    mismatches: list[str] = []
    points = 0

    def judge(ok: bool, label: str, expect, actual) -> None:
        nonlocal points
        points += 1
        if not ok:
            mismatches.append(f"{label}: 期望 {expect}，实际 {actual}")

    for cid, truth in gt["candidates"].items():
        cand = by_id.get(cid)
        if cand is None:
            for field in ("role", "novelty_check", "relevance_problem", "relevance_means"):
                judge(False, f"{cid}.{field}", truth[field], "候选缺失")
            for fid in feature_ids:
                judge(False, f"{cid}.{fid}.status", truth["disclosure"].get(fid, {}).get("status"), "候选缺失")
            continue
        mapping = cand.data.get("feature_mapping") if isinstance(cand.data.get("feature_mapping"), dict) else {}
        judge(cand.data.get("role") == truth["role"], f"{cid}.role", truth["role"], cand.data.get("role"))
        judge(cand.data.get("novelty_check") == truth["novelty_check"], f"{cid}.novelty_check",
              truth["novelty_check"], cand.data.get("novelty_check"))
        judge(cand.data.get("relevance_problem") == truth["relevance_problem"],
              f"{cid}.relevance_problem", truth["relevance_problem"], cand.data.get("relevance_problem"))
        judge(cand.data.get("relevance_means") == truth["relevance_means"],
              f"{cid}.relevance_means", truth["relevance_means"], cand.data.get("relevance_means"))
        for fid in feature_ids:
            expect = truth["disclosure"].get(fid, {}).get("status")
            actual = (mapping.get(fid) or {}).get("status") if isinstance(mapping.get(fid), dict) else "missing"
            judge(actual == expect, f"{cid}.{fid}.status", expect, actual)

    # 矩阵格：期望格 = 轴内任一 disclosed→●，否则 partial→○，否则—
    near = [cid for cid, truth in gt["candidates"].items() if truth["role"] == "near_prior_art"]
    col_for_cand = {cand: col for col, cand in col_to_cand.items()}
    for axis_id, axis in gt["axes"].items():
        short = axis_id.split("@")[0]
        for cid in near:
            statuses = [gt["candidates"][cid]["disclosure"].get(f, {}).get("status") for f in axis["features"]]
            expect = "●" if "disclosed" in statuses else ("○" if "partial" in statuses else "—")
            col = col_for_cand.get(cid)
            actual = cells.get((short, col), "列缺失") if col else "无对应列"
            judge(actual == expect, f"matrix[{short}][{cid}]", expect, actual)

    # 结论必引
    concl_text = ""
    concl_dir = workspace / "05_novelty_conclusions"
    if concl_dir.is_dir():
        concl_text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                               for p in sorted(concl_dir.glob("*.md")))
    for cid in gt["conclusions_must_cite"]:
        judge(bool(PID_RE.search(concl_text or "")) and cid in concl_text,
              f"conclusions.cite[{cid}]", f"结论需引用 {cid}", "未引用")

    misjudgment_rate = (len(mismatches) / points) if points else None
    report = {
        "case": case_dir.name, "workspace": str(workspace),
        "validate": {"errors": 0, "warnings": warn_count},
        "citation": {"total": total, "passed": passed,
                     "precision": precision,
                     "coverage": coverage,
                     "expected_pairs": len(expected_pairs),
                     "failed": [{k: c.get(k) for k in ("surface", "owner", "ref", "locator", "error")}
                                for c in citations if not c["ok"]]},
        "features": {"total": len(feature_ids), "omissions": omissions,
                     "omission_rate": omission_rate, "detail": features_detail},
        "judgment": {"points": points, "mismatches": mismatches,
                     "misjudgment_rate": misjudgment_rate},
        "notes": notes,
    }
    return report, []


def _verify_one(workspace: Path, citation: dict) -> bool:
    from patentkit.assessment import passage

    try:
        passage(workspace, {"ref": citation["ref"], "locator": citation["locator"],
                            "quote": citation["quote"], "rationale": "-"})
        return True
    except (ValueError, OSError):
        return False


def perfect(report: dict) -> bool:
    c, f, j = report["citation"], report["features"], report["judgment"]
    return (c["total"] > 0 and c["precision"] == 1.0 and c["coverage"] == 1.0
            and f["total"] > 0 and f["omission_rate"] == 0.0
            and j["points"] > 0 and j["misjudgment_rate"] == 0.0)


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", type=Path, help="案例目录（benchmarks/cases/<id>）")
    parser.add_argument("--workspace", type=Path, help="待评分的工作区目录")
    parser.add_argument("--suite", type=Path, help="批量：对目录下每个案例评分（配合 --gold）")
    parser.add_argument("--gold", action="store_true", help="使用案例自带的 gold/ 作为工作区")
    parser.add_argument("--gate", choices=("perfect",), help="达标门：perfect = 三项指标全满分")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    jobs: list[tuple[Path, Path]] = []
    if args.suite:
        for case_dir in sorted(p for p in args.suite.iterdir() if (p / "ground_truth.yaml").is_file()):
            jobs.append((case_dir, case_dir / "gold"))
    elif args.case:
        jobs.append((args.case, args.case / "gold" if args.gold else args.workspace))
    else:
        parser.error("需要 --case（或 --suite）")
    if not args.gold and args.workspace is None and not args.suite:
        parser.error("--case 模式需要 --workspace（或用 --gold 评参考解）")

    reports, failures = [], 0
    for case_dir, workspace in jobs:
        report, fatal = score_case(case_dir, workspace)
        if fatal:
            failures += 1
            print("\n".join(fatal), file=sys.stderr)
            if args.json:
                print(json.dumps({"case": case_dir.name, "fatal": fatal}, ensure_ascii=True))
            continue
        reports.append(report)
        if not args.json:
            c, f, j = report["citation"], report["features"], report["judgment"]
            print(f"■ {report['case']} ← {report['workspace']}")
            print(f"  引用准确性：precision={c['precision']}（{c['passed']}/{c['total']}）"
                  f"  coverage={c['coverage']}（期望引文 {c['expected_pairs']} 组）")
            if c["failed"]:
                for item in c["failed"][:6]:
                    print(f"    ✗ {item['owner']} {item['ref']}#{item['locator']}: {item['error']}")
            print(f"  特征遗漏：{len(f['omissions'])}/{f['total']}"
                  f"（{'、'.join(f['omissions']) or '无'}）")
            print(f"  误判率：{j['misjudgment_rate']}（{len(j['mismatches'])}/{j['points']} 判断点）")
            for m in j["mismatches"][:8]:
                print(f"    ✗ {m}")
            if report["validate"]["warnings"]:
                print(f"  （内核校验警告 {report['validate']['warnings']} 条，未阻断评分）")
            for n in report["notes"][:5]:
                print(f"  · {n}")
        if args.gate == "perfect" and not perfect(report):
            failures += 1

    if args.json:
        payload = [r for r in reports] or [{"fatal": "all cases failed"}]
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    if not args.json:
        print(f"\n结论：{len(reports) - failures}/{len(jobs)} 通过" +
              (f"（gate={args.gate}）" if args.gate else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
