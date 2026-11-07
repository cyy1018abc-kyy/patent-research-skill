#!/usr/bin/env python3
"""Leakage self-check for retrieval-benchmark suite manifests (Phase V / V1-5).

Hard checks (any violation = exit 1, evaluation invalid):

1. **query-family disjointness** — ``source_id`` (the topic's own query family)
   is globally unique: a query family never appears as a query in two splits;
2. **time monotonicity** — every train topic's ``time_split_key`` <= val topics'
   <= test topics', per the manifest ``time_split`` boundaries;
3. **id integrity** — ``topic_id`` unique + ``TP-\\d{4}`` shaped;
4. **empty-gold discipline** — zero-gold topics must carry
   ``gold_known_incomplete=true`` (they stay out of the recall denominator);
5. **mining-input purity** (roadmap 41A-3) — when ``--cooccurrence`` points at a
   mined table, its recorded mining input must be split-clean: only train/val
   splits declared, every consumed ``topic_id`` resolvable in the manifest, none
   of them a test topic. A test topic that entered the co-occurrence mining
   invalidates the evaluation exactly like a test query in training data.

Report-only (recorded in the manifest ``leakage_report``): gold families shared
across splits, and query families that also serve as gold targets. Both are
inherent fixed-corpus properties (a 2003 query family can be cited by a 2010
query) and leak nothing for unsupervised retrieval — test query TEXT never
enters train-side data; the counts are published for transparency.

``--inject <kind>`` corrupts a copy of the manifest (or, for kind
``cooccurrence``, of the mining table) deliberately so CI/tests can prove the
checker is not a rubber stamp.

Usage:
    python benchmarks/retrieval/check_leakage.py --manifest topics/public/manifest.json
    python benchmarks/retrieval/check_leakage.py --manifest topics/public/manifest.json \
        --cooccurrence topics/public/cooccurrence.json
    python benchmarks/retrieval/check_leakage.py --manifest ... --inject family
    python benchmarks/retrieval/check_leakage.py --manifest ... --cooccurrence ... --inject cooccurrence
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
MINING_SPLITS = ("train", "val")  # test-split data must never seed mining (roadmap 41A-3)


def cooccurrence_violations(manifest: dict, table: dict) -> list[str]:
    """Hard gate 5: the mined table's recorded mining input must be split-clean.

    The table records exactly what the miner consumed (``mining_input.splits`` /
    ``mining_input.topic_ids``); every topic id is resolved against the manifest
    and any test-split topic — or any unresolved/duplicated id — is a violation.
    A missing ``mining_input`` block fails closed: an unrecorded input cannot be
    proven clean.
    """
    problems: list[str] = []
    if not isinstance(table, dict) or not isinstance(table.get("mining_input"), dict):
        return ["挖掘产物缺少 mining_input 记录——无法证明挖掘输入未混入 test 主题（拒绝）"]
    mining_input = table["mining_input"]
    splits = mining_input.get("splits")
    if not isinstance(splits, list) or not splits:
        problems.append("mining_input.splits 缺失或为空（须显式声明 train/val）")
    else:
        for split in splits:
            if split not in MINING_SPLITS:
                problems.append(
                    f"挖掘 split {split!r} 不允许（仅 {list(MINING_SPLITS)}）——test 数据不得参与挖掘")
    split_of = {t.get("topic_id"): t.get("split") for t in manifest.get("topics", [])}
    topic_ids = mining_input.get("topic_ids")
    if not isinstance(topic_ids, list) or not topic_ids:
        problems.append("mining_input.topic_ids 缺失或为空（须记录全部被消费的主题）")
        return problems
    seen: set[str] = set()
    for tid in topic_ids:
        if not isinstance(tid, str) or not tid:
            problems.append(f"mining_input.topic_ids 含非法条目 {tid!r}")
            continue
        if tid in seen:
            problems.append(f"{tid}: 挖掘输入 topic_id 重复")
            continue
        seen.add(tid)
        split = split_of.get(tid)
        if split is None:
            problems.append(f"{tid}: 挖掘输入引用了 manifest 中不存在的主题")
            continue
        if split == "test":
            problems.append(f"{tid}: test 主题混入挖掘输入（硬门）")
            continue
        if isinstance(splits, list) and split not in splits:
            problems.append(f"{tid}: 主题 split {split!r} 未在声明挖掘 splits {splits} 内")
    return problems


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


def _inject(manifest: dict, kind: str, table: dict | None = None) -> dict | tuple[dict, dict]:
    broken = copy.deepcopy(manifest)
    topics = broken["topics"]
    if kind == "family":
        donor = next(t for t in topics if t["split"] == "train")
        victim = next(t for t in topics if t["split"] == "test")
        victim["source_id"] = donor["source_id"]  # 查询族跨 split 重复（硬门）
        return broken
    if kind == "time":
        ts = broken["time_split"]
        test_topic = next(t for t in topics if t["split"] == "test")
        test_topic[ts["key"]] = "1964-01-01T00:00:00"  # 早于 test_first_date（下界）
        return broken
    if kind == "empty_gold":
        victim = next(t for t in topics if t["split"] == "val")
        victim["gold_families"] = []
        victim.pop("gold_known_incomplete", None)
        return broken
    if kind == "cooccurrence":
        # 泄漏注入样例：test split 主题混入挖掘输入 —— 硬门必须拒绝
        if table is None:
            raise SystemExit("--inject cooccurrence 需要 --cooccurrence 指向挖掘产物")
        broken_table = copy.deepcopy(table)
        test_topic = next((t for t in topics if t.get("split") == "test"), None)
        if test_topic is None:
            raise SystemExit("manifest 无 test 主题，无法注入 cooccurrence 样例")
        mining_input = broken_table.setdefault("mining_input", {})
        mining_input["splits"] = ["train", "val"]  # 声明保持干净，让违规落在 topic 上
        ids = [i for i in (mining_input.get("topic_ids") or []) if i != test_topic["topic_id"]]
        ids.append(test_topic["topic_id"])
        mining_input["topic_ids"] = ids
        return broken, broken_table
    raise SystemExit(f"未知注入类型 {kind}（可选 family/time/empty_gold/cooccurrence）")


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
    parser.add_argument("--cooccurrence", type=Path, default=None,
                        help="挖掘产物（mine_cooccurrence.py 输出）——提供则加跑硬门 5：挖掘输入 split 纯度")
    parser.add_argument("--inject", choices=("family", "time", "empty_gold", "cooccurrence"),
                        help="注入违规用于自检（操作副本，不写盘）")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    table = None
    if args.cooccurrence is not None:
        try:
            table = json.loads(args.cooccurrence.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            print(f"[FAIL] 挖掘产物不可读/非法 JSON: {exc}", file=sys.stderr)
            return 1
    if args.inject:
        if args.inject == "cooccurrence":
            broken_manifest, broken_table = _inject(manifest, args.inject, table)
            found = cooccurrence_violations(broken_manifest, broken_table)
        else:
            broken_manifest = _inject(manifest, args.inject)
            found = violations(broken_manifest)
        if not found:
            print(f"[FAIL] 注入 {args.inject} 后未检出任何违规——检查器失效", file=sys.stderr)
            return 1
        print(f"[OK] 注入 {args.inject} 被正确检出（{len(found)} 条）——检查器有效")
        return 0
    found = violations(manifest) + (cooccurrence_violations(manifest, table) if table is not None else [])
    if found:
        print(f"[FAIL] 防泄漏自检：{len(found)} 条违规", file=sys.stderr)
        for p in found:
            print(f"  {p}", file=sys.stderr)
        return 1
    report = leakage_report(manifest)
    gates = "查询族/时间/ID/空 gold" + ("/挖掘输入纯度" if table is not None else "")
    print(f"[OK] 防泄漏自检 0 命中：{len(manifest['topics'])} 主题；硬门（{gates}）全过")
    print(f"[INFO] 固定语料透明报告：{json.dumps(report, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
