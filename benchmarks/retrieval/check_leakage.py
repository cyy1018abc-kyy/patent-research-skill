#!/usr/bin/env python3
"""Leakage self-check for retrieval-benchmark suite manifests (Phase V / V1-5).

Hard checks (any violation = exit 1, evaluation invalid):

1. **query-family disjointness** — ``source_id`` (the topic's own query family)
   is globally unique: a query family never appears as a query in two splits;
2. **time monotonicity** — every train topic's ``time_split_key`` <= val topics'
   <= test topics', per the manifest ``time_split`` boundaries;
3. **id integrity** — ``topic_id`` unique + ``TP-\\d{4}`` shaped;
4. **empty-gold discipline** — zero-gold topics must carry
   ``gold_known_incomplete=true`` (they stay out of the recall denominator).

Report-only (recorded in the manifest ``leakage_report``): gold families shared
across splits, and query families that also serve as gold targets. Both are
inherent fixed-corpus properties (a 2003 query family can be cited by a 2010
query) and leak nothing for unsupervised retrieval — test query TEXT never
enters train-side data; the counts are published for transparency.

``--inject <kind>`` corrupts a copy of the manifest deliberately so CI/tests can
prove the checker is not a rubber stamp.

Usage:
    python benchmarks/retrieval/check_leakage.py --manifest topics/public/manifest.json
    python benchmarks/retrieval/check_leakage.py --manifest ... --inject family
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

TP_RE = re.compile(r"^TP-[0-9]{4}$")
ORDER = {"train": 0, "val": 1, "test": 2}


def violations(manifest: dict) -> list[str]:
    problems: list[str] = []
    topics = manifest.get("topics", [])

    seen_tp: dict[str, str] = {}
    query_family: dict[str, str] = {}  # source_id -> topic_id
    gold_split: dict[str, str] = {}  # family -> earliest split it is gold of
    cross_split_gold = 0
    for topic in topics:
        tid = topic.get("topic_id", "")
        if not TP_RE.match(tid):
            problems.append(f"{tid}: topic_id 不符合 TP-####")
        elif tid in seen_tp:
            problems.append(f"{tid}: topic_id 重复（与 {seen_tp[tid]}）")
        else:
            seen_tp[tid] = tid
        src = topic.get("source_id")
        if src is None:
            problems.append(f"{tid}: 缺 source_id（查询族不跨 split 的硬门依据）")
        elif src in query_family:
            problems.append(f"{tid}: 查询族 {src} 跨 split 重复（与 {query_family[src]}）")
        else:
            query_family[src] = tid
        split = topic.get("split", "")
        if split not in ORDER:
            problems.append(f"{tid}: 非法 split {split!r}")
            continue
        for fam in topic.get("gold_families", []):
            if fam in gold_split and gold_split[fam] != split:
                cross_split_gold += 1
            gold_split.setdefault(fam, split)
        if not topic.get("gold_families") and not topic.get("gold_known_incomplete"):
            problems.append(f"{tid}: 空 gold 但未标 gold_known_incomplete")

    ts = manifest.get("time_split")
    if ts:
        key = ts.get("key", "time_split_key")
        # 上界字段：split 内不得晚于边界；下界字段（test_first_date）：不得早于边界
        bounds = [("train_last_date", "train", "upper"), ("val_last_date", "val", "upper"),
                  ("test_first_date", "test", "lower")]
        for field, split, direction in bounds:
            limit = ts.get(field)
            if not limit:
                continue
            for topic in topics:
                if topic.get("split") == split:
                    day = str(topic.get(key) or topic.get("time_split_key") or "")[:10]
                    if not day:
                        continue
                    crossed = day > limit[:10] if direction == "upper" else day < limit[:10]
                    if crossed:
                        problems.append(
                            f"{topic.get('topic_id')}: {split} 主题日期 {day} "
                            f"{'晚于' if direction == 'upper' else '早于'}边界 {limit[:10]}（{field}）")
    return problems


def leakage_report(manifest: dict) -> dict:
    """Fixed-corpus transparency counters (not failures)."""
    topics = manifest.get("topics", [])
    gold_split: dict[str, set[str]] = {}
    queries: set[str] = set()
    for topic in topics:
        queries.add(topic.get("source_id") or "")
        for fam in topic.get("gold_families", []):
            gold_split.setdefault(fam, set()).add(topic["split"])
    shared = [f for f, splits in gold_split.items() if len(splits) > 1]
    return {
        "note": "fixed-corpus benchmark: gold families shared across splits are expected; query families are disjoint (hard checks)",
        "gold_families_total": len(gold_split),
        "gold_families_in_multiple_splits": len(shared),
        "query_families_also_gold": len(queries & set(gold_split)),
    }


def _inject(manifest: dict, kind: str) -> dict:
    broken = copy.deepcopy(manifest)
    topics = broken["topics"]
    if kind == "family":
        donor = next(t for t in topics if t["split"] == "train")
        victim = next(t for t in topics if t["split"] == "test")
        victim["source_id"] = donor["source_id"]  # 查询族跨 split 重复（硬门）
    elif kind == "time":
        ts = broken["time_split"]
        test_topic = next(t for t in topics if t["split"] == "test")
        test_topic[ts["key"]] = "1964-01-01T00:00:00"  # 早于 test_first_date（下界）
    elif kind == "empty_gold":
        victim = next(t for t in topics if t["split"] == "val")
        victim["gold_families"] = []
        victim.pop("gold_known_incomplete", None)
    else:
        raise SystemExit(f"未知注入类型 {kind}（可选 family/time/empty_gold）")
    return broken


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inject", choices=("family", "time", "empty_gold"), help="注入违规用于自检（操作副本，不写盘）")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.inject:
        manifest = _inject(manifest, args.inject)
        found = violations(manifest)
        if not found:
            print(f"[FAIL] 注入 {args.inject} 后未检出任何违规——检查器失效", file=sys.stderr)
            return 1
        print(f"[OK] 注入 {args.inject} 被正确检出（{len(found)} 条）——检查器有效")
        return 0
    found = violations(manifest)
    if found:
        print(f"[FAIL] 防泄漏自检：{len(found)} 条违规", file=sys.stderr)
        for p in found:
            print(f"  {p}", file=sys.stderr)
        return 1
    report = leakage_report(manifest)
    print(f"[OK] 防泄漏自检 0 命中：{len(manifest['topics'])} 主题；硬门（查询族/时间/ID/空 gold）全过")
    print(f"[INFO] 固定语料透明报告：{json.dumps(report, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
