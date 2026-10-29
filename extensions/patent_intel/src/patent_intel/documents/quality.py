"""Parsing quality assessment (blueprint C-03/C-05).

Heuristic, honest, conservative: a document whose text shows OCR/parser damage gets
a low score, and the locators built from it inherit ``verification_status=unverified``
— low quality never silently upgrades to citable evidence (interface rule 6).
"""

from __future__ import annotations

from typing import Any

__all__ = ["assess_quality", "QUALITY_THRESHOLD"]

#: Below this overall score, locators refuse auto-citation status.
QUALITY_THRESHOLD = 0.7


def assess_quality(doc: Any) -> dict[str, Any]:
    paragraphs = list(getattr(doc, "paragraphs", []) or [])
    total = len(paragraphs)
    if total == 0:
        return {"score": 0.0, "empty": True, "suspicious_ratio": 1.0, "notes": ["no paragraphs parsed"]}

    replacement_chars = 0
    total_chars = 0
    suspicious = 0
    for para in paragraphs:
        text = para.text
        total_chars += len(text)
        replacement_chars += text.count("\ufffd")
        # suspicious: mostly punctuation/control, or extremely short for a patent paragraph
        alnum = sum(ch.isalnum() for ch in text)
        if len(text) > 0 and alnum / max(1, len(text)) < 0.3:
            suspicious += 1
        elif 0 < len(text) < 8 and para.section == "description":
            suspicious += 1

    replacement_ratio = replacement_chars / max(1, total_chars)
    suspicious_ratio = suspicious / total
    score = max(0.0, 1.0 - replacement_ratio * 5.0 - suspicious_ratio * 0.8)
    notes: list[str] = []
    if replacement_ratio > 0.01:
        notes.append(f"high replacement-char ratio ({replacement_ratio:.3f}) — OCR damage likely")
    if suspicious_ratio > 0.2:
        notes.append(f"{suspicious}/{total} paragraphs look non-textual")
    return {
        "score": round(score, 4),
        "empty": False,
        "replacement_ratio": round(replacement_ratio, 5),
        "suspicious_ratio": round(suspicious_ratio, 4),
        "paragraph_count": total,
        "notes": notes,
        "citable": score >= QUALITY_THRESHOLD,
    }
