"""Controlled terminology expansion (blueprint A-02, WP-A; roadmap 41A-3).

Three expanders:

* :class:`DictionaryExpander` — offline, deterministic, from a curated seed
  dictionary plus optional user dictionaries. Every expansion records its relation
  (``synonym`` / ``hypernym`` / ``hyponym`` / ``translation`` / ``abbreviation``)
  and is a *reviewable proposal* — never auto-approved, never silently treated as
  the legal equivalent of the source feature (UT-Q01: 上下位概念不等于法律同一特征).
* :class:`CrossDomainExpander` — the dictionary path **plus** corpus co-occurrence
  mining terms (roadmap 41A-3): mined candidates carry relation ``cross_domain``
  and provenance that records the mining splits (train/val only), parameters and
  table digest. With no mining table attached it is *byte-equivalent* to
  :class:`DictionaryExpander` — the curated dictionary path is preserved verbatim
  as the fallback.
* :class:`LLMExpander` — optional hook. The base wheel ships **no** LLM client and
  **no** network code; a host may inject one, and its output goes through the same
  provenance + review discipline. Terms from an LLM without a feature link are
  marked ``unverified-proposal`` (UT-Q03).

Expansion of *necessary* features is forbidden: expanders only add retrieval terms,
they never add or remove requiredness (interface rule: 不凭空添加必要特征).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from patent_intel.contracts import FeatureSpec, QuerySpec, Requiredness
from patent_intel.retrieval.cooccurrence import MiningTable
from patent_intel.retrieval.lexical import tokenize
from patent_intel.retrieval.terminology import detect_language, normalize_term

__all__ = [
    "TermCandidate",
    "Expander",
    "DictionaryExpander",
    "CrossDomainExpander",
    "LLMExpander",
    "SEED_TERMS",
    "TermExpansionError",
]

_OWNER = "WP-A"

#: Curated seed dictionary: headword -> expansions with relations. zh/en mixed on
#: purpose (cross-language retrieval is the norm in patent prior-art search).
SEED_TERMS: dict[str, list[dict[str, str]]] = {
    "时间同步": [
        {"term": "time synchronization", "relation": "translation"},
        {"term": "clock sync", "relation": "synonym"},
        {"term": "时钟校准", "relation": "synonym"},
    ],
    "信标": [
        {"term": "beacon", "relation": "translation"},
        {"term": "broadcast frame", "relation": "hypernym"},
        {"term": "sync frame", "relation": "synonym"},
    ],
    "漂移补偿": [
        {"term": "drift compensation", "relation": "translation"},
        {"term": "frequency offset correction", "relation": "synonym"},
        {"term": "clock drift", "relation": "hyponym"},
    ],
    "重同步": [
        {"term": "resynchronization", "relation": "translation"},
        {"term": "re-sync", "relation": "abbreviation"},
        {"term": "rejoin procedure", "relation": "synonym"},
    ],
    "无线传感网": [
        {"term": "wireless sensor network", "relation": "translation"},
        {"term": "WSN", "relation": "abbreviation"},
        {"term": "mesh network", "relation": "hypernym"},
    ],
    "电池管理": [
        {"term": "battery management", "relation": "translation"},
        {"term": "BMS", "relation": "abbreviation"},
        {"term": "state of charge", "relation": "hyponym"},
    ],
    "荷电状态": [
        {"term": "state of charge", "relation": "translation"},
        {"term": "SOC", "relation": "abbreviation"},
    ],
}


class TermExpansionError(ValueError):
    """Invalid expansion request."""


@dataclass(frozen=True)
class TermCandidate:
    """One proposed retrieval term. A proposal until approved; provenance mandatory."""

    term: str
    relation: str  # synonym | hypernym | hyponym | translation | abbreviation | cross_domain | llm
    feature_id: str | None
    source: str  # "seed-dictionary" | dict path | "cooccurrence:<digest>" | "llm:<model>" | "user:<path>"
    #: UT-Q03: no source feature link ⇒ the whole candidate is unverified
    verified: bool = True
    #: extra provenance merged into to_provenance() (e.g. the mining block:
    #: splits/params/digest of the co-occurrence table the term was mined from);
    #: None keeps provenance byte-identical to the pre-41A-3 shape
    extra: dict[str, Any] | None = None

    def to_provenance(self) -> dict[str, Any]:
        provenance = {
            "feature_id": self.feature_id,
            "term": self.term,
            "relation": self.relation,
            "source": self.source,
            "verified": self.verified,
        }
        if self.extra:
            provenance.update(self.extra)
        return provenance


class Expander(Protocol):
    """Anything that can propose retrieval terms for a feature."""

    def expand(self, feature: FeatureSpec) -> list[TermCandidate]: ...


def _headword_for(feature: FeatureSpec) -> str:
    """Best-effort headword: the feature statement itself (dictionary keys are
    matched by substring against the statement)."""
    return feature.statement


class DictionaryExpander:
    """Offline deterministic expansion over SEED_TERMS + optional user dictionaries."""

    def __init__(self, extra_dictionaries: list[Path] | None = None) -> None:
        self._dict: dict[str, list[dict[str, str]]] = {k: list(v) for k, v in SEED_TERMS.items()}
        for path in extra_dictionaries or []:
            self.load_dictionary(path)

    def load_dictionary(self, path: Path) -> None:
        """Merge a user JSON dictionary (same shape as SEED_TERMS)."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise TermExpansionError(f"cannot load dictionary {path}: {exc}") from None
        if not isinstance(data, dict):
            raise TermExpansionError(f"dictionary {path} must be an object")
        for key, entries in data.items():
            if not isinstance(entries, list):
                continue
            self._dict.setdefault(key, []).extend(entries)

    def expand(self, feature: FeatureSpec) -> list[TermCandidate]:
        statement = feature.statement
        lower = statement.lower()
        out: list[TermCandidate] = []
        for headword, entries in sorted(self._dict.items()):
            if headword in statement or headword in lower:
                for entry in entries:
                    term = str(entry.get("term") or "").strip()
                    relation = str(entry.get("relation") or "synonym")
                    if not term or term == headword:
                        continue
                    out.append(
                        TermCandidate(
                            term=term,
                            relation=relation,
                            feature_id=feature.feature_id,
                            source="seed-dictionary" if headword in SEED_TERMS else "user-dictionary",
                        )
                    )
        # the feature statement itself is always a base candidate (verified)
        out.insert(0, TermCandidate(term=statement, relation="base", feature_id=feature.feature_id, source="feature-statement"))
        return out


class CrossDomainExpander:
    """Cross-domain expansion: corpus co-occurrence mining with a dictionary fallback.

    Composition, in deterministic order:

    1. the **dictionary path** — delegated verbatim to an internal
       :class:`DictionaryExpander` (seed terms + optional user dictionaries), so a
       mining-less expander is exactly equivalent to today's behavior;
    2. the **mining path** (roadmap 41A-3) — when a :class:`MiningTable` is
       attached, seed tokens of the feature statement look up mined co-occurring
       terms, emitted as ``relation="cross_domain"`` candidates whose provenance
       carries the mining block (splits — train/val only — parameters, digest).
       Mined terms that duplicate a dictionary term (or each other) are dropped;
       mined terms are appended after dictionary terms, so the fallback path's
       output order is untouched.

    Mined terms stay *reviewable proposals*: they broaden the net (broadening
    relation) and never touch requiredness.
    """

    def __init__(
        self,
        mining: MiningTable | None = None,
        extra_dictionaries: list[Path] | None = None,
        *,
        max_mined_terms: int = 6,
    ) -> None:
        if max_mined_terms < 0:
            raise TermExpansionError("max_mined_terms must be >= 0")
        self._dictionary = DictionaryExpander(extra_dictionaries=extra_dictionaries)
        self._mining = mining
        self._max_mined_terms = max_mined_terms

    @property
    def mining(self) -> MiningTable | None:
        return self._mining

    def load_dictionary(self, path: Path) -> None:
        """Merge a user JSON dictionary into the fallback path (same as DictionaryExpander)."""
        self._dictionary.load_dictionary(path)

    def expand(self, feature: FeatureSpec) -> list[TermCandidate]:
        candidates = self._dictionary.expand(feature)
        if self._mining is None:
            return candidates
        statement_tokens = {normalize_term(tok) for tok in tokenize(feature.statement)}
        existing = {normalize_term(cand.term) for cand in candidates} | statement_tokens
        mined: list[TermCandidate] = []
        provenance_extra = {"mining": self._mining.mining_provenance()}
        for seed in sorted(statement_tokens):
            for entry in self._mining.terms_for(seed):
                key = normalize_term(entry.term)
                if not key or key in existing:
                    continue
                existing.add(key)
                mined.append(
                    TermCandidate(
                        term=entry.term,
                        relation="cross_domain",
                        feature_id=feature.feature_id,
                        source=f"cooccurrence:{self._mining.digest[:12]}",
                        verified=True,
                        extra=provenance_extra,
                    )
                )
                if len(mined) >= self._max_mined_terms:
                    return candidates + mined
        return candidates + mined


@dataclass
class LLMExpander:
    """Optional host-injected LLM expander. No client ships with the base wheel.

    ``client`` must be a callable ``(prompt: str) -> list[dict]`` returning entries
    with ``term``/``relation``. Results are proposals with ``source="llm:<model>"``;
    the host is responsible for network consent — this class performs no IO itself.
    """

    model_id: str
    client: Any = None
    #: terms the LLM proposed without any feature linkage
    _unlinked: list[TermCandidate] = field(default_factory=list, repr=False)

    def expand(self, feature: FeatureSpec) -> list[TermCandidate]:
        if self.client is None:
            return []
        prompt = (
            "Propose patent retrieval terms for this technical feature. "
            "Return JSON list of {term, relation} where relation is one of "
            "synonym|hypernym|hyponym|translation|abbreviation. "
            f"Feature: {feature.statement}"
        )
        try:
            raw = self.client(prompt)
        except Exception as exc:  # noqa: BLE001 - a failing expander must not kill planning
            self._unlinked.append(
                TermCandidate(term=f"<expander-error: {exc}>", relation="llm", feature_id=None, source=f"llm:{self.model_id}", verified=False)
            )
            return []
        out: list[TermCandidate] = []
        for entry in raw if isinstance(raw, list) else []:
            term = str((entry or {}).get("term") or "").strip()
            relation = str((entry or {}).get("relation") or "llm")
            if not term:
                continue
            out.append(
                TermCandidate(
                    term=term,
                    relation=relation,
                    feature_id=feature.feature_id,
                    source=f"llm:{self.model_id}",
                )
            )
        return out

    @property
    def unverified_proposals(self) -> list[TermCandidate]:
        return list(self._unlinked)


def expand_features(
    features: list[FeatureSpec],
    expanders: list[Expander] | None = None,
) -> dict[str, list[TermCandidate]]:
    """Expand every feature with every expander; returns ``feature_id -> candidates``.

    Necessary features are expanded for *retrieval terms only*: the caller (query
    planner) never promotes an expansion into a requiredness change (contract test
    in test_query_expand.py).
    """
    expanders = expanders or [DictionaryExpander()]
    result: dict[str, list[TermCandidate]] = {}
    for feature in features:
        candidates: list[TermCandidate] = []
        for expander in expanders:
            candidates.extend(expander.expand(feature))
        result[feature.feature_id] = candidates
    return result


def terms_to_query_spec(
    feature: FeatureSpec,
    candidates: list[TermCandidate],
    *,
    query_id: str,
    axis_id: str,
    source: str,
    query_type: str,
) -> QuerySpec:
    """Bundle term candidates into a QuerySpec proposal (approved=False)."""
    if feature.requiredness == Requiredness.NEGATION:
        # negative features must not become positive search terms (UT-Q01)
        raise TermExpansionError(
            f"feature {feature.feature_id} is a negation; it cannot seed positive query terms"
        )
    terms = []
    provenance = []
    seen: set[str] = set()
    for cand in candidates:
        if normalize_term(cand.term) in seen:
            continue
        seen.add(normalize_term(cand.term))
        terms.append(cand.term)
        provenance.append(cand.to_provenance())
    return QuerySpec(
        owner=_OWNER,
        query_id=query_id,
        axis_id=axis_id,
        terms=terms,
        language=detect_language(" ".join(terms)),
        query_type=query_type,
        source=source,
        provenance=provenance,
        approved=False,
    )
