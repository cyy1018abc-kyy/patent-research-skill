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

__all__ = ["CorpusDoc", "BM25Index", "tokenize"]

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


_ = normalize_term  # kept import for API stability of diagnostic tooling
