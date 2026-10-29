"""Cross-layer integration tests (blueprint §11 IT-01/IT-02/IT-03/IT-07).

IT-01/04  extension active around a kernel workspace leaves kernel `check` output
          byte-identical (normalized timestamps); sidecar removal changes nothing.
IT-02     synthetic OPS XML goes through the KERNEL's own ingest → verified comes
          from the kernel, never from the extension.
IT-03     candidate → document anchor → projection → coverage matrix → claim chart
          → amendment proposal: the whole chain stays proposal-only and writes
          nothing into kernel workspace directories.
IT-07     UTF-8/Chinese paths/timezone discipline on Windows.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD = REPO_ROOT / "benchmarks" / "cases" / "bm01-timesync" / "gold"
XML_FIXTURE = REPO_ROOT / "extensions" / "patent_intel" / "tests" / "fixtures" / "documents" / "sample_exchange.xml"


def _kernel_check(ws: Path) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "patentkit", "check", "--json"],
        cwd=str(ws), capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
    )
    assert proc.returncode in (0, 1, 2), proc.stderr[:500]
    return re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)", "<TS>", proc.stdout)


def _kernel_dir_inventory(ws: Path) -> set[str]:
    """Relative paths inside kernel-owned directories (00_… to 07_…)."""
    out: set[str] = set()
    for d in ws.iterdir():
        if d.is_dir() and re.match(r"0\d_", d.name):
            for p in d.rglob("*"):
                out.add(str(p.relative_to(ws)).replace("\\", "/"))
    return out


def test_it01_it04_extension_around_kernel_is_invisible(tmp_path: Path) -> None:
    from patent_intel.cli import main

    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)
    baseline = _kernel_check(ws)

    state = tmp_path / "sidecar"
    sidecar_dir = str(ws / ".patent-intel")
    assert main(["recall", "report", "--root", str(ws), "--json", "--state-dir", sidecar_dir]) == 0
    assert main(["evidence", "build", "--root", str(ws), "--json", "--state-dir", sidecar_dir]) == 0
    assert main(["landscape", "report", "--root", str(ws), "--json", "--state-dir", sidecar_dir]) == 0

    assert _kernel_check(ws) == baseline, "kernel check changed while the extension was active"
    # sidecar carries everything the extension wrote
    assert (ws / ".patent-intel" / "reports").is_dir()
    assert (ws / ".patent-intel" / "evidence" / "projections.json").is_file()
    shutil.rmtree(ws / ".patent-intel")
    assert _kernel_check(ws) == baseline, "kernel check changed after sidecar removal"


def test_it02_kernel_ingest_of_ops_xml_produces_verified(tmp_path: Path) -> None:
    """IT-02: the extension may NOT set verified; the kernel's ingest does."""
    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)
    raw_dir = ws / "02_search_logs" / "raw"
    xml_bytes = XML_FIXTURE.read_bytes()
    (raw_dir / "ops_synthetic_page-1.xml").write_bytes(xml_bytes)
    log = {
        "db": "espacenet",
        "target": "TGT-9001",
        "actor": "it-test",
        "capture_mode": "live",
        "timestamp": "2026-02-05T08:00:00+00:00",
        "query": {"id": "N1", "axis": "N1@TGT-9001", "text": "ops synthetic ingest"},
        "result": {"hit_count": 1, "raw_export": "raw/ops_synthetic_page-1.xml", "complete": True},
    }
    (ws / "02_search_logs" / "espacenet_2026-02-05_N1_9.log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    proc = subprocess.run(
        [sys.executable, "-m", "patentkit", "ingest",
         "--log", "espacenet_2026-02-05_N1_9.log.json",
         "--raw", "02_search_logs/raw/ops_synthetic_page-1.xml",
         "--apply"],
        cwd=str(ws), capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
    )
    assert proc.returncode == 0, f"kernel ingest failed: {proc.stdout[-800:]} {proc.stderr[-800:]}"
    candidates = list((ws / "03_candidates").glob("P-*.json"))
    new_candidates = [c for c in candidates if "119000001" in c.name.lower() or "cn119" in c.read_text(encoding="utf-8").lower()]
    assert new_candidates, "kernel ingest should create a candidate from the OPS XML"
    data = json.loads(new_candidates[0].read_text(encoding="utf-8"))
    assert data["evidence_level"] == "verified"  # graded by the kernel, from the raw artifact


def test_it03_advisory_chain_is_proposal_only(tmp_path: Path) -> None:
    from patent_intel.advisory.amendment_proposal import build_amendment_proposal
    from patent_intel.advisory.claim_chart import build_claim_chart
    from patent_intel.documents.claims import parse_claim_dependencies
    from patent_intel.documents.locators import make_anchor
    from patent_intel.documents.patent_xml import parse_patent_xml
    from patent_intel.evidence.coverage_matrix import build_coverage_matrix
    from patent_intel.evidence.graph import EvidenceGraphBuilder
    from patent_intel.kernel_bridge import read_candidates

    ws = tmp_path / "ws"
    shutil.copytree(GOLD, ws)
    before = _kernel_dir_inventory(ws)

    doc = parse_patent_xml(XML_FIXTURE, source_document="02_search_logs/raw/ops_synthetic_page-1.xml")
    parse_claim_dependencies(doc)
    anchor = make_anchor(doc, "0012", quote="MAC层打戳")

    features = [{"feature_id": "FEAT-N1-001", "statement": "信标发送时刻估计", "axis_id": "N1@TGT-9001"}]
    projections = EvidenceGraphBuilder(features=features, built_at="2026-10-28T00:00:00+00:00").build_from_workspace(ws)
    candidates = read_candidates(ws)
    matrix = build_coverage_matrix(features, candidates, projections)
    chart = build_claim_chart(doc, matrix, candidates)
    candidate_ids = {str(c["id"]) for c in candidates}
    proposal = build_amendment_proposal(
        proposal_id="AP-IT-001",
        claims=[{"number": c.number, "text": c.text} for c in doc.claims],
        change_kind="claim_amendment",
        change_payload={"text": "…其特征在于，在MAC子层打发送时刻戳", "claim_numbers": [1, 2]},
        projections=projections,
        known_candidate_ids=candidate_ids,
    )

    assert anchor.verification_status == "machine_parsed"
    assert proposal.requires_human_review is True
    assert "draft audit" in (proposal.kernel_gate_ref or "")
    assert chart.describe()["combination_hypothesis"] in (True, False)
    # the chain wrote nothing into kernel directories
    assert _kernel_dir_inventory(ws) == before


def test_it07_utf8_chinese_paths_and_timezone(tmp_path: Path) -> None:
    """IT-07: 中文+空格路径、UTF-8 输出、ISO-8601 UTC 时间戳。"""
    from patent_intel.cli import main

    weird = tmp_path / "专利 调研 工作区"
    weird.mkdir()
    ws = weird / "ws"
    shutil.copytree(GOLD, ws)
    state = weird / "side car"
    code = main(["recall", "report", "--root", str(ws), "--json", "--state-dir", str(state)])
    assert code == 0
    reports = list((state / "reports").glob("recall_*.json"))
    assert reports
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert payload["axes"], "glossary axes must survive CJK paths"
    # contracts: every record timestamp is ISO-8601 UTC
    from patent_intel.contracts import QuerySpec, utc_now_iso

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", utc_now_iso())
    spec = QuerySpec(
        owner="WP-A", query_id="Q-T", axis_id="N1@T", terms=["信标"], language="zh",
        query_type="single_feature", source="multi",
    )
    assert spec.to_dict()["created_at"].endswith("+00:00")
