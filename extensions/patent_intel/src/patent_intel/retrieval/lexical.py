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

from patent_intel.retrieval.terminology import normalize_term

__all__ = ["CorpusDoc", "BM25Index", "tokenize"]

_CJK = re.compile(r"[\u4e00-\u9fff]")
_WORD = re.compile(r"[a-zA-Z0-9]+")

_OWNER = "WP-A"


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

        Deterministic: equal scores order by doc_id ascending.
        """
        if k <= 0:
            raise ValueError("k must be positive")
        query_terms = tokenize(query)
        scores: dict[str, float] = {}
        for doc_id, tf_map in self._tf.items():
            doc_len = self._len[doc_id]
            if doc_len == 0:
                continue
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * doc_len / self._avg_len)
            for term in query_terms:
                tf = tf_map.get(term, 0)
                if tf == 0:
                    continue
                idf = self.idf(term)
                if idf <= 0:
                    continue
                score += idf * (tf * (self.k1 + 1)) / (tf + norm)
            if score > 0:
                scores[doc_id] = score
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:k]

    def explain(self, doc_id: str, query: str) -> dict[str, float]:
        """Per-term score contributions (auditability for ranking diagnostics)."""
        tf_map = self._tf.get(doc_id, {})
        doc_len = self._len.get(doc_id, 0)
        norm = self.k1 * (1 - self.b + self.b * doc_len / self._avg_len) if doc_len else 1.0
        out: dict[str, float] = {}
        for term in tokenize(query):
            tf = tf_map.get(term, 0)
            if tf:
                idf = self.idf(term)
                out[term] = idf * (tf * (self.k1 + 1)) / (tf + norm)
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
