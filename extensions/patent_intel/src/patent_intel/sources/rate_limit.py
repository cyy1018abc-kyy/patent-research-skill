"""Rate limiting and polite backoff (blueprint B-04).

Discipline (docs/data-sources.md): 默认串行 + 指数退避；403/429 一律停下，
保留已完成部分再退出——绝不重试风暴。Quota numbers are NOT hardcoded here
(they change; the OPS portal is authoritative) — callers inject limits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

__all__ = ["RateLimitExceeded", "BackoffStopped", "RateLimiter", "with_backoff"]

T = TypeVar("T")

_OWNER = "WP-B"


class RateLimitExceeded(Exception):
    """The caller tried to exceed the configured request budget."""


class BackoffStopped(Exception):
    """A 403/429-class response: acquisition stops after flushing completed work.

    Carries the HTTP status so the caller records the honest stop reason.
    """

    def __init__(self, status: int, attempts: int) -> None:
        super().__init__(f"source returned {status} after {attempts} attempt(s); stopped without retry storm")
        self.status = status
        self.attempts = attempts


@dataclass
class RateLimiter:
    """Minimal token bucket (serial acquisition by design)."""

    min_interval_sec: float = 1.0
    max_requests: int | None = None
    _last: float = field(default=0.0, repr=False)
    _count: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if self.min_interval_sec < 0:
            raise ValueError("min_interval_sec must be non-negative")
        if self.max_requests is not None and self.max_requests < 0:
            raise ValueError("max_requests must be non-negative")

    def acquire(self, *, now: Callable[[], float] | None = None) -> float:
        """Wait as needed for the next slot; returns the wait time. Raises
        :class:`RateLimitExceeded` once the request budget is spent."""
        clock = now or time.monotonic
        if self.max_requests is not None and self._count >= self.max_requests:
            raise RateLimitExceeded(f"request budget exhausted ({self.max_requests})")
        current = clock()
        wait = 0.0
        since = current - self._last
        if self._last and since < self.min_interval_sec:
            wait = self.min_interval_sec - since
            time.sleep(wait)
            current = clock()
        self._last = current
        self._count += 1
        return wait


def with_backoff(
    fn: Callable[[], T],
    *,
    stop_on_status: set[int] | None = None,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry transient failures with exponential backoff; **stop immediately** on
    403/429-class statuses (no retry storm) by raising :class:`BackoffStopped`.

    ``fn`` returns the response object (or raises). Status detection: the returned
    object's ``status_code`` attribute (requests-style) is inspected; other return
    values are treated as success.
    """
    stop_on = stop_on_status or {403, 429}
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        result = fn()
        status = getattr(result, "status_code", None)
        if isinstance(status, int) and status in stop_on:
            raise BackoffStopped(status, attempt)
        if status is None or (isinstance(status, int) and status < 400):
            return result
        last_exc = RuntimeError(f"HTTP {status}")
        if attempt < max_attempts:
            sleep(min(max_delay, base_delay * (2 ** (attempt - 1))))
    raise RuntimeError(f"exhausted {max_attempts} attempts; last error: {last_exc}")
