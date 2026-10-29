#!/usr/bin/env python3
"""EX-01 annotation agreement tool (Phase V / V2-3): Cohen's kappa, disagreement
export, qrels builder.

Worksheets are utf-8-sig CSV with EXACTLY these columns (protocol §3):
    topic_id,doc_id,relevance,rationale,reviewer,reviewed_at

* ``relevance`` ∈ {0,1,2} or blank (blank = "not assessed"; excluded from kappa
  and from qrels, protocol §3.3);
* rows are joined on (topic_id, doc_id); entries present in only one reviewer's
  sheet are unpaired — counted and excluded from kappa;
* kappa: Cohen's, overall + per-topic; the gate (>= 0.7) lives in
  docs/annotation-protocol.md §3.5 — a low kappa means MORE calibration, never
  looser labels.

Usage:
    python tools/annotation_agreement.py --sheets a.csv b.csv --kappa
    python tools/annotation_agreement.py --sheets a.csv b.csv --export-disagreements out.csv
    python tools/annotation_agreement.py --sheets a.csv b.csv --arbitrated arb.csv \
        --qrels-version private-qrels-2026-11-01 --as-of 2026-11-01 --out gold/qrels.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

COLUMNS = ("topic_id", "doc_id", "relevance", "rationale", "reviewer", "reviewed_at")
VALID_LEVELS = {"0", "1", "2"}


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def load_sheet(path: Path) -> tuple[list[str], dict[tuple[str, str], dict]]:
    """Return (column headers, {(topic_id, doc_id): row}) with column validation."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or tuple(reader.fieldnames) != COLUMNS:
            raise SystemExit(
                f"{path}: 列名必须是 {list(COLUMNS)}，实际 {reader.fieldnames}（协议 §3.1 列冻结）")
        rows = {}
        for n, row in enumerate(reader, start=2):
            key = (row["topic_id"].strip(), row["doc_id"].strip())
            if not key[0] or not key[1]:
                raise SystemExit(f"{path}:{n}: topic_id/doc_id 不得为空")
            rel = row["relevance"].strip()
            if rel and rel not in VALID_LEVELS:
                raise SystemExit(f"{path}:{n}: relevance 必须是 0/1/2 或空白（未评估），实际 {rel!r}")
            if key in rows:
                raise SystemExit(f"{path}:{n}: (topic_id, doc_id) 重复 {key}")
            row["relevance"] = rel
            rows[key] = row
    return COLUMNS, rows


def paired_labels(sheets: dict[Path, dict[tuple[str, str], dict]]):
    """Join sheets on (topic_id, doc_id); return {(topic,doc): [labels…]}, unpaired count."""
    keys: set[tuple[str, str]] = set()
    for rows in sheets.values():
        keys.update(k for k, row in rows.items() if row["relevance"])
    labels: dict[tuple[str, str], list[str]] = {}
    unpaired = 0
    for key in sorted(keys):
        vals = [sheets[p][key]["relevance"] for p in sheets if key in sheets[p] and sheets[p][key]["relevance"]]
        if len(vals) < len(sheets):
            unpaired += 1
            continue
        labels[key] = vals
    return labels, unpaired


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa over (reviewer_1, reviewer_2) label pairs (None if degenerate)."""
    if len(pairs) < 2:
        return None
    labels_1 = [p[0] for p in pairs]
    labels_2 = [p[1] for p in pairs]
    categories = sorted(set(labels_1) | set(labels_2))
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum(
        (sum(1 for x in labels_1 if x == cat) / n) * (sum(1 for x in labels_2 if x == cat) / n)
        for cat in categories
    )
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def collect() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheets", nargs="+", required=True, type=Path, help="≥2 份评审工作表")
    parser.add_argument("--kappa", action="store_true", help="输出整体与逐主题 Cohen's κ")
    parser.add_argument("--kappa-gate", type=float, default=0.7, help="一致性门（协议 §3.5）")
    parser.add_argument("--export-disagreements", type=Path, help="导出分歧行（喂仲裁表）")
    parser.add_argument("--arbitrated", type=Path, help="仲裁后终表（与 --sheets 同列）")
    parser.add_argument("--qrels-version", default="")
    parser.add_argument("--as-of", default="", help="Gold 适用日期（ISO）")
    parser.add_argument("--source", default="private expert topics (EX-01)", help="Gold 来源说明")
    parser.add_argument("--out", type=Path, help="qrels 输出路径（与 --arbitrated 同用）")
    args = parser.parse_args()
    _pin_utf8_stdio()
    if args.kappa and len(args.sheets) != 2:
        raise SystemExit("--kappa 需要恰好 2 份工作表（协议：≥2 评审）")
    return args


def main() -> int:
    args = collect()
    sheets = {}
    for path in args.sheets:
        _, rows = load_sheet(path)
        sheets[path] = rows
    labels, unpaired = paired_labels(sheets)
    print(f"[sheets] {len(sheets)} 份，有效配对 {len(labels)} 条，单侧未配对 {unpaired} 条（不计 κ/gold）")
    exit_code = 0

    if args.kappa:
        by_topic: dict[str, list[str]] = {}
        for (tid, _doc), pair in labels.items():
            by_topic.setdefault(tid, []).extend(pair)
        per_topic = {tid: cohen_kappa(pair_groups) for tid, pair_groups in
                     _group_pairs(labels).items()}
        overall = cohen_kappa(list(labels.values()))
        print(f"[kappa] overall = {overall:.4f}（门 ≥ {args.kappa_gate}）")
        low = []
        for tid in sorted(per_topic):
            k = per_topic[tid]
            if k is None:
                print(f"  {tid}: n/a（该主题有效配对不足或类别单一）")
                continue
            mark = "" if k >= args.kappa_gate else "  ← 低于门"
            if k < args.kappa_gate:
                low.append(tid)
            print(f"  {tid}: κ={k:.4f}{mark}")
        if overall is not None and overall < args.kappa_gate:
            print(f"[FAIL] overall κ < {args.kappa_gate}：触发校准轮（协议 §3.5，不得降标）", file=sys.stderr)
            exit_code = 1
        if low:
            print(f"[WARN] {len(low)} 个主题低于门：{' '.join(low)}（进入仲裁重点复核）")

    if args.export_disagreements:
        diffs = [
            {"topic_id": k[0], "doc_id": k[1],
             **{f"label_{i + 1}": v for i, v in enumerate(pair)}}
            for k, pair in labels.items() if len(set(pair)) > 1
        ]
        with open(args.export_disagreements, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["topic_id", "doc_id", "label_1", "label_2"])
            writer.writeheader()
            writer.writerows(diffs)
        print(f"[disagreements] {len(diffs)} 条 -> {args.export_disagreements}")

    if args.arbitrated:
        if not args.out or not args.qrels_version or not args.as_of:
            raise SystemExit("--arbitrated 需要 --out + --qrels-version + --as-of 同用")
        _, final = load_sheet(args.arbitrated)
        qrels: dict[str, dict[str, int]] = {}
        blanks = 0
        for (tid, doc), row in final.items():
            rel = row["relevance"]
            if not rel:
                blanks += 1
                continue
            qrels.setdefault(tid, {})[doc] = int(rel)
        doc_out = {
            "qrels_version": args.qrels_version,
            "as_of": args.as_of,
            "source": args.source,
            "gold_known_incomplete": True,
            "labels": qrels,
        }
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(doc_out, ensure_ascii=False, indent=1) + "\n")
        print(f"[qrels] {sum(len(v) for v in qrels.values())} 条标签 / {len(qrels)} 主题 "
              f"（blank 未评估 {blanks} 条已排除）-> {args.out}")
    return exit_code


def _group_pairs(labels: dict[tuple[str, str], list[str]]) -> dict[str, list[list[str]]]:
    grouped: dict[str, list[list[str]]] = {}
    for (tid, _doc), pair in labels.items():
        grouped.setdefault(tid, []).append(pair)
    return grouped


if __name__ == "__main__":
    sys.exit(main())
