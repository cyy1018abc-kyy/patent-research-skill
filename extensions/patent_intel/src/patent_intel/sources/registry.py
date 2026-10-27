"""Source capability registry (blueprint B-01).

Single lookup point for adapters; `doctor` and the controller query it to decide
what is actually executable versus design-only. Registration happens at import of
:mod:`patent_intel.sources` — importing the package with a new adapter module is the
only way a source becomes available.
"""

from __future__ import annotations

from typing import Any

from patent_intel.sources.base import Capability, SourceAdapter

__all__ = ["Registry", "registry", "register_source", "get_source", "describe_sources"]


class Registry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        if not adapter.id:
            raise ValueError("adapter must declare a non-empty id")
        if adapter.id in self._adapters:
            raise ValueError(f"source {adapter.id!r} already registered")
        self._adapters[adapter.id] = adapter

    def get(self, source_id: str) -> SourceAdapter:
        try:
            return self._adapters[source_id]
        except KeyError:
            raise KeyError(
                f"unknown source {source_id!r}; available: {sorted(self._adapters)}"
            ) from None

    def ids(self) -> list[str]:
        return sorted(self._adapters)

    def __contains__(self, source_id: str) -> bool:
        return source_id in self._adapters

    def describe(self) -> list[dict[str, Any]]:
        return [self._adapters[sid].capabilities().describe() for sid in sorted(self._adapters)]


registry = Registry()


def register_source(adapter_cls: type[SourceAdapter]) -> type[SourceAdapter]:
    """Class decorator: instantiate and register at import time."""
    registry.register(adapter_cls())
    return adapter_cls


def get_source(source_id: str) -> SourceAdapter:
    return registry.get(source_id)


def describe_sources() -> list[dict[str, Any]]:
    return registry.describe()


# Import adapters so their @register_source decorators run. Keep this list aligned
# with the modules actually shipped; a planned-only adapter registers too (its
# support_level=planned blocks execution at the base-class gate).
from patent_intel.sources import kernel_sources as _kernel_sources  # noqa: E402,F401
from patent_intel.sources import ops as _ops  # noqa: E402,F401

_ = Capability  # re-export touchpoint for type checkers
