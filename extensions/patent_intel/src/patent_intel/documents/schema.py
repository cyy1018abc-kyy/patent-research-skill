"""Structured patent document model (blueprint C-01/C-05).

A ``StructuredPatentDocument`` is the *only* thing downstream code may quote from:
every paragraph carries its parser-assigned id and verbatim text, and anchors made
from it bind the raw artifact's SHA-256 plus this parser version (interface rule 6 —
no OCR fragment may ever masquerade as an official paragraph number; the ``origin``
field distinguishes ``native_xml`` numbering from ``parser_assigned``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Paragraph", "Claim", "StructuredPatentDocument", "DocumentParseError", "PARSER_VERSION"]

#: Bump on any structural change — old anchors referencing a different version are
#: treated as stale by locators.py (UT-D02).
PARSER_VERSION = "patent_intel.documents 0.1.0"


class DocumentParseError(ValueError):
    """The document cannot be parsed honestly (malformed, unsafe, oversize…)."""


@dataclass(frozen=True)
class Paragraph:
    """One text unit. ``origin`` says whether the id is the source's own numbering."""

    para_id: str
    text: str
    origin: str  # "native_xml" | "parser_assigned"
    section: str  # "abstract" | "claims" | "description" | "other"
    page: int | None = None  # pdf only

    def describe(self) -> dict[str, Any]:
        return {"para_id": self.para_id, "origin": self.origin, "section": self.section, "page": self.page}


@dataclass(frozen=True)
class Claim:
    """One patent claim with its parsed dependency links."""

    number: int
    text: str
    depends_on: list[int]
    #: dependency references the parser could not resolve (not silently dropped)
    unresolved_refs: list[str] = field(default_factory=list)

    @property
    def is_independent(self) -> bool:
        return not self.depends_on and not self.unresolved_refs


@dataclass
class StructuredPatentDocument:
    """Parsed document: metadata + paragraphs + claims, hash-bound to its raw file."""

    source_document: str  # workspace-relative raw path
    raw_sha256: str
    parser_version: str = PARSER_VERSION
    publication_number: str | None = None
    title: str | None = None
    language: str | None = None
    paragraphs: list[Paragraph] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)

    def paragraph_by_id(self, para_id: str) -> Paragraph | None:
        for para in self.paragraphs:
            if para.para_id == para_id:
                return para
        return None

    def section_paragraphs(self, section: str) -> list[Paragraph]:
        return [p for p in self.paragraphs if p.section == section]

    def claim_by_number(self, number: int) -> Claim | None:
        for claim in self.claims:
            if claim.number == number:
                return claim
        return None

    def claim_tree_issues(self) -> list[str]:
        """Human-readable structural problems (duplicate numbers, circular deps, unknown refs)."""
        issues: list[str] = []
        numbers = [c.number for c in self.claims]
        if len(numbers) != len(set(numbers)):
            dupes = sorted({n for n in numbers if numbers.count(n) > 1})
            issues.append(f"duplicate claim numbers: {dupes}")
        by_number = {c.number: c for c in self.claims}
        for claim in self.claims:
            for dep in claim.depends_on:
                if dep not in by_number:
                    issues.append(f"claim {claim.number} depends on missing claim {dep}")
            # cycle detection: follow the dependency chain, revisit of self = circular
            stack = list(claim.depends_on)
            visited: set[int] = set()
            while stack:
                node = stack.pop()
                if node == claim.number:
                    issues.append(f"claim {claim.number}: circular dependency")
                    break
                if node in visited:
                    continue
                visited.add(node)
                node_claim = by_number.get(node)
                if node_claim is not None:
                    stack.extend(node_claim.depends_on)
        return issues

    def describe(self) -> dict[str, Any]:
        return {
            "source_document": self.source_document,
            "raw_sha256": self.raw_sha256,
            "parser_version": self.parser_version,
            "publication_number": self.publication_number,
            "title": self.title,
            "language": self.language,
            "paragraph_count": len(self.paragraphs),
            "claim_count": len(self.claims),
            "quality": self.quality,
        }
