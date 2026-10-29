"""Claim structure extraction (blueprint C-02): dependency parsing and tree building.

Dependency references the parser cannot resolve are kept in ``unresolved_refs``
(marked ``unknown``) — never dropped, never guessed (C-02 acceptance).
"""

from __future__ import annotations

import re

from patent_intel.documents.schema import Claim, StructuredPatentDocument

__all__ = ["parse_claim_dependencies", "EN_DEP", "ZH_DEP"]

#: "according to claim 2", "as in claim 1", "of any one of claims 2 to 4"
EN_DEP = re.compile(
    r"(?:according to|as in|of|recited in|as claimed in)\s+(?:any one of\s+)?"
    r"claims?\s+([0-9]+)((?:\s*(?:,|to|or|-)\s*[0-9]+)*)",
    re.IGNORECASE,
)
#: 根据权利要求1-3任一项所述 / 按照权利要求2
ZH_DEP = re.compile(r"(?:根据|按照|依[据照])权利要求\s*([0-9]+)((?:\s*[-~至到或、和]\s*[0-9]+)*)")


def parse_claim_dependencies(doc: StructuredPatentDocument) -> list[Claim]:
    """(Re)build ``doc.claims`` from the claims-section paragraphs.

    References to claim numbers that do not exist in the document go to
    ``unresolved_refs`` (marked unknown) instead of ``depends_on`` — dropped
    references would silently corrupt the dependency tree.
    """
    # pass 1: claim numbers that actually exist (from native ids or leading text)
    numbered: list[tuple[int, str]] = []
    for para in doc.section_paragraphs("claims"):
        if para.para_id.startswith("claim-"):
            digits = "".join(ch for ch in para.para_id[len("claim-"):] if ch.isdigit())
            if digits:
                numbered.append((int(digits), para.text))
                continue
        number, body = _leading_number(para.text)
        if number is not None:
            numbered.append((number, body))
    known = {number for number, _ in numbered}

    # pass 2: dependency classification
    claims: list[Claim] = []
    for number, body in numbered:
        depends: list[int] = []
        unresolved: list[str] = []
        for pattern in (EN_DEP, ZH_DEP):
            for match in pattern.finditer(body):
                refs = [int(match.group(1))] + [int(x) for x in re.findall(r"[0-9]+", match.group(2) or "")]
                for ref in refs:
                    if ref in known:
                        depends.append(ref)
                    else:
                        unresolved.append(str(ref))
        claims.append(
            Claim(
                number=number,
                text=body,
                depends_on=sorted(set(depends)),
                unresolved_refs=sorted(set(unresolved)),
            )
        )
    doc.claims = claims
    return claims


def _leading_number(text: str) -> tuple[int | None, str]:
    """Extract the claim's own number from its leading phrase."""
    m = re.match(r"^\s*([0-9]+)\s*[\.、．]?\s*(.*)$", text, re.DOTALL)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, text
