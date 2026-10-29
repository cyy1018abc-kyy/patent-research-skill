"""EPO OPS adapter (blueprint B-04) — optional, contract-tested, never live-run in CI.

Status honesty: ``support_level="partial"`` — the OAuth flow, rate limiting,
page checkpointing and raw archiving are implemented and tested against a fake
transport; **no live OPS call has been made from this repo** (docs/data-sources.md
keeps OPS behind real-task authorization; quota figures are never hardcoded).

Credentials come from ``OPS_OAUTH_KEY`` / ``OPS_OAUTH_SECRET`` environment
variables and are **never** written to logs, ledgers, or error messages.
Raw responses are archived into the *sidecar* ``raw/`` area with SHA-256 audit
entries; promoting them to kernel ``verified`` evidence remains a separate,
explicit kernel-ingest step (ADR 0001) — the adapter has no bypass.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from patent_intel.contracts import QuerySpec, RunStatus
from patent_intel.io.audit import AuditLedger
from patent_intel.io.safe_io import write_text_atomic
from patent_intel.sources.base import (
    AcquisitionResult,
    Capability,
    DryRunResult,
    NetworkNotConfirmed,
    RequestPlan,
    SourceAdapter,
)
from patent_intel.sources.checkpoint import Checkpoint, CheckpointStore
from patent_intel.sources.rate_limit import BackoffStopped, RateLimitExceeded, RateLimiter
from patent_intel.sources.registry import register_source

__all__ = ["OpsAdapter", "OpsTransportError"]

_OWNER = "WP-B"

#: OPS base URLs (documented endpoints; the portal remains authoritative).
_OAUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_SEARCH_URL = "https://ops.epo.org/3.2/published-data/search"
RAW_DIR_NAME = "raw"

#: transport callable: (method, url, headers, timeout) -> ResponseLike
Transport = Callable[..., Any]


class OpsTransportError(RuntimeError):
    """OPS transport failure (network, timeout, protocol)."""


def _default_transport(method: str, url: str, headers: dict[str, str], timeout: int) -> Any:
    """Requests-based transport; requires the `ops` extra."""
    try:
        import requests
    except ImportError as exc:
        raise NetworkNotConfirmed(
            "the OPS adapter requires the optional 'ops' extra: pip install 'patent_intel[ops]'"
        ) from exc
    return requests.request(method, url, headers=headers, timeout=timeout)


@register_source
class OpsAdapter(SourceAdapter):
    """Espacenet OPS search adapter (OAuth client-credentials, paged, checkpointed)."""

    id = "ops"

    def __init__(self, *, transport: Transport | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self._transport = transport or _default_transport
        self._sleep = sleep
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # -- capability ----------------------------------------------------

    def capabilities(self) -> Capability:
        return Capability(
            source=self.id,
            query_fields=frozenset({"keywords", "class"}),
            languages=frozenset({"en", "zh", "de", "fr"}),
            max_results_per_query=0,  # unknown; paged with explicit limits
            pagination=True,
            license_status="official_api",
            cost="free within portal quota (portal-authoritative; not hardcoded here)",
            return_format="json/xml (sidecar raw/) + audit ledger",
            support_level="partial",
            requires_credentials=True,
            notes=(
                "Contract-tested against a fake transport only; no live run from this "
                "repo yet. 403/429 stop acquisition (no retry storm); raw pages go to "
                "the sidecar with SHA-256 audit entries."
            ),
        )

    # -- auth ----------------------------------------------------------

    def _credentials(self) -> tuple[str, str]:
        key = os.environ.get("OPS_OAUTH_KEY", "")
        secret = os.environ.get("OPS_OAUTH_SECRET", "")
        if not key or not secret:
            raise NetworkNotConfirmed(
                "OPS credentials missing: set OPS_OAUTH_KEY / OPS_OAUTH_SECRET environment variables"
            )
        return key, secret

    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        key, secret = self._credentials()
        basic = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
        try:
            resp = self._transport(
                "POST",
                _OAUTH_URL,
                {"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
                30,
            )
        except Exception as exc:  # noqa: BLE001 - transport layer
            raise OpsTransportError(f"OAuth token request failed: {type(exc).__name__}") from None
        if resp.status_code != 200:
            # no credential material in the message — only the status
            raise OpsTransportError(f"OAuth token request returned HTTP {resp.status_code}")
        try:
            payload = resp.json()
            self._token = str(payload["access_token"])
            self._token_expiry = time.monotonic() + float(payload.get("expires_in", 1200)) - 60
        except Exception as exc:  # noqa: BLE001
            raise OpsTransportError("OAuth token response was not the expected JSON shape") from None
        return self._token

    # -- request planning ----------------------------------------------

    def build_request(self, query: QuerySpec) -> RequestPlan:
        self.ensure_query_supported(query)
        terms = " ".join(query.terms)
        q = f"ti or ab=({urllib.parse.quote(terms)})"
        args = [q, "--axis", query.axis_id.split("@")[0]]
        return RequestPlan(
            source=self.id,
            query_id=query.query_id,
            verb="ops-search",
            args=args,
            summary=f"OPS search: {q}",
            live=True,
        )

    def dry_run(self, plan: RequestPlan, workspace: Any) -> DryRunResult:
        url = f"{_SEARCH_URL}?q={plan.args[0]}&Range=1-25"
        return DryRunResult(
            plan=plan,
            preview=[f"GET {url}", "Authorization: Bearer <redacted>"],
            notes=[
                "live execution additionally requires OPS_OAUTH_KEY/OPS_OAUTH_SECRET "
                "and config.network_consent with 'ops' in allowed_sources",
            ],
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
        max_pages: int = 2,
        page_size: int = 25,
    ) -> AcquisitionResult:
        self.ensure_live_allowed(confirm_network=confirm_network, config=config)
        if state_dir is None:
            raise ValueError("OPS execute requires the sidecar state_dir (raw/ + runs/ + audit/)")
        state_dir = Path(state_dir)
        raw_dir = state_dir / RAW_DIR_NAME
        runs_dir = state_dir / "runs"
        audit = AuditLedger(state_dir / "audit")

        fingerprint = hashlib.sha256(("|".join(plan.args)).encode("utf-8")).hexdigest()
        store = CheckpointStore(runs_dir)
        cp = store.find_resumable(fingerprint) or Checkpoint(
            run_id=f"ops-{plan.query_id}-{time.strftime('%Y%m%d%H%M%S')}",
            query_id=plan.query_id,
            source=self.id,
            request_fingerprint=fingerprint,
        )
        cp.transition(RunStatus.RUNNING)
        store.save(cp)

        limiter = RateLimiter(min_interval_sec=1.0, max_requests=max_pages + 1)
        result = AcquisitionResult()
        try:
            token = self._access_token()
            limiter.acquire()
            start = len(cp.pages_done) * page_size + 1
            for page_index in range(len(cp.pages_done), max_pages):
                range_header = f"{page_index * page_size + 1}-{(page_index + 1) * page_size}"
                try:
                    resp = self._transport(
                        "GET",
                        f"{_SEARCH_URL}?q={plan.args[0]}",
                        {"Authorization": f"Bearer {token}", "X-OPS-Range": range_header},
                        60,
                    )
                except Exception as exc:  # noqa: BLE001 - transport layer (timeouts, DNS, …)
                    raise OpsTransportError(
                        f"search request failed: {type(exc).__name__}: {exc}"
                    ) from None
                if resp.status_code in (403, 429):
                    raise BackoffStopped(resp.status_code, page_index + 1)
                if resp.status_code != 200:
                    raise OpsTransportError(f"search returned HTTP {resp.status_code}")
                body = resp.text
                sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
                raw_name = f"ops_{plan.query_id}_page-{page_index + 1}.json"
                raw_path = raw_dir / raw_name
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                write_text_atomic(raw_path, body)
                cp.record_page(
                    fingerprint=f"{fingerprint}:{page_index}",
                    raw_ref=f"{RAW_DIR_NAME}/{raw_name}",
                    sha256=sha,
                    bytes_written=len(body.encode("utf-8")),
                )
                audit.append_raw(
                    path=f"{RAW_DIR_NAME}/{raw_name}",
                    sha256=sha,
                    bytes_written=len(body.encode("utf-8")),
                    source=self.id,
                    request_fingerprint=fingerprint,
                    extra={"page": page_index + 1, "range": range_header},
                )
                store.save(cp)
                result.log_paths.append(str(raw_path))
            cp.transition(RunStatus.COMPLETE if len(cp.pages_done) == max_pages else RunStatus.PARTIAL)
        except BackoffStopped as exc:
            cp.transition(RunStatus.FAILED, error=f"stopped on HTTP {exc.status}")
            audit.append_failure(
                source=self.id,
                run_id=cp.run_id,
                stop_reason=f"http_{exc.status}",
                preserved_pages=len(cp.pages_done),
                detail=str(exc),
            )
        except (OpsTransportError, RateLimitExceeded, NetworkNotConfirmed) as exc:
            cp.transition(RunStatus.FAILED, error=str(exc))
            audit.append_failure(
                source=self.id,
                run_id=cp.run_id,
                stop_reason="transport_error",
                preserved_pages=len(cp.pages_done),
                detail=str(exc),
            )
        finally:
            store.save(cp)

        result.runs = [cp.to_search_run()]
        result.raw_refs = [dict(page) for page in cp.pages_done]
        return result
