"""Corpus co-occurrence mining for cross-domain query expansion (roadmap 41A-3).

Upgrades the cross-domain path from a hand-curated dictionary to **corpus
co-occurrence mining**: seed terms come from *topic text of the train/val
splits only*, co-occurrence statistics come from the frozen corpus snapshot,
and the mined table feeds :class:`~patent_intel.retrieval.query_expand.CrossDomainExpander`.

Split isolation is a signature-level contract, not a convention:

* :attr:`MINING_SPLITS` is ``("train", "val")`` — ``"test"`` is structurally
  rejected, no matter how the caller spells the request;
* :meth:`CooccurrenceMiner.mine` takes an **explicit, keyword-only** ``splits``
  argument; every topic must carry its own split label and every label must be
  one of the declared splits — a test topic smuggled into the topic list is a
  hard error, never a silent filter (fail-closed, check_leakage.py re-checks
  the written artifact independently);
* the miner reads topic *text* only — it never touches gold families, not even
  train-side ones, so no gold data of any split enters mining.

Determinism: identical topics + corpus + params ⇒ identical table bytes
(sorted iteration everywhere, rounded lift, stable tie-breaks, canonical JSON,
``digest`` = SHA-256 over the mining content). Zero third-party dependencies;
tokenization reuses :func:`patent_intel.retrieval.lexical.tokenize` so mined
terms live in the exact token space the BM25 engine searches.

Scoring: for a seed token ``s`` and candidate token ``t``,
``lift = P(t|s) / P(t) = co(s,t)·N / (df(s)·df(t))`` over documents. Candidates
must pass a co-occurrence floor, a document-frequency band (kills stopwords and
boilerplate) and a lift floor, then keep the top terms per seed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from patent_intel.retrieval.lexical import CorpusDoc, tokenize

__all__ = [
    "MINING_SPLITS",
    "MiningInputError",
    "MiningTableError",
    "MiningParams",
    "TopicSeed",
    "CooccurrenceEntry",
    "MiningTable",
    "CooccurrenceMiner",
]

#: Splits allowed to seed cross-domain mining. ``test`` must never appear here:
#: mining is train-side data preparation, and test topics (their text or gold)
#: entering the mining input would invalidate the evaluation protocol.
MINING_SPLITS = ("train", "val")

_OWNER = "WP-A"
_SCHEMA_VERSION = 1
_RECORD_TYPE = "cooccurrence_table"
_LIFT_DECIMALS = 6


class MiningInputError(ValueError):
    """Mining input violates the split-isolation contract (hard rejection)."""


class MiningTableError(ValueError):
    """A serialized mining table is malformed or fails its digest check."""


@dataclass(frozen=True)
class MiningParams:
    """Mining hyper-parameters. Recorded verbatim in the table and in every
    mined term's provenance — mined terms are always reproducible proposals."""

    min_cooccurrence: int = 2
    min_lift: float = 2.0
    min_df: int = 2
    #: candidate terms rarer than ``min_df`` or more common than
    #: ``max_df_ratio * corpus size`` are rejected (stopword/boilerplate band)
    max_df_ratio: float = 0.05
    max_terms_per_seed: int = 8

    def __post_init__(self) -> None:
        if self.min_cooccurrence < 1:
            raise ValueError("min_cooccurrence must be >= 1")
        if self.min_lift < 0:
            raise ValueError("min_lift must be >= 0")
        if self.min_df < 1:
            raise ValueError("min_df must be >= 1")
        if not 0 < self.max_df_ratio <= 1.0:
            raise ValueError("max_df_ratio must be in (0, 1]")
        if self.max_terms_per_seed < 1:
            raise ValueError("max_terms_per_seed must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_cooccurrence": self.min_cooccurrence,
            "min_lift": self.min_lift,
            "min_df": self.min_df,
            "max_df_ratio": self.max_df_ratio,
            "max_terms_per_seed": self.max_terms_per_seed,
        }


@dataclass(frozen=True)
class TopicSeed:
    """One mining seed: a topic's id, its OWN split label, and its seed text.

    ``split`` is the topic's label from the manifest — the miner cross-checks it
    against the declared splits on every call. ``text`` is topic text only
    (query view); gold families are deliberately not part of a seed.
    """

    topic_id: str
    split: str
    text: str


@dataclass(frozen=True)
class CooccurrenceEntry:
    """One mined candidate term for one seed token."""

    term: str
    co_occurrence: int  # documents containing both seed and term
    df: int  # documents containing the term
    lift: float  # rounded to _LIFT_DECIMALS; sort/serialize on this value only

    def to_dict(self) -> dict[str, Any]:
        return {"term": self.term, "co": self.co_occurrence, "df": self.df, "lift": self.lift}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _compute_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MiningTable:
    """A mined co-occurrence table (deterministic, digest-stamped, serializable).

    ``entries`` maps seed token → candidate terms, each list already sorted by
    ``(-lift, -co_occurrence, term)`` and capped at ``max_terms_per_seed``.
    """

    params: MiningParams
    splits: tuple[str, ...]  # declared (and validated) mining splits, sorted
    topic_ids: tuple[str, ...]  # exactly the topics consumed, sorted
    corpus_docs: int
    entries: Mapping[str, tuple[CooccurrenceEntry, ...]] = field(default_factory=dict)
    digest: str = ""  # SHA-256 over params + mining_input + corpus_docs + entries

    def terms_for(self, seed: str) -> tuple[CooccurrenceEntry, ...]:
        """Mined candidates for one seed token (table order, best first)."""
        return self.entries.get(seed, ())

    def mining_provenance(self) -> dict[str, Any]:
        """The provenance block carried by every mined expansion term: mining
        splits, parameters, corpus size, topic count and table digest."""
        return {
            "splits": list(self.splits),
            "params": self.params.to_dict(),
            "corpus_docs": self.corpus_docs,
            "topics": len(self.topic_ids),
            "digest": self.digest,
        }

    @classmethod
    def build(
        cls,
        *,
        params: MiningParams,
        splits: tuple[str, ...],
        topic_ids: tuple[str, ...],
        corpus_docs: int,
        entries: Mapping[str, tuple[CooccurrenceEntry, ...]],
    ) -> "MiningTable":
        """Construct a table and stamp its digest over the mining content."""
        payload = {
            "params": params.to_dict(),
            "mining_input": {
                "splits": list(splits),
                "topic_ids": list(topic_ids),
                "topics_total": len(topic_ids),
            },
            "corpus_docs": corpus_docs,
            "entries": {
                seed: [entry.to_dict() for entry in entries_in_seed]
                for seed, entries_in_seed in sorted(entries.items())
            },
        }
        return cls(
            params=params,
            splits=splits,
            topic_ids=topic_ids,
            corpus_docs=corpus_docs,
            entries=dict(entries),
            digest=_compute_digest(payload),
        )

    # -- serialization ---------------------------------------------------

    def _digest_payload(self) -> dict[str, Any]:
        return {
            "params": self.params.to_dict(),
            "mining_input": {
                "splits": list(self.splits),
                "topic_ids": list(self.topic_ids),
                "topics_total": len(self.topic_ids),
            },
            "corpus_docs": self.corpus_docs,
            "entries": {
                seed: [entry.to_dict() for entry in entries]
                for seed, entries in sorted(self.entries.items())
            },
        }

    def to_dict(self) -> dict[str, Any]:
        out = {
            "schema_version": _SCHEMA_VERSION,
            "record_type": _RECORD_TYPE,
            "owner": _OWNER,
            "digest": self.digest,
        }
        out.update(self._digest_payload())
        return out

    def to_json(self) -> str:
        """Deterministic serialization: same table ⇒ same bytes."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MiningTable":
        """Rebuild a table and verify its digest over the mining content.

        Unknown top-level keys (the benchmark artifact adds a ``provenance``
        block) are ignored; a digest mismatch means the mining content was
        tampered with and is a hard error.
        """
        if not isinstance(data, Mapping):
            raise MiningTableError("cooccurrence table must be a JSON object")
        if data.get("schema_version") != _SCHEMA_VERSION:
            raise MiningTableError(f"unsupported schema_version {data.get('schema_version')!r}")
        if data.get("record_type") != _RECORD_TYPE:
            raise MiningTableError(f"record_type must be {_RECORD_TYPE!r}")
        try:
            params = MiningParams(**data["params"])
            mining_input = data["mining_input"]
            splits = tuple(mining_input["splits"])
            topic_ids = tuple(mining_input["topic_ids"])
            corpus_docs = data["corpus_docs"]
            raw_entries = data["entries"]
            stored_digest = data["digest"]
        except (KeyError, TypeError) as exc:
            raise MiningTableError(f"cooccurrence table missing/invalid field: {exc}") from None
        if not isinstance(raw_entries, dict):
            raise MiningTableError("entries must be an object keyed by seed token")
        entries: dict[str, tuple[CooccurrenceEntry, ...]] = {}
        for seed, entry_list in raw_entries.items():
            parsed: list[CooccurrenceEntry] = []
            for item in entry_list if isinstance(entry_list, list) else []:
                try:
                    parsed.append(
                        CooccurrenceEntry(
                            term=str(item["term"]),
                            co_occurrence=int(item["co"]),
                            df=int(item["df"]),
                            lift=float(item["lift"]),
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise MiningTableError(f"bad entry under seed {seed!r}: {exc}") from None
            entries[str(seed)] = tuple(parsed)
        table = cls(
            params=params,
            splits=splits,
            topic_ids=topic_ids,
            corpus_docs=int(corpus_docs),
            entries=entries,
            digest=str(stored_digest),
        )
        computed = _compute_digest(table._digest_payload())
        if computed != table.digest:
            raise MiningTableError(
                f"cooccurrence table digest mismatch: recorded {table.digest[:12]}…, computed {computed[:12]}…"
            )
        return table


def _as_topic_seed(item: TopicSeed | Mapping[str, Any], index: int) -> TopicSeed:
    if isinstance(item, TopicSeed):
        return item
    if isinstance(item, Mapping):
        missing = [key for key in ("topic_id", "split", "text") if key not in item]
        if missing:
            raise MiningInputError(f"topics[{index}]: missing field(s) {missing}")
        return TopicSeed(
            topic_id=str(item["topic_id"]),
            split=str(item["split"]),
            text=str(item["text"]),
        )
    raise MiningInputError(f"topics[{index}]: expected TopicSeed or mapping, got {type(item).__name__}")


class CooccurrenceMiner:
    """Mines cross-domain candidate terms from topic-seeded corpus co-occurrence.

    The miner is pure computation: no IO, no network, no gold. It consumes topic
    seeds (:class:`TopicSeed`, text only) and a corpus snapshot
    (:class:`~patent_intel.retrieval.lexical.CorpusDoc` stream) and produces a
    deterministic :class:`MiningTable`.
    """

    def __init__(self, params: MiningParams | None = None) -> None:
        self.params = params or MiningParams()

    # -- public API --------------------------------------------------------

    def mine(
        self,
        topics: Sequence[TopicSeed | Mapping[str, Any]],
        corpus: Iterable[CorpusDoc],
        *,
        splits: str | Sequence[str],
    ) -> MiningTable:
        """Mine co-occurrence terms.

        ``splits`` is explicit and keyword-only on purpose: the caller must
        state which splits the topic batch comes from, and the miner enforces
        the train/val-only contract on both the declaration and every topic's
        own label. There is no default — silence is how test data leaks.
        """
        declared = self._validate_splits(splits)
        seeds = self._validate_topics(topics, declared)
        seed_tokens = sorted({tok for topic in seeds for tok in tokenize(topic.text)})
        if not seed_tokens:
            raise MiningInputError("topic text produced no seed tokens; nothing to mine")

        entries, n_docs = self._scan_corpus(seed_tokens, corpus, self.params)
        return MiningTable.build(
            params=self.params,
            splits=tuple(sorted(declared)),
            topic_ids=tuple(sorted(topic.topic_id for topic in seeds)),
            corpus_docs=n_docs,
            entries=entries,
        )

    # -- validation (fail-closed split isolation) --------------------------

    @staticmethod
    def _validate_splits(splits: str | Sequence[str]) -> tuple[str, ...]:
        declared = (splits,) if isinstance(splits, str) else tuple(splits)
        if not declared:
            raise MiningInputError(
                "splits declaration is empty; state the mining splits explicitly"
            )
        if len(set(declared)) != len(declared):
            raise MiningInputError(f"splits declaration has duplicates: {declared!r}")
        for split in declared:
            if split not in MINING_SPLITS:
                raise MiningInputError(
                    f"split {split!r} is not allowed in mining input "
                    f"(allowed: {MINING_SPLITS}); test-split data must never seed mining"
                )
        return declared

    @staticmethod
    def _validate_topics(
        topics: Sequence[TopicSeed | Mapping[str, Any]], declared: tuple[str, ...]
    ) -> list[TopicSeed]:
        if not topics:
            raise MiningInputError("no topics supplied for mining")
        seeds: list[TopicSeed] = []
        seen: set[str] = set()
        for index, item in enumerate(topics):
            topic = _as_topic_seed(item, index)
            if not topic.topic_id.strip():
                raise MiningInputError(f"topics[{index}]: empty topic_id")
            if topic.topic_id in seen:
                raise MiningInputError(f"topic {topic.topic_id!r} appears more than once")
            seen.add(topic.topic_id)
            # Per-topic label cross-check: this is what rejects a test topic
            # smuggled into the list, regardless of the declared splits.
            if topic.split not in declared:
                raise MiningInputError(
                    f"topic {topic.topic_id!r} declares split {topic.split!r} which is not "
                    f"among the declared mining splits {declared}; mining accepts only "
                    f"{MINING_SPLITS} — test-split topics must never enter the mining input"
                )
            if not topic.text.strip():
                raise MiningInputError(f"topic {topic.topic_id!r}: empty seed text")
            seeds.append(topic)
        return seeds

    # -- corpus scan -------------------------------------------------------

    def _scan_corpus(
        self, seed_tokens: list[str], corpus: Iterable[CorpusDoc], params: MiningParams
    ) -> tuple[dict[str, tuple[CooccurrenceEntry, ...]], int]:
        seed_set = set(seed_tokens)
        df: dict[str, int] = {}
        co: dict[str, dict[str, int]] = {seed: {} for seed in seed_tokens}
        seen_doc_ids: set[str] = set()
        n_docs = 0
        for doc in corpus:
            if doc.doc_id in seen_doc_ids:
                raise MiningInputError(f"duplicate doc_id {doc.doc_id!r} in corpus snapshot")
            seen_doc_ids.add(doc.doc_id)
            n_docs += 1
            tokens = set(tokenize(doc.text))
            for token in tokens:
                df[token] = df.get(token, 0) + 1
            seeds_in_doc = [token for token in tokens if token in seed_set]
            if not seeds_in_doc:
                continue
            for seed in seeds_in_doc:
                counts = co[seed]
                for other in tokens:
                    if other != seed:
                        counts[other] = counts.get(other, 0) + 1
        if n_docs == 0:
            raise MiningInputError("empty corpus snapshot; co-occurrence needs documents")
        max_df = params.max_df_ratio * n_docs
        if params.min_df > max_df:
            raise MiningInputError(
                f"min_df={params.min_df} exceeds max_df_ratio * corpus size "
                f"({params.max_df_ratio} * {n_docs} = {max_df:.1f}); no term can pass both "
                "bands — fix the parameters for this corpus instead of mining an empty table"
            )
        return self._score(co, df, n_docs, params), n_docs

    def _score(
        self,
        co: dict[str, dict[str, int]],
        df: Mapping[str, int],
        n_docs: int,
        params: MiningParams,
    ) -> dict[str, tuple[CooccurrenceEntry, ...]]:
        max_df = params.max_df_ratio * n_docs
        entries: dict[str, tuple[CooccurrenceEntry, ...]] = {}
        for seed in sorted(co):
            seed_df = df.get(seed, 0)
            if seed_df == 0:
                continue
            scored: list[CooccurrenceEntry] = []
            for term, count in co[seed].items():
                if count < params.min_cooccurrence:
                    continue
                term_df = df.get(term, 0)
                if term_df < params.min_df or term_df > max_df:
                    continue
                lift = round((count * n_docs) / (seed_df * term_df), _LIFT_DECIMALS)
                if lift < params.min_lift:
                    continue
                scored.append(CooccurrenceEntry(term=term, co_occurrence=count, df=term_df, lift=lift))
            scored.sort(key=lambda entry: (-entry.lift, -entry.co_occurrence, entry.term))
            entries[seed] = tuple(scored[: params.max_terms_per_seed])
        return {seed: tup for seed, tup in entries.items() if tup}
