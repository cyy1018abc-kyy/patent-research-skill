"""SourceAdapter protocol and capability matrix (blueprint B-01).

Core discipline: **a source never pretends to support what it cannot**. Any query
shape outside the declared capability matrix raises :class:`CapabilityError` — the
caller must route the query elsewhere or degrade explicitly, never receive a
fabricated "success" (interface rule 1 of the blueprint's contract).

Network acquisition is double-gated: the caller must pass ``confirm_network=True``
*and* the loaded config must have ``network_consent`` with this source in
``allowed_sources``. Neither condition alone is sufficient.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from patent_intel.contracts import QuerySpec, SearchRun

__all__ = [
    "Capability",
    "CapabilityError",
    "NetworkNotConfirmed",
    "SourceAdapter",
    "RequestPlan",
    "DryRunResult",
]


class CapabilityError(Exception):
    """The query shape is outside this source's declared capability matrix."""


class NetworkNotConfirmed(Exception):
    """Live acquisition attempted without the double consent gate (config + flag)."""


@dataclass(frozen=True)
class Capability:
    """What a source can honestly do (B-06 keeps the human-readable mirror in docs)."""

    source: str
    #: query fields this source accepts, e.g. {"abstract", "class", "keywords"}
    query_fields: frozenset[str]
    languages: frozenset[str]
    #: hard upper bound on results per query (0 = unknown → callers must treat as limited)
    max_results_per_query: int
    pagination: bool
    #: "official_api" | "public_export" | "manual_export_only"
    license_status: str
    cost: str
    return_format: str
    #: "full" (integration-tested) | "partial" (contract-tested, no live run yet)
    #: | "planned" (design only — must not be executed)
    support_level: str
    requires_credentials: bool
    notes: str = ""

    def describe(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "query_fields": sorted(self.query_fields),
            "languages": sorted(self.languages),
            "max_results_per_query": self.max_results_per_query,
            "pagination": self.pagination,
            "license_status": self.license_status,
            "cost": self.cost,
            "return_format": self.return_format,
            "support_level": self.support_level,
            "requires_credentials": self.requires_credentials,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RequestPlan:
    """A concrete, reviewable request derived from an approved QuerySpec."""

    source: str
    query_id: str
    verb: str
    args: list[str]
    #: human-readable summary of what would be sent (dry-run output, audit trail)
    summary: str
    #: True when the plan triggers live network IO when executed
    live: bool

    def describe(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "query_id": self.query_id,
            "verb": self.verb,
            "args": self.args,
            "summary": self.summary,
            "live": self.live,
        }


@dataclass(frozen=True)
class DryRunResult:
    plan: RequestPlan
    #: commands/URLs that would be issued (no network touched)
    preview: list[str]
    notes: list[str]

    def describe(self) -> dict[str, Any]:
        return {"plan": self.plan.describe(), "preview": self.preview, "notes": self.notes}


@dataclass
class AcquisitionResult:
    """Outcome of one executed acquisition: runs + raw artifacts (kernel-written)."""

    runs: list[SearchRun] = field(default_factory=list)
    raw_refs: list[dict[str, Any]] = field(default_factory=list)
    #: paths of kernel-written log files created by this execution
    log_paths: list[str] = field(default_factory=list)

    def describe(self) -> dict[str, Any]:
        return {
            "runs": [r.to_dict() for r in self.runs],
            "raw_refs": self.raw_refs,
            "log_paths": self.log_paths,
        }


class SourceAdapter(ABC):
    """One retrieval source. Implementations must be offline-safe until execute()."""

    #: unique source id used in configs and logs (e.g. "cnipa", "crossref", "ops")
    id: str = ""

    @abstractmethod
    def capabilities(self) -> Capability: ...

    @abstractmethod
    def build_request(self, query: QuerySpec) -> RequestPlan:
        """Translate an approved query into a concrete request; refuse invalid shapes."""

    @abstractmethod
    def dry_run(self, plan: RequestPlan, workspace: Any) -> DryRunResult:
        """Preview the request without network IO. Must not write anything."""

    @abstractmethod
    def execute(
        self,
        plan: RequestPlan,
        workspace: Any,
        *,
        confirm_network: bool,
        config: Any,
    ) -> AcquisitionResult:
        """Run the acquisition. Requires config.network_consent AND source allowlisted."""

    # -- shared gating -------------------------------------------------

    def ensure_live_allowed(self, *, confirm_network: bool, config: Any) -> None:
        if not confirm_network:
            raise NetworkNotConfirmed(
                "live acquisition refused: pass --confirm-network explicitly"
            )
        if config is None or not getattr(config, "network_consent", False):
            raise NetworkNotConfirmed(
                "live acquisition refused: config.network_consent is false — "
                "edit the sidecar config.json to consent explicitly"
            )
        allowed = getattr(config, "allowed_sources", None) or []
        if self.id not in allowed:
            raise NetworkNotConfirmed(
                f"live acquisition refused: source {self.id!r} not in config.allowed_sources"
            )

    def ensure_query_supported(self, query: QuerySpec) -> None:
        cap = self.capabilities()
        if cap.support_level == "planned":
            raise CapabilityError(
                f"source {self.id!r} is design-only (support_level=planned); not executable"
            )
        fields = set((query.filters or {}).keys()) | {"keywords"}
        unsupported = fields - cap.query_fields
        if unsupported:
            raise CapabilityError(
                f"source {self.id!r} does not support query fields {sorted(unsupported)} "
                f"(supports {sorted(cap.query_fields)}); refusing to fabricate availability"
            )
