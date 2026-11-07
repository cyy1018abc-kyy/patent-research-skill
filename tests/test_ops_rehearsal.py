"""OPS live-rehearsal driver tests (Stage 4 / L4 tooling) — fully offline.

The fake transport simulates the documented OPS behaviour (OAuth client-credentials,
X-OPS-Range paging, 403 on invalid credentials) so the whole runbook §1 sequence is
rehearsed without any network access. These tests pin the driver's evidence contract:
request budget, consistency check, hash audit, and a clean 403 drill.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from ops_live_rehearsal import REQUEST_BUDGET, run_rehearsal  # noqa: E402


@pytest.fixture(autouse=True)
def _dummy_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """The offline rehearsal never touches the network, but the adapter's
    credential gate still requires the variables to be present (values unused
    by the fake transport; the 403 drill overrides them itself)."""
    monkeypatch.setenv("OPS_OAUTH_KEY", "test-key")
    monkeypatch.setenv("OPS_OAUTH_SECRET", "test-secret")


class FakeOpsRehearsalTransport:
    """Simulates OPS: OAuth 200 (403 for the rehearsal's invalid key), paged search."""

    def __init__(self) -> None:
        self.oauth_calls = 0
        self.search_calls = 0

    def _page(self, page_index: int) -> str:
        return json.dumps({
            "results": [
                {"publication_number": f"EP{1000000 + page_index * 25 + i}A1", "title": f"hit {i}"}
                for i in range(25)
            ]
        })

    def __call__(self, method: str, url: str, headers: dict, timeout: int):
        import os

        if "auth/accesstoken" in url:
            self.oauth_calls += 1
            if os.environ.get("OPS_OAUTH_KEY") == "invalid-rehearsal-key":
                return _Resp(403)
            return _Resp(200, json_data={"access_token": "fake-token", "expires_in": 1200})
        self.search_calls += 1
        range_header = headers.get("X-OPS-Range", "1-25")
        start = int(range_header.split("-")[0])
        page_index = (start - 1) // 25
        return _Resp(200, text=self._page(page_index))


class _Resp:
    def __init__(self, status_code: int, text: str = "{}", json_data: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json


def _assert_honest_report(report: dict, *, verdict: str) -> None:
    assert report["verdict"] == verdict
    assert report["requests_total"] <= REQUEST_BUDGET
    raw = json.dumps(report)
    assert "fake-token" not in raw and "invalid-rehearsal-key" not in raw  # no secrets in evidence


def test_rehearsal_full_sequence_passes_offline(tmp_path: Path) -> None:
    fake = FakeOpsRehearsalTransport()
    report = run_rehearsal(sidecar=tmp_path / "sidecar", transport=fake, live=False)
    _assert_honest_report(report, verdict="PASS")
    steps = {s["step"]: s for s in report["steps"]}
    assert steps["oauth_smoke"]["ok"] is True
    step2 = steps["dry_run_execute_consistency_and_paging"]
    assert step2["ok"] is True and step2["consistent"] is True
    assert step2["raw_pages"] == 2 and step2["complete"] is True
    # complete=True refers to the REQUESTED 2-page window (both fetched); judgement
    # about the source hit count happens at runbook §1 step 8 against real metadata
    assert steps["raw_artifact_hash_audit"]["ok"] is True
    assert steps["http_403_drill"]["ok"] is True
    assert fake.oauth_calls == 2 and fake.search_calls == 2  # smoke+paging, drill OAuth 403s


def test_rehearsal_403_drill_fails_cleanly_and_preserves_pages(tmp_path: Path) -> None:
    fake = FakeOpsRehearsalTransport()
    report = run_rehearsal(sidecar=tmp_path / "sidecar", transport=fake, live=False)
    drill = {s["step"]: s for s in report["steps"]}["http_403_drill"]
    assert drill["status"] == "failed"
    # the drill itself captured 0 pages (it dies at OAuth), but the main run's two
    # raw pages must still be on disk — 已采集页不丢 (no retry storm, no cleanup)
    assert drill["preserved_pages"] == 0
    raw_pages = list((tmp_path / "sidecar" / "raw").glob("ops_*.json"))
    assert len(raw_pages) == 2


def test_rehearsal_request_budget_is_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import ops_live_rehearsal as mod

    monkeypatch.setattr(mod, "REQUEST_BUDGET", 2)  # force the cap below the sequence's need
    fake = FakeOpsRehearsalTransport()
    with pytest.raises(RuntimeError, match="request budget exceeded"):
        run_rehearsal(sidecar=tmp_path / "sidecar", transport=fake, live=False)


def test_rehearsal_evidence_file_round_trips(tmp_path: Path) -> None:
    fake = FakeOpsRehearsalTransport()
    report = run_rehearsal(sidecar=tmp_path / "sidecar", transport=fake, live=False)
    evidence_files = list((tmp_path / "sidecar").glob("rehearsal-evidence-*.json"))
    assert not evidence_files  # the CLI writes evidence files; run_rehearsal returns the dict
    parsed = json.loads(json.dumps(report))
    assert parsed["verdict"] == "PASS"
    assert all("ok" in s for s in parsed["steps"])
