"""Landscape report rendering (blueprint E-03): local CSV/Markdown, offline, zero JS.

Reports are descriptive over the searched sample and always carry the boundary
statement; they are written to the sidecar reports/ directory.
"""

from __future__ import annotations

import csv
import io
import time
from pathlib import Path
from typing import Any

from patent_intel.io.safe_io import write_text_atomic
from patent_intel.landscape.aggregation import LandscapeStats, aggregate_landscape
from patent_intel.landscape.trends import trend_by_axis, trend_by_year

__all__ = ["build_landscape_report"]

_OWNER = "WP-E"

_BOUNDARY = (
    "边界声明：本报告只统计已检索样本；聚类稀疏或零命中不能证明技术空白，"
    "更不能得出可授权结论。家族计数与文献计数分开；未知家族未做合并。"
)


def build_landscape_report(records: list[dict[str, Any]], state_dir: Path) -> dict[str, str]:
    """Build CSV + Markdown landscape reports; returns written paths."""
    stats: LandscapeStats = aggregate_landscape(records)
    years = trend_by_year(records)
    axes = trend_by_axis(records)

    state_dir = Path(state_dir)
    out_dir = state_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")

    # -- CSV ------------------------------------------------------------
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["dimension", "value", "families", "documents", "unknown_family_docs"])
    for dimension, table in (("applicant", stats.by_applicant), ("class", stats.by_class), ("region", stats.by_region)):
        for value, cell in sorted(table.items()):
            writer.writerow([dimension, value, cell["families"], cell["documents"], cell["unknown_family_docs"]])
    for year, count in years["by_year"].items():
        writer.writerow(["year", year, "", count, ""])
    for axis, count in axes["by_axis"].items():
        writer.writerow(["axis", axis, "", count, ""])
    csv_path = out_dir / f"landscape_{stamp}.csv"
    write_text_atomic(csv_path, buf.getvalue())

    # -- Markdown -------------------------------------------------------
    lines: list[str] = [
        "# 专利技术态势报告（描述性统计）",
        "",
        f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 样本文献数：{stats.totals.get('documents', 0)}（家族组内 {stats.totals.get('family_group_docs', 0)}，未知家族 {stats.totals.get('unknown_family_docs', 0)}）",
        f"- 年份缺失占比：{years['missing_year_share']:.1%}",
        "",
        _BOUNDARY,
        "",
        "## 申请人（家族/文献分开计）",
        "",
        "| 申请人 | 家族数 | 文献数 | 其中未知家族文献 |",
        "|---|---:|---:|---:|",
    ]
    for value, cell in sorted(stats.by_applicant.items(), key=lambda kv: -kv[1]["documents"])[:20]:
        lines.append(f"| {value} | {cell['families']} | {cell['documents']} | {cell['unknown_family_docs']} |")
    lines += ["", "## 年度趋势（样本内）", "", "| 年份 | 文献数 |", "|---|---:|"]
    for year, count in years["by_year"].items():
        lines.append(f"| {year} | {count} |")
    lines += ["", "## 技术轴分布", "", "| 轴 | 文献数 |", "|---|---:|"]
    for axis, count in axes["by_axis"].items():
        lines.append(f"| {axis} | {count} |")
    if axes["documents_without_axis"]:
        lines.append(f"\n（{axes['documents_without_axis']} 篇文献未标注技术轴）")
    md_path = out_dir / f"landscape_{stamp}.md"
    write_text_atomic(md_path, "\n".join(lines) + "\n")

    return {"csv": str(csv_path), "markdown": str(md_path)}
