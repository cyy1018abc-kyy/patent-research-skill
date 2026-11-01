"""Offline lexical retrieval: deterministic BM25 over a local corpus (blueprint A-04).

Corpus documents are kernel-adjacent objects (candidates, raw captures, NPL records)
turned into ``(doc_id, text, family_id)`` triples. Ranking is pure stdlib and fully
deterministic: identical corpus + query + parameters ⇒ identical ranking (UT-R01);
ties break by doc id. Dense retrieval and RRF fusion live in :mod:`.hybrid` and
degrade to lexical-only when the `dense` extra is absent.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

import os

from patent_intel.retrieval.terminology import normalize_term

__all__ = ["CorpusDoc", "BM25Index", "BM25FIndex", "tokenize"]

_CJK = re.compile(r"[\u4e00-\u9fff]")
_WORD = re.compile(r"[a-zA-Z0-9]+")

_OWNER = "WP-A"


def _numpy_enabled() -> bool:
    """Vectorized search path toggle: on unless numpy is missing or the escape
    hatch is set (tests pin the pure-Python path to compare both)."""
    if os.environ.get("PATENT_INTEL_BM25_FORCE_PY"):
        return False
    try:
        import numpy  # noqa: F401
    except ImportError:
        return False
    return True


def tokenize(text: str) -> list[str]:
    """Deterministic tokenizer: ASCII word tokens + CJK bigrams (single CJK chars
    carry too much ambiguity for BM25; bigrams are the standard cheap baseline)."""
    tokens: list[str] = []
    for word in _WORD.findall(text):
        tokens.append(word.lower())
    i = 0
    chars = [ch for ch in text if _CJK.match(ch)]
    while i + 1 < len(chars):
        tokens.append(chars[i] + chars[i + 1])
        i += 1
    if len(chars) == 1:
        tokens.append(chars[0])
    return tokens


@dataclass(frozen=True)
class CorpusDoc:
    doc_id: str
    text: str
    family_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BM25Index:
    """Okapi BM25 over an in-memory corpus. k1/b default from the sidecar config."""

    def __init__(
        self,
        docs: Iterable[CorpusDoc],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.docs: dict[str, CorpusDoc] = {}
        self._tf: dict[str, dict[str, int]] = {}
        self._len: dict[str, int] = {}
        self._df: dict[str, int] = {}
        for doc in docs:
            if doc.doc_id in self.docs:
                raise ValueError(f"duplicate doc_id {doc.doc_id!r} in corpus")
            tokens = tokenize(doc.text)
            self.docs[doc.doc_id] = doc
            tf: dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self._tf[doc.doc_id] = tf
            self._len[doc.doc_id] = len(tokens)
            for token in set(tokens):
                self._df[token] = self._df.get(token, 0) + 1
        self._avg_len = (sum(self._len.values()) / len(self._len)) if self._len else 0.0
        # Inverted storage: term -> {doc_id: tf} (transposed from doc-major tf once
        # at build time). Identical information, but search() walks postings for the
        # query's terms instead of scanning every document — a 45k-doc corpus with
        # full-text queries turned the per-doc scan into ~30s per request. Score
        # semantics are unchanged (only docs containing a query term can score > 0;
        # duplicate query tokens still weight a term once per occurrence).
        postings: dict[str, dict[str, int]] = {}
        for doc_id, tf_map in self._tf.items():
            for token, count in tf_map.items():
                bucket = postings.get(token)
                if bucket is None:
                    postings[token] = {doc_id: count}
                else:
                    bucket[doc_id] = count
        self._postings = postings
        del self._tf  # free the doc-major copy; everything reads _postings now
        # Precomputed per-doc length norm (4.1-A1): the search hot loop visits the
        # same (doc, term) pairs millions of times on full-text corpora and the norm
        # is constant per doc — compute it once with the IDENTICAL expression, so
        # every value is bit-for-bit what the inline computation produced.
        self._norm = {
            doc_id: self.k1 * (1 - self.b + self.b * doc_len / self._avg_len)
            for doc_id, doc_len in self._len.items() if doc_len > 0
        }
        self._np = self._build_numpy() if _numpy_enabled() else None

    def _build_numpy(self):
        """Columnar postings (doc-index int32, tf int32) for the vectorized path.

        Score arithmetic is IEEE-identical to the dict path: same expression tree
        per (doc, term), same per-doc accumulation order (terms iterated in query
        order), float64 throughout. Rank ties keep doc_id order via the lexicographic
        rank array. Returns None when numpy is unavailable.
        """
        try:
            import numpy as np
        except ImportError:
            return None
        doc_ids = sorted(self.docs)  # deterministic lexicographic doc order
        doc_index = {doc_id: i for i, doc_id in enumerate(doc_ids)}
        terms: dict[str, tuple] = {}
        for term, bucket in self._postings.items():
            ids = sorted(bucket)  # doc_id ascending → idx ascending (searchsorted-ready)
            idx = np.fromiter((doc_index[d] for d in ids), dtype=np.int32, count=len(ids))
            tfs = np.fromiter((bucket[d] for d in ids), dtype=np.int32, count=len(ids))
            terms[term] = (idx, tfs)
        norm_vec = np.fromiter(
            (self._norm[d] for d in doc_ids), dtype=np.float64, count=len(doc_ids))
        del self._postings  # dict copy no longer needed in numpy mode (~3 GB on 45k docs)
        return {"np": np, "doc_ids": doc_ids, "doc_index": doc_index,
                "terms": terms, "norm": norm_vec}

    def __len__(self) -> int:
        return len(self.docs)

    def idf(self, term: str) -> float:
        """BM25+ style idf, floored at 0 (never negative weights)."""
        n = len(self.docs)
        df = self._df.get(term, 0)
        if df == 0:
            return 0.0
        return max(0.0, math.log((n - df + 0.5) / (df + 0.5) + 1.0))

    def search(self, query: str, *, k: int = 10) -> list[tuple[str, float]]:
        """Rank documents for the query. Returns [(doc_id, score)] best-first.

        Deterministic: equal scores order by doc_id ascending. The numpy path (when
        available) is IEEE-bit-identical to the pure-Python path — see _build_numpy.
        """
        if k <= 0:
            raise ValueError("k must be positive")
        if self._np is not None:
            return self._search_np(query, k)
        return self._search_py(query, k)

    def _search_py(self, query: str, k: int) -> list[tuple[str, float]]:
        query_terms = tokenize(query)
        scores: dict[str, float] = {}
        postings_all = self._postings
        norm_map = self._norm
        k1p1 = self.k1 + 1.0
        for term in query_terms:
            postings = postings_all.get(term)
            if not postings:
                continue
            idf = self.idf(term)
            if idf <= 0:
                continue
            for doc_id, tf in postings.items():
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * (tf * k1p1) / (tf + norm_map[doc_id])
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:k]

    def _search_np(self, query: str, k: int) -> list[tuple[str, float]]:
        np = self._np["np"]
        terms = self._np["terms"]
        norm_vec = self._np["norm"]
        scores = np.zeros(len(self._np["doc_ids"]), dtype=np.float64)
        k1p1 = self.k1 + 1.0
        for term in tokenize(query):
            entry = terms.get(term)
            if entry is None:
                continue
            idx, tfs = entry
            idf = self.idf(term)
            if idf <= 0:
                continue
            scores[idx] += idf * (tfs * k1p1) / (tfs + norm_vec[idx])
        positive = np.nonzero(scores > 0.0)[0]
        if positive.size == 0:
            return []
        # lexsort: last key is primary → order by (-score, lexicographic doc order);
        # doc_index IS the lexicographic rank (doc_ids built from sorted(self.docs))
        order = np.lexsort((positive, -scores[positive]))
        top = positive[order[:k]]
        return [(self._np["doc_ids"][int(i)], float(scores[int(i)])) for i in top]

    def explain(self, doc_id: str, query: str) -> dict[str, float]:
        """Per-term score contributions (auditability for ranking diagnostics)."""
        doc_len = self._len.get(doc_id, 0)
        norm = self._norm[doc_id] if doc_len else 1.0
        out: dict[str, float] = {}
        if self._np is not None:
            np = self._np["np"]
            di = self._np["doc_index"].get(doc_id)
            if di is None:
                return out
            for term in tokenize(query):
                entry = self._np["terms"].get(term)
                if entry is None:
                    continue
                idx, tfs = entry
                pos = int(np.searchsorted(idx, di))
                if pos < len(idx) and int(idx[pos]) == di:
                    tf = int(tfs[pos])
                    out[term] = self.idf(term) * (tf * (self.k1 + 1.0)) / (tf + norm)
            return out
        for term in tokenize(query):
            tf = self._postings.get(term, {}).get(doc_id, 0)
            if tf:
                idf = self.idf(term)
                out[term] = idf * (tf * (self.k1 + 1.0)) / (tf + norm)
        return out


def corpus_from_candidates(candidates: list[dict[str, Any]]) -> list[CorpusDoc]:
    """Build corpus docs from kernel candidate records (03_candidates shape)."""
    docs: list[CorpusDoc] = []
    for cand in candidates:
        doc_id = str(cand.get("id") or cand.get("url_or_doc_number") or "")
        if not doc_id:
            continue
        text = " ".join(
            str(part)
            for part in (cand.get("title"), cand.get("summary_zh"), " ".join(cand.get("tags") or []))
            if part
        )
        family = cand.get("family") or None
        family_id = str(family[0]) if isinstance(family, list) and family else None
        docs.append(CorpusDoc(doc_id=doc_id, text=text, family_id=family_id, metadata={"kind": cand.get("kind")}))
    return docs


class BM25FIndex:
    """Field-weighted BM25F (roadmap §4.1; ablation ABL-1 A1..A3).

    score(q, d) = Σ_f w_f · BM25_f(q, d): each field is scored with the same Okapi
    conventions as :class:`BM25Index` (idf floored at 0, k1/b length norm against
    the field's own average length) and the per-field scores are weighted and
    summed. A document absent from a field's postings (empty field) contributes 0
    for that field — an empty field is never an error and never a fabricated score.

    Deterministic: ties by doc_id ascending. ``search(..., fields=...)`` restricts
    which fields are searched (the mechanical request variants); weights are NOT
    renormalized within a subset — they are per-field multipliers, period. Built
    with the same inverted-postings + precomputed-norm technique as BM25Index's
    fast path.
    """

    def __init__(
        self,
        fields_by_doc: dict[str, dict[str, str]],
        *,
        weights: dict[str, float],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if not fields_by_doc:
            raise ValueError("empty corpus")
        if any(w < 0 for w in weights.values()):
            raise ValueError("field weights must be non-negative")
        self.k1 = k1
        self.b = b
        self.weights = dict(weights)
        self._n_docs = len(fields_by_doc)
        self._all_doc_ids = sorted(fields_by_doc)
        self.fields: list[str] = []
        self._postings: dict[str, dict[str, dict[str, int]]] = {}
        self._df: dict[str, dict[str, int]] = {}
        self._norm: dict[str, dict[str, float]] = {}
        field_tokens: dict[str, dict[str, list[str]]] = {}
        for doc_id, fields in fields_by_doc.items():
            for field_name, text in fields.items():
                if field_name not in self.weights:
                    continue  # unweighted fields are not indexed at all
                field_tokens.setdefault(field_name, {})[doc_id] = tokenize(text or "")
        if not field_tokens:
            raise ValueError("no indexed field overlaps the supplied weights")
        for field_name in sorted(field_tokens):
            self.fields.append(field_name)
            docs = field_tokens[field_name]
            postings: dict[str, dict[str, int]] = {}
            df: dict[str, int] = {}
            lengths: dict[str, int] = {}
            for doc_id, tokens in docs.items():
                lengths[doc_id] = len(tokens)
                for token in tokens:
                    bucket = postings.get(token)
                    if bucket is None:
                        postings[token] = {doc_id: 1}
                        df[token] = 1
                    elif doc_id in bucket:
                        bucket[doc_id] += 1
                    else:
                        bucket[doc_id] = 1
                        df[token] += 1
            self._postings[field_name] = postings
            self._df[field_name] = df
            avg = (sum(lengths.values()) / len(lengths)) if lengths else 0.0
            self._norm[field_name] = {
                doc_id: self.k1 * (1 - self.b + self.b * length / avg)
                for doc_id, length in lengths.items() if length > 0
            }
            del docs
        del field_tokens
        self._np = self._build_numpy() if _numpy_enabled() else None

    def __len__(self) -> int:
        return self._n_docs

    def _idf(self, field: str, term: str) -> float:
        """Same BM25+ style floored idf as BM25Index, per-field df."""
        df = self._df[field].get(term, 0)
        if df == 0:
            return 0.0
        return max(0.0, math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1.0))

    def _build_numpy(self):
        """Columnar per-field postings over a shared global doc order.

        The vectorized arithmetic uses the SAME expression tree as the pure-Python
        path — ((w·idf) · tf) · k1p1 / (tf + norm) — so the two paths are
        IEEE-bit-identical (UT-R01 discipline, mirroring BM25Index._build_numpy).
        """
        try:
            import numpy as np
        except ImportError:
            return None
        doc_ids = self._all_doc_ids
        doc_index = {doc_id: i for i, doc_id in enumerate(doc_ids)}
        per_field: dict[str, dict[str, tuple]] = {}
        norm_vecs: dict[str, Any] = {}
        for field in self.fields:
            postings = self._postings[field]
            terms: dict[str, tuple] = {}
            for term, bucket in postings.items():
                ids = sorted(bucket)
                idx = np.fromiter((doc_index[d] for d in ids), dtype=np.int32, count=len(ids))
                tfs = np.fromiter((bucket[d] for d in ids), dtype=np.int32, count=len(ids))
                terms[term] = (idx, tfs)
            per_field[field] = terms
            norm_vecs[field] = np.fromiter(
                (self._norm[field].get(d, 0.0) for d in doc_ids), dtype=np.float64, count=len(doc_ids))
        return {"np": np, "doc_ids": doc_ids, "per_field": per_field, "norm": norm_vecs}

    def search(
        self, query: str, *, k: int = 10, fields: list[str] | None = None
    ) -> list[tuple[str, float]]:
        """Rank documents for the query; ``fields=None`` searches all indexed fields.

        Deterministic: ties by doc_id ascending. Query tokens are iterated raw
        (duplicates weight repeatedly), matching BM25Index conventions. The numpy
        path (when available) is IEEE-bit-identical to the pure-Python path.
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        active = [f for f in self.fields if fields is None or f in fields]
        if fields is not None:
            unknown = set(fields) - set(self.fields)
            if unknown:
                raise ValueError(f"unknown fields {sorted(unknown)} (indexed: {self.fields})")
        if self._np is not None:
            return self._search_np(query, k, active)
        return self._search_py(query, k, active)

    def _search_py(self, query: str, k: int, active: list[str]) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        k1p1 = self.k1 + 1.0
        for field in active:
            weight = self.weights.get(field, 1.0)
            if weight == 0.0:
                continue
            postings = self._postings[field]
            norm_map = self._norm[field]
            for token in tokenize(query):
                bucket = postings.get(token)
                if not bucket:
                    continue
                scaled_idf = weight * self._idf(field, token)
                if scaled_idf <= 0.0:
                    continue
                for doc_id, tf in bucket.items():
                    norm = norm_map.get(doc_id)
                    if norm is None:
                        continue
                    contribution = (scaled_idf * tf) * k1p1 / (tf + norm)
                    scores[doc_id] = scores.get(doc_id, 0.0) + contribution
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:k]

    def _search_np(self, query: str, k: int, active: list[str]) -> list[tuple[str, float]]:
        np = self._np["np"]
        doc_ids = self._np["doc_ids"]
        scores = np.zeros(len(doc_ids), dtype=np.float64)
        k1p1 = self.k1 + 1.0
        for field in active:
            weight = self.weights.get(field, 1.0)
            if weight == 0.0:
                continue
            terms = self._np["per_field"][field]
            norm_vec = self._np["norm"][field]
            for token in tokenize(query):
                entry = terms.get(token)
                if entry is None:
                    continue
                idx, tfs = entry
                scaled_idf = weight * self._idf(field, token)
                if scaled_idf <= 0.0:
                    continue
                scores[idx] += (scaled_idf * tfs) * k1p1 / (tfs + norm_vec[idx])
        positive = np.nonzero(scores > 0.0)[0]
        if positive.size == 0:
            return []
        order = np.lexsort((positive, -scores[positive]))
        top = positive[order[:k]]
        return [(doc_ids[int(i)], float(scores[int(i)])) for i in top]


_ = normalize_term  # kept import for API stability of diagnostic tooling
