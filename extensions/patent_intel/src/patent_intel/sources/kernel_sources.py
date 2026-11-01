"""Adapters that drive the kernel's own fetch commands (blueprint B-02).

The kernel already owns the acquisition contract: `fetch-cnipa` / `fetch-crossref`
write the raw artifact under ``02_search_logs/raw/`` plus the ``.log.json`` with
``capture_mode: live`` and honest ``result.complete``. These adapters **reuse** that
path via subprocess — they never write kernel files themselves — then read back the
newly created logs (read-only) to build :class:`SearchRun` records whose
``hits_reported`` / ``records_fetched`` mirror what the kernel recorded.

Acquisition verbs are a *separate* allowlist from the analysis verbs in
``kernel_allowlist``: they legitimately cause kernel-side writes (that is the
sanctioned way raw artifacts come into existence), so they are double-gated by
``SourceAdapter.ensure_live_allowed`` (config consent + per-command flag).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from patent_intel.contracts import QuerySpec, SearchRun
from patent_intel.kernel_allowlist import FORBIDDEN_FLAGS
from patent_intel.sources.base import (
    AcquisitionResult,
    Capability,
    CapabilityError,
    DryRunResult,
    NetworkNotConfirmed,
    RequestPlan,
    SourceAdapter,
)
from patent_intel.sources.normalize import normalize_doi, normalize_publication_number
from patent_intel.sources.registry import register_source

__all__ = ["KernelFetchAdapter", "CnipaAdapter", "CrossrefAdapter", "ACQUISITION_VERBS"]

#: Kernel verbs that write raw artifacts + logs. Only this module may dispatch them.
ACQUISITION_VERBS = frozenset({"fetch-cnipa", "fetch-crossref", "fetch-bigquery"})


class KernelFetchAdapter(SourceAdapter):
    """Base for sources implemented by kernel fetch commands."""

    kernel_verb: str = ""
    #: mapping of QuerySpec.filter/field names → kernel CLI flag builders
    field_flags: dict[str, str] = {}
    #: flag the kernel uses to actually acquire (vs preview); e.g. --apply
    apply_flag: str = "--apply"
    #: extra flags always passed (e.g. --json is NOT supported by fetch verbs; keep off)
    base_args: tuple[str, ...] = ()

    def capabilities(self) -> Capability:  # pragma: no cover - overridden
        raise NotImplementedError

    def build_request(self, query: QuerySpec) -> RequestPlan:
        self.ensure_query_supported(query)
        args: list[str] = [self.kernel_verb, *self.base_args]
        used_fields: list[str] = []
        for field_name, flag in self.field_flags.items():
            value = None
            if field_name == "keywords":
                value = " ".join(query.terms)
            else:
                value = (query.filters or {}).get(field_name)
            if value:
                args += [flag, str(value)]
                used_fields.append(field_name)
        if not used_fields:
            raise CapabilityError(
                f"query {query.query_id} has no field usable by source {self.id!r} "
                f"(usable fields: {sorted(self.field_flags)})"
            )
        # axis is mandatory in kernel fetch commands (log naming contract)
        axis = query.axis_id.split("@")[0] if "@" in query.axis_id else query.axis_id
        args += ["--axis", axis]
        summary = f"{self.kernel_verb} " + " ".join(f"{f}=<…>" for f in used_fields)
        return RequestPlan(
            source=self.id,
            query_id=query.query_id,
            verb=self.kernel_verb,
            args=args,
            summary=summary,
            live=True,
        )

    def _run_kernel(self, args: list[str], workspace: Path, timeout: int = 300) -> dict[str, Any]:
        """Dispatch the acquisition verb to the kernel CLI. Guardrails enforced here."""
        if not args or args[0] not in ACQUISITION_VERBS:
            raise CapabilityError(f"{args[:1]!r} is not an acquisition verb of this adapter")
        for flag in FORBIDDEN_FLAGS - {self.apply_flag}:
            if flag in args:
                raise CapabilityError(f"flag {flag!r} is refused in acquisition calls")
        if self.apply_flag not in args:
            raise CapabilityError(
                f"acquisition requires {self.apply_flag} so the kernel writes raw+log evidence"
            )
        cmd = [sys.executable, "-m", "patentkit", *args]
        proc = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"kernel {self.kernel_verb} exited {proc.returncode}: {proc.stderr.strip()[:2000]}"
            )
        return {"stdout": proc.stdout, "stderr": proc.stderr}

    def dry_run(self, plan: RequestPlan, workspace: Any) -> DryRunResult:
        """Preview without --apply: kernel prints the request; nothing is written."""
        preview_args = [a for a in plan.args if a != self.apply_flag]
        proc = subprocess.run(
            [sys.executable, "-m", "patentkit", *preview_args],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
            check=False,
        )
        notes = []
        if proc.returncode != 0:
            notes.append(f"kernel preview exited {proc.returncode}: {proc.stderr.strip()[:500]}")
        return DryRunResult(plan=plan, preview=[proc.stdout.strip() or plan.summary], notes=notes)

    def execute(
        self,
        plan: RequestPlan,
        workspace: Any,
        *,
        confirm_network: bool,
        config: Any,
    ) -> AcquisitionResult:
        self.ensure_live_allowed(confirm_network=confirm_network, config=config)
        workspace_path = Path(workspace)
        before = self._snapshot_logs(workspace_path)
        result = self._run_kernel(list(plan.args), workspace_path)
        after = self._snapshot_logs(workspace_path)
        new_logs = [p for p in after if p not in before]
        return self._collect(plan, workspace_path, new_logs, result)

    # -- helpers -------------------------------------------------------

    def _snapshot_logs(self, workspace: Path) -> dict[Path, tuple[float, int]]:
        logs = workspace / "02_search_logs"
        snap: dict[Path, tuple[float, int]] = {}
        if logs.is_dir():
            for p in logs.glob("*.log.json"):
                st = p.stat()
                snap[p] = (st.st_mtime, st.st_size)
        return snap

    def _collect(
        self,
        plan: RequestPlan,
        workspace: Path,
        new_logs: list[Path],
        raw_result: dict[str, Any],
    ) -> AcquisitionResult:
        out = AcquisitionResult()
        normalized_total: int | None = None
        for log_path in new_logs:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            result_block = data.get("result") or {}
            hits = result_block.get("hit_count")
            complete = result_block.get("complete")
            raw_export = result_block.get("raw_export")
            records = self._iter_raw_records(workspace, raw_export)
            normalized = self._count_normalized(records)
            if normalized is not None:
                normalized_total = (normalized_total or 0) + normalized
            run = SearchRun(
                owner="WP-B",
                run_id=f"{plan.source}:{log_path.stem}",
                query_id=plan.query_id,
                source=plan.source,
                executed_at=str(data.get("timestamp") or ""),
                status="complete" if complete is True else "partial",
                hits_reported=hits if isinstance(hits, int) else None,
                # kernel fetch commands take the first page(s) only:
                records_fetched=self._fetched_count(workspace, raw_export),
                complete=complete if isinstance(complete, bool) else None,
                incomplete_reason=str(data.get("capture_incomplete_reason") or "")
                or (None if complete is True else "unknown"),
                artifact_refs=[{"log": str(log_path), "raw_export": raw_export}],
            )
            out.runs.append(run)
            if raw_export:
                raw_path = (workspace / "02_search_logs" / raw_export).resolve()
                if raw_path.is_file():
                    out.raw_refs.append(
                        {
                            "path": str(raw_path.relative_to(workspace)),
                            "bytes": raw_path.stat().st_size,
                            "source": plan.source,
                        }
                    )
            out.log_paths.append(str(log_path))
        if not out.runs:
            raise RuntimeError(
                f"kernel {self.kernel_verb} produced no new search log; "
                f"stdout was: {raw_result.get('stdout', '')[:500]!r}"
            )
        out.records_normalized = normalized_total
        return out

    def _iter_raw_records(self, workspace: Path, raw_export: str | None) -> list[dict[str, Any]] | None:
        """Parse the raw artifact into record dicts.

        Returns ``None`` when the artifact is missing or unreadable (unknown — never
        fabricated as zero), a list of row dicts otherwise (possibly empty).
        """
        if not raw_export:
            return None
        raw_path = workspace / "02_search_logs" / raw_export
        if not raw_path.is_file():
            return None
        try:
            if raw_path.suffix == ".json":
                data = json.loads(raw_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [row for row in data if isinstance(row, dict)]
                if isinstance(data, dict):
                    items = data.get("items") or data.get("results") or data.get("records")
                    if isinstance(items, list):
                        return [row for row in items if isinstance(row, dict)]
                    return []
                return []
            if raw_path.suffix in (".csv", ".tsv"):
                delimiter = "\t" if raw_path.suffix == ".tsv" else ","
                with raw_path.open(encoding="utf-8", newline="") as fh:
                    return [dict(row) for row in csv.DictReader(fh)]
            if raw_path.suffix == ".jsonl":
                rows: list[dict[str, Any]] = []
                for line in raw_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
                return rows
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return None
        return None

    def _fetched_count(self, workspace: Path, raw_export: str | None) -> int | None:
        """Count records in the raw artifact (best effort; None when unreadable)."""
        records = self._iter_raw_records(workspace, raw_export)
        if records is None:
            return None
        return len(records)

    @staticmethod
    def _count_normalized(records: list[dict[str, Any]] | None) -> int | None:
        """Records whose identifier (publication number or DOI) was confidently
        normalized (roadmap §8.3: records_normalized ≠ records_fetched)."""
        if records is None:
            return None
        count = 0
        for record in records:
            pub = str(record.get("publication_number") or record.get("normalized_number") or "").strip()
            doi = str(record.get("DOI") or record.get("doi") or "").strip()
            if pub and normalize_publication_number(pub).confidence != "uncertain":
                count += 1
            elif doi and normalize_doi(doi).confidence != "uncertain":
                count += 1
        return count


@register_source
class CnipaAdapter(KernelFetchAdapter):
    """CNIPA publication search via the kernel's fetch-cnipa (external tool contract)."""

    id = "cnipa"
    kernel_verb = "fetch-cnipa"
    field_flags = {"abstract": "--abstract", "class": "--class", "title": "--title", "applicant": "--applicant"}

    def capabilities(self) -> Capability:
        return Capability(
            source=self.id,
            query_fields=frozenset({"keywords", "abstract", "class", "title", "applicant"}),
            languages=frozenset({"zh"}),
            max_results_per_query=3,  # per page; kernel fetches the first page(s) only
            pagination=False,
            license_status="public_export",
            cost="free",
            return_format="json (raw/) + log",
            support_level="partial",  # contract-tested; live run needs the external tool
            requires_credentials=False,
            notes=(
                "3 records per page; kernel declares result.complete=false for partial "
                "fetches (V026 discipline). Live runs need playwright + cnipa_search.py."
            ),
        )


@register_source
class CrossrefAdapter(KernelFetchAdapter):
    """Crossref bibliographic search via the kernel's fetch-crossref."""

    id = "crossref"
    kernel_verb = "fetch-crossref"
    field_flags = {"keywords": "--query"}
    base_args = ("--pages", "2")

    def capabilities(self) -> Capability:
        return Capability(
            source=self.id,
            query_fields=frozenset({"keywords"}),
            languages=frozenset({"en"}),
            max_results_per_query=0,  # unknown; treat as limited
            pagination=True,
            license_status="official_api",
            cost="free (polite pool)",
            return_format="json (raw/) + log",
            support_level="partial",
            requires_credentials=False,
            notes=(
                "Bibliographic metadata only — NPL full-text disclosure evidence is a "
                "separate concern (WP-B npl.py); --apply writes raw/ + log."
            ),
        )
