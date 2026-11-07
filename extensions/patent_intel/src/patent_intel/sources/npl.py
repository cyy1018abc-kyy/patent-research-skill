"""NPL (non-patent literature) evidence entry points (blueprint B-07; P1-B1 / roadmap 41B-1).

The load-bearing distinctions (interface rule 4 / UT-S04):

* **bibliographic metadata** (DOI, title, journal, dates) is *not* disclosure
  evidence — a paper's abstract/catalogue record never proves a technical
  teaching inside its body;
* **preprint vs published version** are distinct records: public dates, DOIs and
  content may all differ; a preprint must never stand in silently for the journal
  version (and vice versa);
* full-text availability is stated honestly; when we cannot verify a full text,
  `fulltext_availability` says ``unknown``/``metadata_only`` and callers must not
  fabricate disclosure citations from metadata.

P1-B1 additions (license-first hard gate, ``docs/source-licensing.md``):

* **versioned full text with SHA-256 binding** — a captured full text
  (:class:`NplFulltext`) declares which version it is (preprint vs published) and
  is bound to its content by a digest that is *validated*, not declared;
* **license-first gating** — :class:`NplSourceAdapter` refuses to execute any
  upstream whose licensing is not verified in ``docs/source-licensing.md``. As of
  this package *every* NPL/standards upstream is ``support_level=planned`` (the
  licensing work was done offline; no external terms were verifiable), so the
  adapter refuses execution **before any transport call**. The refusal is a
  feature: an unverified source must never get as far as a single HTTP request.
* the HTTP transport is injectable; the contract tests run entirely on fakes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from patent_intel.contracts import (
    AnchorVerification,
    DocumentAnchor,
    QuerySpec,
    RunStatus,
    SearchRun,
    utc_now_iso,
)
from patent_intel.io.audit import AuditLedger
from patent_intel.io.safe_io import write_text_atomic
from patent_intel.sources.base import (
    AcquisitionResult,
    Capability,
    CapabilityError,
    DryRunResult,
    NetworkNotConfirmed,
    RequestPlan,
    SourceAdapter,
)
from patent_intel.sources.normalize import normalize_doi
from patent_intel.sources.rate_limit import BackoffStopped
from patent_intel.sources.registry import register_source

__all__ = [
    "NplRecord",
    "NplFulltext",
    "FulltextVersion",
    "FulltextAvailability",
    "LicenseGrant",
    "LicenseNotGranted",
    "NplTransportError",
    "NplSourceAdapter",
    "DOC_LICENSE_TABLE",
    "fulltext_availability",
    "version_relation",
    "npl_anchor",
    "anchor_from_capture",
    "license_grant",
    "require_licensed",
]

_OWNER = "WP-B"
_RAW_DIR_NAME = "raw"
_TIMEOUT_SEC = 60
#: stop statuses: unauthorized (401), forbidden (403), throttled (429) — never retried
_STOP_STATUSES = frozenset({401, 403, 429})


# ── versioned full text with SHA-256 binding (P1-B1) ─────────────────


class FulltextVersion:
    """Which version of a work a captured full text claims to be (UT-S04)."""

    PREPRINT = "preprint"
    PUBLISHED = "published"

    ALL = (PREPRINT, PUBLISHED)


@dataclass(frozen=True)
class NplFulltext:
    """One captured full-text artifact, SHA-256-bound (P1-B1).

    The binding is *validated*, not declared: :meth:`capture` computes the digest
    over the content, and direct construction with a non-matching ``sha256`` is
    refused — a hash that does not bind its content must never enter the evidence
    chain. :meth:`from_dict` re-validates, so a tampered serialized capture cannot
    be reloaded.
    """

    #: which version of the work this capture claims to be (FulltextVersion)
    version: str
    content: str
    #: upstream that served it (must be licensed at fetch time — docs/source-licensing.md)
    source_id: str
    #: URL that actually served the bytes
    url: str
    captured_at: str
    sha256: str
    media_type: str = "text/plain"
    #: DOI this capture claims to be — the version-identity proof used when a
    #: capture is attached across a declared preprint↔published relation
    link_doi: str | None = None

    def __post_init__(self) -> None:
        if self.version not in FulltextVersion.ALL:
            raise ValueError(f"fulltext version {self.version!r} not in {FulltextVersion.ALL}")
        if not self.source_id.strip():
            raise ValueError("fulltext capture must name the upstream that served it")
        if not self.url.strip():
            raise ValueError("fulltext capture must record its source URL")
        if not self.captured_at.strip():
            raise ValueError("fulltext capture must record its capture time")
        computed = self.digest_of(self.content)
        if self.sha256 != computed:
            raise ValueError(
                f"sha256 {self.sha256[:12]}… does not bind the capture content "
                f"(computed {computed[:12]}…) — refusing an unbound hash"
            )

    @staticmethod
    def digest_of(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def capture(
        cls,
        *,
        version: str,
        content: str,
        source_id: str,
        url: str,
        captured_at: str,
        media_type: str = "text/plain",
        link_doi: str | None = None,
    ) -> "NplFulltext":
        """Bind a freshly captured text: the digest is computed here, never passed in."""
        return cls(
            version=version,
            content=content,
            source_id=source_id,
            url=url,
            captured_at=captured_at,
            sha256=cls.digest_of(content),
            media_type=media_type,
            link_doi=link_doi,
        )

    def verify(self) -> bool:
        """Re-hash the content — the audit path after any serialization round-trip."""
        return self.sha256 == self.digest_of(self.content)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source_id": self.source_id,
            "url": self.url,
            "captured_at": self.captured_at,
            "sha256": self.sha256,
            "media_type": self.media_type,
            "link_doi": self.link_doi,
            "bytes": len(self.content.encode("utf-8")),
        }
        # content is deliberately NOT serialized here — the full text lives in the
        # raw/ artifact it is hash-bound to, never duplicated into records.

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, content: str) -> "NplFulltext":
        """Rebuild from a record dict plus the raw artifact's content; the binding is
        re-validated on construction, so a mismatched content/hash pair is refused."""
        return cls(
            version=str(data["version"]),
            content=content,
            source_id=str(data["source_id"]),
            url=str(data["url"]),
            captured_at=str(data["captured_at"]),
            sha256=str(data["sha256"]),
            media_type=str(data.get("media_type") or "text/plain"),
            link_doi=data.get("link_doi"),
        )

    def describe(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source_id": self.source_id,
            "url": self.url,
            "captured_at": self.captured_at,
            "sha256": self.sha256,
            "media_type": self.media_type,
            "link_doi": self.link_doi,
            "bytes": len(self.content.encode("utf-8")),
        }


@dataclass
class NplRecord:
    """One NPL bibliographic record, version-explicit, with captured full texts."""

    record_id: str
    doi: str | None = None
    title: str | None = None
    #: "journal-article" | "proceedings-article" | "posted-content" (preprint) | …
    work_type: str | None = None
    #: Crossref-style deposited/issued dates (ISO strings)
    published_online: str | None = None
    published_print: str | None = None
    #: relation to other versions, e.g. {"is-preprint-of": "10.x/yyy"}
    relations: dict[str, str] = field(default_factory=dict)
    #: where the metadata came from (crossref/arxiv/manual)
    source: str = "crossref"
    #: URL that actually serves a full text (only set when the source says so)
    fulltext_url: str | None = None
    #: captured full texts, one per version at most (P1-B1)
    fulltext_captures: list[NplFulltext] = field(default_factory=list)

    @classmethod
    def from_crossref(cls, item: dict[str, Any], *, record_id: str) -> "NplRecord":
        """Build from a Crossref works-API item (bibliographic fields only)."""
        doi_raw = str(item.get("DOI") or "")
        date_parts = (item.get("issued") or {}).get("date-parts") or [[]]
        published_online = None
        published_print = None
        online = (item.get("published-online") or {}).get("date-parts") or None
        print_ = (item.get("published-print") or {}).get("date-parts") or None
        if online and online[0]:
            published_online = "-".join(str(p) for p in online[0])
        if print_ and print_[0]:
            published_print = "-".join(str(p) for p in print_[0])
        if not published_online and not published_print and date_parts and date_parts[0]:
            issued = "-".join(str(p) for p in date_parts[0])
            published_print = issued
        relations: dict[str, str] = {}
        for rel_key, rel_items in (item.get("relation") or {}).items():
            for rel in rel_items or []:
                if isinstance(rel, dict) and rel.get("id"):
                    relations[rel_key] = str(rel["id"])
        return cls(
            record_id=record_id,
            doi=normalize_doi(doi_raw).normalized or None if doi_raw else None,
            title=(item.get("title") or [None])[0],
            work_type=item.get("type"),
            published_online=published_online,
            published_print=published_print,
            relations=relations,
            source="crossref",
        )

    # -- versioned full text (P1-B1) ------------------------------------

    def _version_identity(self) -> str | None:
        """The version this record *declares itself* to be; None when unknown."""
        if self.work_type == "posted-content":
            return FulltextVersion.PREPRINT
        if self.work_type:
            return FulltextVersion.PUBLISHED
        return None

    def attach_fulltext(self, capture: NplFulltext) -> None:
        """Attach a captured full text under version discipline (UT-S04).

        Rules (all refusals are loud, never silent merges):

        1. one capture per version — a re-capture must replace explicitly, never
           silently;
        2. a capture whose version matches the record's declared identity attaches
           directly;
        3. a record with no declared work_type only accepts a capture that proves
           its identity by carrying ``link_doi`` equal to the record DOI;
        4. a cross-version capture (published text on a preprint record or vice
           versa) attaches **only** through a declared, matching relation — the
           record must name its counterpart DOI in ``relations`` and the capture
           must carry that same DOI as ``link_doi``.
        """
        if any(existing.version == capture.version for existing in self.fulltext_captures):
            raise ValueError(
                f"record {self.record_id!r} already carries a {capture.version!r} full text; "
                "a re-capture must replace explicitly, never silently"
            )
        identity = self._version_identity()
        if capture.version == identity:
            self.fulltext_captures.append(capture)
            return
        if identity is None:
            if self.doi and capture.link_doi == self.doi:
                self.fulltext_captures.append(capture)
                return
            raise ValueError(
                f"record {self.record_id!r} declares no work_type; attaching a "
                f"{capture.version!r} capture requires the record DOI and the "
                "capture's link_doi to match"
            )
        relation_key = (
            "is-preprint-of" if identity == FulltextVersion.PREPRINT else "has-preprint"
        )
        expected = self.relations.get(relation_key)
        if not expected or capture.link_doi != expected:
            raise ValueError(
                f"record {self.record_id!r} is a {identity} record; attaching a "
                f"{capture.version!r} capture requires relations[{relation_key!r}] "
                "and the capture's link_doi to name that counterpart DOI — a "
                "preprint must never stand in silently for the journal version "
                "(and vice versa)"
            )
        self.fulltext_captures.append(capture)

    def captured_fulltext(self, version: str) -> NplFulltext | None:
        for existing in self.fulltext_captures:
            if existing.version == version:
                return existing
        return None


class FulltextAvailability:
    METADATA_ONLY = "metadata_only"  # catalogue/abstract only — NO disclosure evidence
    ABSTRACT = "abstract"            # abstract text captured; still not body disclosure
    FULLTEXT = "fulltext"            # a full-text artifact is actually captured
    UNKNOWN = "unknown"              # cannot determine honestly


def fulltext_availability(record: NplRecord, *, captured_text_bytes: int = 0) -> str:
    """Honest availability verdict for one record."""
    if captured_text_bytes > 0 or record.fulltext_captures:
        return FulltextAvailability.FULLTEXT
    if record.fulltext_url:
        return FulltextAvailability.UNKNOWN  # URL claimed but nothing captured yet
    if record.work_type == "posted-content":
        return FulltextAvailability.ABSTRACT
    return FulltextAvailability.METADATA_ONLY


def version_relation(record: NplRecord) -> dict[str, Any]:
    """Preprint/published separation summary (never conflated, UT-S04)."""
    is_preprint = record.work_type == "posted-content"
    published_of = record.relations.get("is-preprint-of")
    preprint_of = record.relations.get("has-preprint")
    return {
        "record_id": record.record_id,
        "is_preprint": is_preprint,
        "published_doi": published_of or (record.doi if not is_preprint else None),
        "preprint_doi": preprint_of or (record.doi if is_preprint else None),
        "public_date": record.published_online or record.published_print,
        "captured_versions": sorted(c.version for c in record.fulltext_captures),
        "note": (
            "preprint and journal version are separate records; citing one is not "
            "citing the other — dates and content may differ"
        ),
    }


def npl_anchor(record: NplRecord, quote: str, *, raw_sha256: str, source_document: str) -> DocumentAnchor:
    """Anchor a quote inside a *captured* NPL artifact.

    Metadata-only records have no artifact to anchor — callers must capture the
    artifact first; this function refuses to fabricate an anchor from metadata.
    """
    if not quote.strip():
        raise ValueError("empty quote")
    return DocumentAnchor(
        owner=_OWNER,
        raw_sha256=raw_sha256,
        source_document=source_document,
        paragraph="npl:quote",
        text_hash=hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        parser_version="patent_intel.sources.npl 0.1.0",
        verification_status=AnchorVerification.UNVERIFIED,  # NPL quotes await human confirmation
        extra={"doi": record.doi, "record_id": record.record_id, "quote": quote[:200]},
    )


def anchor_from_capture(
    record: NplRecord, capture: NplFulltext, quote: str, *, source_document: str
) -> DocumentAnchor:
    """Anchor a quote *read from a captured full text* (P1-B1).

    The anchor binds the capture's SHA-256, so later verification re-checks the
    same artifact the quote was read from. A quote that the captured text does not
    contain must never produce an anchor — metadata is not disclosure evidence.
    """
    if not quote.strip():
        raise ValueError("empty quote")
    if not capture.verify():
        raise ValueError("capture failed its SHA-256 re-check — refusing to anchor against tampered content")
    if quote not in capture.content:
        raise ValueError("quote not found in the captured full text — refusing to anchor from metadata")
    return DocumentAnchor(
        owner=_OWNER,
        raw_sha256=capture.sha256,
        source_document=source_document,
        paragraph=f"npl:quote:{capture.version}",
        text_hash=hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        parser_version="patent_intel.sources.npl 0.1.0",
        verification_status=AnchorVerification.UNVERIFIED,
        extra={
            "doi": record.doi,
            "record_id": record.record_id,
            "quote": quote[:200],
            "fulltext_version": capture.version,
            "link_doi": capture.link_doi,
            "upstream": capture.source_id,
        },
    )


# ── license-first gate (P1-B1; docs/source-licensing.md) ──────────────


@dataclass(frozen=True)
class LicenseGrant:
    """One upstream's licensing state, mirrored from ``docs/source-licensing.md`` §4.

    ``support_level`` uses the ``sources/base.py`` vocabulary; ``planned`` refuses
    execution (unverified licensing can never be contract-tested into executability).
    """

    source_id: str
    license_status: str
    support_level: str
    evidence: str


#: Frozen mirror of ``docs/source-licensing.md`` §4 (P1-B1, 2026-11-07). Every NPL/
#: standards upstream was registered **offline**: no external terms were verifiable,
#: so all entries are ``planned`` and refuse execution. Updating this table and the
#: document MUST happen in the same commit — divergence silently kills the gate.
DOC_LICENSE_TABLE: Mapping[str, LicenseGrant] = {
    "arxiv": LicenseGrant(
        "arxiv", "unverified → planned", "planned", "docs/source-licensing.md §5.1"
    ),
    "europepmc": LicenseGrant(
        "europepmc", "unverified → planned", "planned", "docs/source-licensing.md §5.2"
    ),
    "openalex": LicenseGrant(
        "openalex", "unverified → planned", "planned", "docs/source-licensing.md §5.3"
    ),
    "unpaywall": LicenseGrant(
        "unpaywall", "unverified → planned", "planned", "docs/source-licensing.md §5.3"
    ),
    "publisher-direct": LicenseGrant(
        "publisher-direct", "unverified → planned", "planned", "docs/source-licensing.md §5.4"
    ),
    "standards-text": LicenseGrant(
        "standards-text", "unverified → planned", "planned", "docs/source-licensing.md §5.5"
    ),
}


class LicenseNotGranted(Exception):
    """License-first gate: the upstream has no verified license grant.

    Raised *before* any transport call — an unlicensed source must never emit a
    single network request.
    """


def license_grant(
    source_id: str, grants: Mapping[str, LicenseGrant] | None = None
) -> LicenseGrant | None:
    """Look up the licensing state of ``source_id`` (doc table by default)."""
    table = DOC_LICENSE_TABLE if grants is None else grants
    return table.get(source_id)


def require_licensed(
    source_id: str, grants: Mapping[str, LicenseGrant] | None = None
) -> LicenseGrant:
    """License-first hard gate: return the grant or raise :class:`LicenseNotGranted`.

    An unknown source and a ``support_level=planned`` source both refuse — the gate
    checks the level, not mere presence, so an injected table cannot promote a
    source by listing it.
    """
    grant = license_grant(source_id, grants)
    if grant is None:
        raise LicenseNotGranted(
            f"source {source_id!r} has no license entry in docs/source-licensing.md — "
            "refusing (license-first: no entry, no execution)"
        )
    if grant.support_level == "planned":
        raise LicenseNotGranted(
            f"source {source_id!r} is support_level=planned (license unverified, "
            f"{grant.evidence}) — refusing execution until licensing evidence lands"
        )
    return grant


# ── NPL full-text acquisition adapter (P1-B1) ─────────────────────────


class NplTransportError(RuntimeError):
    """NPL full-text transport failure (network, timeout, protocol)."""


#: transport callable: (method, url, headers, timeout) -> ResponseLike
Transport = Callable[..., Any]


def _default_transport(method: str, url: str, headers: dict[str, str], timeout: int) -> Any:
    """No in-process network stack — a real transport must be injected (INT wave-gate fix).

    The extension-wide discipline is that network imports live ONLY in the
    transport layer (ops.py; guard: test_extension_source_has_no_network_imports_
    outside_transport). NPL acquisition therefore never carries a requests-based
    fallback: callers inject a transport explicitly after their own consent and
    licensing gates. Until then every default-transport call raises
    ``NetworkNotConfirmed`` — unreachable in practice while all grants are
    ``planned`` (the license gate refuses before any transport call).
    """
    raise NetworkNotConfirmed(
        "the NPL full-text adapter has no built-in network stack: inject a transport "
        "(and satisfy the license gate in docs/source-licensing.md) before acquisition"
    )


@register_source
class NplSourceAdapter(SourceAdapter):
    """NPL full-text acquisition adapter (P1-B1, roadmap 41B-1).

    License-first: ``execute()`` refuses any upstream whose licensing is not
    verified in ``docs/source-licensing.md`` *before* touching the transport —
    as of this package that is every upstream, so no real acquisition can happen
    no matter how the adapter is configured. The acquisition contract itself is
    ``partial`` (stub-transport-tested, never live-run — the same honesty rule as
    the OPS adapter); the upstream license table is what keeps it non-executable.

    The transport and the license table are both injectable (contract tests run
    on fakes); 401/403/429 responses stop acquisition immediately without a retry
    storm, and every successful capture lands as a raw/ artifact with a SHA-256
    audit entry — the raw-first discipline of ``docs/data-sources.md`` applies to
    NPL full texts exactly as to patent sources.
    """

    id = "npl"

    def __init__(
        self,
        *,
        upstream: str = "arxiv",
        transport: Transport | None = None,
        grants: Mapping[str, LicenseGrant] | None = None,
    ) -> None:
        self._upstream = upstream
        self._transport = transport or _default_transport
        self._grants = grants

    # -- capability ----------------------------------------------------

    def capabilities(self) -> Capability:
        return Capability(
            source=self.id,
            # terms-only declaration: the query gate checks `keywords` unconditionally
            # (base.ensure_query_supported); no identifier filters are declared because
            # discovery against unverified upstreams is not a capability this source
            # can honestly claim.
            query_fields=frozenset({"keywords"}),
            languages=frozenset(),  # nothing verified — no language claimed
            max_results_per_query=0,  # unknown; search never executed (no licensed upstream)
            pagination=False,
            license_status="manual_export_only",
            cost="free (no upstream executable yet; manual capture is the only compliant channel)",
            return_format="raw fulltext artifact (sidecar raw/) + audit ledger",
            support_level="partial",
            requires_credentials=False,
            notes=(
                "Contract-tested against a fake transport only; no live run possible: "
                "the license-first gate (docs/source-licensing.md) marks every "
                "NPL/standards upstream support_level=planned, so execute() refuses "
                "BEFORE any transport call for every real upstream. build_request "
                "makes reviewable search plans (terms); executable fetch plans "
                "(verb='npl-fulltext') are record-driven and carry their own URL — "
                "the adapter never constructs URLs. 401/403/429 stop immediately "
                "(no retry storm). Captures land in sidecar raw/ with SHA-256 audit "
                "entries; quotes anchor only against captured text, never metadata."
            ),
        )

    # -- request planning ----------------------------------------------

    def build_request(self, query: QuerySpec) -> RequestPlan:
        """Reviewable *search* plan from the query terms.

        A search plan is a preview artifact: it cannot be executed until an upstream
        is licensed AND its endpoint verified (none is today) — the URL is never
        constructed from unverified upstream knowledge. Record-driven full-text
        fetches use ``verb='npl-fulltext'`` plans that carry their own URL.
        """
        self.ensure_query_supported(query)
        q = " ".join(query.terms)
        return RequestPlan(
            source=self.id,
            query_id=query.query_id,
            verb="npl-search",
            args=[q],
            summary=f"npl search ({self._upstream}): {q!r} (execution license-gated)",
            live=True,
        )

    def dry_run(self, plan: RequestPlan, workspace: Any) -> DryRunResult:
        notes = [
            "execution additionally requires: config.network_consent with 'npl' "
            "in allowed_sources, AND a verified license grant for upstream "
            f"{self._upstream!r} (docs/source-licensing.md — currently planned)"
        ]
        if plan.verb == "npl-fulltext" and plan.args:
            url = plan.args[0]
            version = plan.args[1] if len(plan.args) > 1 else "(no version)"
            return DryRunResult(
                plan=plan,
                preview=[f"GET {url}", f"version claim: {version}"],
                notes=notes,
            )
        q = plan.args[0] if plan.args else "(no query)"
        return DryRunResult(
            plan=plan,
            preview=[
                f"search query: {q}",
                "upstream search endpoint: unverified — no URL constructed "
                "(docs/source-licensing.md)",
            ],
            notes=notes,
        )

    # -- execution -----------------------------------------------------

    def execute(  # type: ignore[override]
        self,
        plan: RequestPlan,
        workspace: Any,
        *,
        confirm_network: bool,
        config: Any,
        state_dir: Path | None = None,
        grants: Mapping[str, LicenseGrant] | None = None,
    ) -> AcquisitionResult:
        """Fetch one full-text artifact. Two gates run before any transport call:

        1. the shared double consent gate (``ensure_live_allowed``);
        2. the license-first gate (:func:`require_licensed`) — P1-B1 hard gate.
        """
        self.ensure_live_allowed(confirm_network=confirm_network, config=config)
        # license-first hard gate — raises before any transport call on unlicensed upstreams
        require_licensed(self._upstream, grants=grants if grants is not None else self._grants)
        if plan.verb != "npl-fulltext":
            # search plans are reviewable previews only: no upstream has a verified
            # endpoint, and URLs are never constructed from unverified knowledge
            raise CapabilityError(
                f"verb {plan.verb!r} is not executable: npl search needs a licensed "
                "upstream with a verified endpoint (docs/source-licensing.md — none "
                "exists today); fetch plans use verb='npl-fulltext' with a "
                "plan-carried URL"
            )
        if state_dir is None:
            raise ValueError("NPL execute requires the sidecar state_dir (raw/ + audit/)")
        state_dir = Path(state_dir)
        if len(plan.args) < 2 or not str(plan.args[0]).startswith(("http://", "https://")):
            raise CapabilityError(
                f"plan {plan.query_id} does not carry an http(s) fulltext URL + version"
            )
        url, version = str(plan.args[0]), str(plan.args[1])
        link_doi = str(plan.args[2]).strip() or None if len(plan.args) > 2 else None

        audit = AuditLedger(state_dir / "audit")
        raw_dir = state_dir / _RAW_DIR_NAME
        fingerprint = hashlib.sha256("|".join([self._upstream, url, version]).encode("utf-8")).hexdigest()
        run_id = f"npl:{plan.query_id}:{version}"
        result = AcquisitionResult()

        try:
            try:
                resp = self._transport(
                    "GET",
                    url,
                    {"Accept": "text/plain, application/pdf;q=0.8, */*;q=0.1",
                     "User-Agent": "patent-intel-npl/0.1 (license-gated)"},
                    _TIMEOUT_SEC,
                )
            except Exception as exc:  # noqa: BLE001 - transport layer (timeouts, DNS, …)
                raise NplTransportError(f"fulltext request failed: {type(exc).__name__}") from None
            status = getattr(resp, "status_code", None)
            if isinstance(status, int) and status in _STOP_STATUSES:
                # 401/403/429: stop immediately — no retry storm, nothing preserved
                raise BackoffStopped(status, 1)
            if status != 200:
                raise NplTransportError(f"fulltext returned HTTP {status}")
            body = resp.text
            capture = NplFulltext.capture(
                version=version,
                content=body,
                source_id=self._upstream,
                url=url,
                captured_at=utc_now_iso(),
                link_doi=link_doi,
            )
            raw_name = f"npl_{plan.query_id}_{version}.txt"
            raw_path = raw_dir / raw_name
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(raw_path, body)
            rel_path = f"{_RAW_DIR_NAME}/{raw_name}"
            audit.append_raw(
                path=rel_path,
                sha256=capture.sha256,
                bytes_written=len(body.encode("utf-8")),
                source=self.id,
                request_fingerprint=fingerprint,
                extra={"upstream": self._upstream, "url": url, "version": version},
            )
            result.log_paths.append(str(raw_path))
            result.raw_refs.append(
                {"path": rel_path, "sha256": capture.sha256, "bytes": len(body.encode("utf-8")), "source": self.id}
            )
            result.runs.append(
                SearchRun(
                    owner=_OWNER,
                    run_id=run_id,
                    query_id=plan.query_id,
                    source=self.id,
                    executed_at=utc_now_iso(),
                    status=RunStatus.COMPLETE,
                    request_fingerprint=fingerprint,
                    hits_reported=None,  # a full-text fetch has no hit count — never invented
                    records_fetched=1,
                    complete=True,
                    artifact_refs=[{"raw": rel_path, "sha256": capture.sha256, "version": version, "url": url}],
                )
            )
        except BackoffStopped as exc:
            result.runs.append(
                SearchRun(
                    owner=_OWNER,
                    run_id=run_id,
                    query_id=plan.query_id,
                    source=self.id,
                    executed_at=utc_now_iso(),
                    status=RunStatus.FAILED,
                    request_fingerprint=fingerprint,
                    error=f"stopped on HTTP {exc.status}",
                    artifact_refs=[{"upstream": self._upstream, "url": url, "version": version}],
                )
            )
            audit.append_failure(
                source=self.id,
                run_id=run_id,
                stop_reason=f"http_{exc.status}",
                preserved_pages=0,
                detail=str(exc),
            )
        except (NplTransportError, NetworkNotConfirmed) as exc:
            result.runs.append(
                SearchRun(
                    owner=_OWNER,
                    run_id=run_id,
                    query_id=plan.query_id,
                    source=self.id,
                    executed_at=utc_now_iso(),
                    status=RunStatus.FAILED,
                    request_fingerprint=fingerprint,
                    error=str(exc),
                    artifact_refs=[{"upstream": self._upstream, "url": url, "version": version}],
                )
            )
            audit.append_failure(
                source=self.id,
                run_id=run_id,
                stop_reason="transport_error",
                preserved_pages=0,
                detail=str(exc),
            )
        return result
